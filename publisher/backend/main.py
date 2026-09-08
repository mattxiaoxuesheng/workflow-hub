import hashlib
import hmac
import io
import json
import os
import secrets
import threading
import time
from pathlib import Path

import yaml
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import select, insert, update, delete, func

from . import db
from .content import read_package, image_refs, asset_path
from .render import render, templates, TEMPLATE_DIR
from .wechat import WeChat, WeChatError

ROOT = Path(__file__).resolve().parents[1]
password_hasher = PasswordHasher()
def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()

class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
class UserInput(Login):
    role: str = 'EDITOR'
class Edit(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    markdown: str = Field(min_length=1, max_length=500_000)
    template: str
    base_version_id: int
class TokenInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    days: int = Field(default=90, ge=1, le=365)
class PublishInput(BaseModel):
    confirm_version_id: int
class StatusInput(BaseModel):
    status: str

def create_app(data_dir=None, testing=False, wechat=None):
    cfg = yaml.safe_load(Path(os.getenv('PUBLISHER_CONFIG', ROOT / 'config/app.yaml')).read_text())
    data = Path(data_dir or os.getenv('PUBLISHER_DATA_DIR', ROOT / 'data')).resolve()
    data.mkdir(parents=True, exist_ok=True)
    blobs = data / 'assets'; blobs.mkdir(exist_ok=True)
    engine = db.open_db(data / 'publisher.db')
    app = FastAPI(title=cfg['app']['name'], docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine
    app.state.wechat = wechat or WeChat(os.getenv('WECHAT_APP_ID', ''), os.getenv('WECHAT_APP_SECRET', ''))
    lock = threading.RLock()  # one worker in production; DB keeps constraints as second boundary
    login_attempts = {}
    dummy_hash = password_hasher.hash(secrets.token_urlsafe(24))
    secure = not testing and os.getenv('COOKIE_SECURE', 'true').lower() != 'false'
    origin = os.getenv('PUBLISHER_ORIGIN', '').rstrip('/')

    def log(c, actor, action, target=''):
        c.execute(insert(db.audit).values(actor=str(actor), action=action, target=str(target), created_at=time.time()))
    def row(c, table, id):
        r = c.execute(select(table).where(table.c.id == id)).mappings().first()
        if not r: raise HTTPException(404, '记录不存在')
        return dict(r)

    @app.middleware('http')
    async def security(request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.url.path != '/api/v1/ingest':
            expected = origin or ('http://testserver' if testing else '')
            if not expected or request.headers.get('origin') != expected:
                return JSONResponse({'detail': '来源校验失败，请配置 PUBLISHER_ORIGIN'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https://mmbiz.qpic.cn https://mmbiz.qlogo.cn; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def current(request: Request):
        sid = request.cookies.get('publisher_session', '')
        with engine.begin() as c:
            session = c.execute(select(db.sessions).where(db.sessions.c.token_hash == digest(sid), db.sessions.c.expires_at > time.time())).mappings().first()
            if not session: raise HTTPException(401, '请登录')
            user = row(c, db.users, session['user_id'])
        if user['status'] != 'active': raise HTTPException(401, '账号已禁用')
        if request.method not in ('GET', 'HEAD') and not hmac.compare_digest(request.headers.get('x-csrf-token', ''), session['csrf']):
            raise HTTPException(403, 'CSRF校验失败')
        return {**user, 'csrf': session['csrf']}
    def admin(user=Depends(current)):
        if user['role'] != 'ADMIN': raise HTTPException(403, '需要管理员权限')
        return user

    @app.get('/healthz')
    def health(): return {'status': 'ok'}

    @app.post('/api/v1/login')
    def login(body: Login, request: Request):
        key = request.client.host
        now = time.time()
        with lock:
            attempts = [x for x in login_attempts.get(key, []) if x > now - 300]
            if len(attempts) >= 10: raise HTTPException(429, '尝试过多，请5分钟后重试')
            login_attempts[key] = attempts + [now]
        with engine.begin() as c:
            u = c.execute(select(db.users).where(db.users.c.username == body.username)).mappings().first()
            try:
                password_hasher.verify(u['password_hash'] if u else dummy_hash, body.password)
                if not u or u['status'] != 'active': raise ValueError()
            except (VerificationError, ValueError):
                log(c, body.username, 'login_failed')
                return JSONResponse({'detail': '用户名或密码错误'}, status_code=401)
            sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            ttl = int(cfg['security']['session_expire_hours'] * 3600)
            c.execute(delete(db.sessions).where(db.sessions.c.expires_at < now))
            c.execute(insert(db.sessions).values(token_hash=digest(sid), user_id=u['id'], csrf=csrf, expires_at=now+ttl))
            log(c, u['username'], 'login')
        result = JSONResponse({'username': u['username'], 'role': u['role'], 'csrf': csrf})
        result.set_cookie('publisher_session', sid, max_age=ttl, secure=secure, httponly=True, samesite='strict')
        return result

    @app.get('/api/v1/me')
    def me(user=Depends(current)):
        return {k: user[k] for k in ('username', 'role', 'csrf')}

    @app.post('/api/v1/logout')
    def logout(request: Request, user=Depends(current)):
        with engine.begin() as c:
            c.execute(delete(db.sessions).where(db.sessions.c.token_hash == digest(request.cookies['publisher_session'])))
        r = JSONResponse({'ok': True}); r.delete_cookie('publisher_session'); return r

    def asset_map(c, version_id):
        return {r['path']: dict(r) for r in c.execute(select(db.assets).where(db.assets.c.version_id == version_id)).mappings()}

    def save_version(c, article_id, title, markdown, template, cover, assets, actor, commit='', package_hash=None):
        render(markdown, template, assets)
        css = (TEMPLATE_DIR / f'{template}.css').read_text()
        n = c.execute(select(func.coalesce(func.max(db.versions.c.number), 0)).where(db.versions.c.article_id == article_id)).scalar_one() + 1
        v = c.execute(insert(db.versions).values(article_id=article_id, number=n, title=title, markdown=markdown, template=template, template_css=css,
            cover=cover, git_commit=commit, package_hash=package_hash, created_by=actor, created_at=time.time())).inserted_primary_key[0]
        for name, a in assets.items():
            c.execute(insert(db.assets).values(version_id=v, path=name, sha256=a['sha256'], mime=a['mime']))
        c.execute(update(db.articles).where(db.articles.c.id == article_id).values(title=title, updated_at=time.time()))
        log(c, actor, 'version_created', v)
        return {'article_id': article_id, 'version_id': v, 'number': n}

    def ingest_token(request):
        value = request.headers.get('authorization', '')
        if not value.startswith('Bearer '): raise HTTPException(401, '缺少上传Token')
        with engine.begin() as c:
            token = c.execute(select(db.tokens).where(db.tokens.c.token_hash == digest(value[7:]))).mappings().first()
            if not token or token['revoked_at'] or token['expires_at'] < time.time() or token['scope'] != 'article:ingest':
                raise HTTPException(401, '上传Token无效')
            c.execute(update(db.tokens).where(db.tokens.c.id == token['id']).values(last_used_at=time.time()))
            return token['name']

    @app.post('/api/v1/ingest')
    async def ingest(request: Request):
        actor = 'token:' + ingest_token(request)  # authenticate before reading multipart
        limit = int(cfg['article']['max_upload_mb'] * 1024**2)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > limit: raise HTTPException(413, '上传包过大')
        # Rehydrate a bounded request for Starlette's multipart parser.
        sent = False
        async def receive():
            nonlocal sent
            if sent: return {'type': 'http.disconnect'}
            sent = True
            return {'type': 'http.request', 'body': bytes(raw), 'more_body': False}
        bounded = Request(request.scope, receive)
        async with bounded.form(max_files=1, max_fields=0, max_part_size=limit) as form:
            package = form.get('package')
            if package is None or not hasattr(package, 'read'): raise HTTPException(422, '缺少package文件')
            content = await package.read()
        try:
            manifest, files, markdown, refs, cover, package_hash = read_package(content, int(cfg['article']['max_unpacked_mb']*1024**2), cfg['article']['max_files'])
            amap = {}
            for name in set(refs + [cover]):
                sha = hashlib.sha256(files[name]).hexdigest()
                with Image.open(io.BytesIO(files[name])) as im: mime = Image.MIME[im.format]
                dest = blobs / sha
                if not dest.exists():
                    tmp = blobs / (sha + '.' + secrets.token_hex(6))
                    tmp.write_bytes(files[name]); tmp.replace(dest)
                amap[name] = {'sha256': sha, 'mime': mime}
        except Exception as e:
            raise HTTPException(422, '内容包校验失败：' + str(e)[:200]) from e
        with lock, engine.begin() as c:
            a = c.execute(select(db.articles).where(db.articles.c.slug == manifest['slug'])).mappings().first()
            if a:
                old = c.execute(select(db.versions).where(db.versions.c.article_id == a['id'], db.versions.c.package_hash == package_hash)).mappings().first()
                if old: return {'article_id': a['id'], 'version_id': old['id'], 'number': old['number'], 'duplicate': True}
                aid = a['id']
            else:
                aid = c.execute(insert(db.articles).values(slug=manifest['slug'], title=manifest['title'], created_at=time.time(), updated_at=time.time())).inserted_primary_key[0]
            return save_version(c, aid, manifest['title'], markdown, cfg['article']['default_template'], cover, amap, actor, str(manifest.get('git_commit', ''))[:80], package_hash)

    @app.get('/api/v1/articles')
    def article_list(user=Depends(current)):
        with engine.begin() as c:
            result = []
            for a in c.execute(select(db.articles).order_by(db.articles.c.updated_at.desc())).mappings():
                versions = [dict(v) for v in c.execute(select(db.versions.c.id, db.versions.c.number, db.versions.c.template, db.versions.c.title).where(db.versions.c.article_id == a['id']).order_by(db.versions.c.number.desc())).mappings()]
                result.append({**dict(a), 'versions': versions})
            return result

    @app.get('/api/v1/templates')
    def template_list(user=Depends(current)): return templates()

    @app.get('/api/v1/versions/{vid}')
    def version(vid: int, user=Depends(current)):
        with engine.begin() as c:
            v = row(c, db.versions, vid)
            v['assets'] = list(asset_map(c, vid))
            v['preview_html'] = render(v['markdown'], v['template'], v['assets'], vid, template_css=v['template_css'])
            p = c.execute(select(db.publications).where(db.publications.c.version_id == vid)).mappings().first()
            v['publication'] = dict(p) if p else None
            return v

    @app.get('/api/v1/versions/{vid}/assets/{name:path}')
    def asset(vid: int, name: str, user=Depends(current)):
        with engine.begin() as c: a = asset_map(c, vid).get(name)
        if not a: raise HTTPException(404)
        return FileResponse(blobs / a['sha256'], media_type=a['mime'])

    @app.post('/api/v1/preview')
    def preview(body: Edit, user=Depends(current)):
        with engine.begin() as c: assets = asset_map(c, body.base_version_id)
        try: return {'html': render(body.markdown, body.template, assets, body.base_version_id)}
        except ValueError as e: raise HTTPException(422, str(e))

    @app.post('/api/v1/articles/{aid}/versions')
    def edit(aid: int, body: Edit, user=Depends(current)):
        with lock, engine.begin() as c:
            old = row(c, db.versions, body.base_version_id)
            if old['article_id'] != aid: raise HTTPException(409, '版本不属于此文章')
            try: return save_version(c, aid, body.title, body.markdown, body.template, old['cover'], asset_map(c, old['id']), user['username'])
            except ValueError as e: raise HTTPException(422, str(e))

    @app.post('/api/v1/versions/{vid}/assets')
    async def add_asset(vid: int, file: UploadFile = File(...), user=Depends(current)):
        content = await file.read(2_000_001)
        if len(content) > 2_000_000: raise HTTPException(413)
        try:
            name = asset_path(file.filename)
            with Image.open(io.BytesIO(content)) as im:
                if im.format not in ('JPEG','PNG') or im.width*im.height > 40_000_000: raise ValueError()
                mime = Image.MIME[im.format]; im.verify()
        except Exception: raise HTTPException(422, '需要有效JPEG/PNG图片和相对文件名')
        with lock, engine.begin() as c:
            old = row(c, db.versions, vid)
            if name != old['cover'] and len(content) > 1_000_000: raise HTTPException(413, '正文图最大1MB')
            sha = hashlib.sha256(content).hexdigest(); (blobs / sha).write_bytes(content)
            amap = asset_map(c, vid); amap[name] = {'sha256':sha,'mime':mime}
            return {**save_version(c, old['article_id'], old['title'], old['markdown'], old['template'], old['cover'], amap, user['username']), 'path':name}

    def publication(c, vid):
        p = c.execute(select(db.publications).where(db.publications.c.version_id == vid)).mappings().first()
        if not p: raise HTTPException(409, '请先发送微信草稿')
        return dict(p)

    @app.post('/api/v1/versions/{vid}/draft')
    def draft(vid: int, user=Depends(current)):
        if not cfg['wechat']['enable_draft']: raise HTTPException(403, '草稿功能已关闭')
        with lock, engine.begin() as c:
            v = row(c, db.versions, vid); amap = asset_map(c, vid)
            prior = c.execute(select(db.publications).where(db.publications.c.version_id == vid)).mappings().first()
            if prior: raise HTTPException(409, '此版本已处理；请查询草稿或创建新版本。结果不确定时先核对微信后台')
            pid = c.execute(insert(db.publications).values(version_id=vid, status='drafting', created_at=time.time(), updated_at=time.time())).inserted_primary_key[0]
        w = app.state.wechat
        try:
            urls = {}
            for name in image_refs(v['markdown']):
                a = amap[name]; urls[name] = w.upload((blobs/a['sha256']).read_bytes(), Path(name).name, a['mime'])
                if not urls[name].startswith(('https://mmbiz.qpic.cn/', 'http://mmbiz.qpic.cn/', 'https://mmbiz.qlogo.cn/')):
                    raise WeChatError('微信图片地址不符合预期')
            cover = amap[v['cover']]
            media = w.upload((blobs/cover['sha256']).read_bytes(), Path(v['cover']).name, cover['mime'], cover=True)
            html = render(v['markdown'], v['template'], amap, vid, urls, template_css=v['template_css'])
            with engine.begin() as c:
                c.execute(update(db.publications).where(db.publications.c.id == pid).values(html_sent=html))
            result = w.call('draft/add', {'articles':[{'title':v['title'], 'content':html, 'thumb_media_id':media, 'need_open_comment':0, 'only_fans_can_comment':0}]})
            media_id = result['media_id']
            with engine.begin() as c:
                c.execute(update(db.publications).where(db.publications.c.id == pid).values(status='draft', draft_media_id=media_id, updated_at=time.time()))
                log(c, user['username'], 'draft_created', vid)
        except Exception as e:
            with engine.begin() as c:
                c.execute(update(db.publications).where(db.publications.c.id == pid).values(status='draft_unknown', result=json.dumps({'error': str(e) if isinstance(e, WeChatError) else '草稿结果不确定，请核对微信后台'})))
            raise HTTPException(502, str(e) if isinstance(e, WeChatError) else '草稿结果不确定，请核对微信后台')
        return refresh_draft(vid, user)

    @app.post('/api/v1/versions/{vid}/draft/check')
    def refresh_draft(vid: int, user=Depends(current)):
        with engine.begin() as c: p = publication(c, vid)
        if not p['draft_media_id']: raise HTTPException(409, '没有已确认的草稿ID；请核对微信后台')
        try: result = app.state.wechat.call('draft/get', {'media_id':p['draft_media_id']})
        except WeChatError as e: raise HTTPException(502, str(e))
        html = result['news_item'][0]['content']
        with engine.begin() as c:
            c.execute(update(db.publications).where(db.publications.c.id == p['id']).values(html_returned=html, updated_at=time.time()))
        return {'draft_media_id':p['draft_media_id'], 'html_changed':html != p['html_sent']}

    @app.post('/api/v1/versions/{vid}/publish')
    def publish(vid: int, body: PublishInput, user=Depends(admin)):
        if not cfg['wechat']['enable_publish']: raise HTTPException(403, '正式发布已关闭')
        if body.confirm_version_id != vid: raise HTTPException(409, '确认版本不一致')
        with lock, engine.begin() as c:
            p = publication(c, vid)
            if p['status'] != 'draft' or not p['html_returned']: raise HTTPException(409, '仅允许发布已取回校验的草稿')
            c.execute(update(db.publications).where(db.publications.c.id == p['id']).values(status='submitting', updated_at=time.time()))
        try:
            r = app.state.wechat.call('freepublish/submit', {'media_id':p['draft_media_id']})
            publish_id = r['publish_id']
        except Exception as e:
            with engine.begin() as c:
                c.execute(update(db.publications).where(db.publications.c.id == p['id']).values(status='publish_unknown'))
            raise HTTPException(502, str(e) if isinstance(e, WeChatError) else '发布结果不确定，请核对微信后台；已阻止重复提交')
        with engine.begin() as c:
            c.execute(update(db.publications).where(db.publications.c.id == p['id']).values(status='publishing', publish_id=publish_id, updated_at=time.time()))
            log(c, user['username'], 'publish_submitted', vid)
        return {'publish_id':publish_id, 'status':'publishing'}

    @app.post('/api/v1/versions/{vid}/publish/check')
    def publish_check(vid: int, user=Depends(current)):
        with engine.begin() as c: p = publication(c, vid)
        if not p['publish_id']: raise HTTPException(409, '没有发布任务ID')
        try: r = app.state.wechat.call('freepublish/get', {'publish_id':p['publish_id']})
        except WeChatError as e: raise HTTPException(502, str(e))
        code = r.get('publish_status')
        status = 'published' if code == 0 else 'publishing' if code == 1 else 'publish_failed'
        with engine.begin() as c:
            c.execute(update(db.publications).where(db.publications.c.id == p['id']).values(status=status, result=json.dumps(r, ensure_ascii=False), updated_at=time.time()))
        return {'status':status, 'result':r}

    @app.get('/api/v1/admin')
    def management(user=Depends(admin)):
        with engine.begin() as c:
            return {'users':[dict(r) for r in c.execute(select(db.users.c.id,db.users.c.username,db.users.c.role,db.users.c.status)).mappings()],
                'tokens':[dict(r) for r in c.execute(select(db.tokens.c.id,db.tokens.c.name,db.tokens.c.prefix,db.tokens.c.scope,db.tokens.c.expires_at,db.tokens.c.last_used_at,db.tokens.c.revoked_at)).mappings()],
                'logs':[dict(r) for r in c.execute(select(db.audit).order_by(db.audit.c.id.desc()).limit(100)).mappings()],
                'wechat':{'app_id':os.getenv('WECHAT_APP_ID',''), 'secret_configured':bool(os.getenv('WECHAT_APP_SECRET')), 'publish_enabled':cfg['wechat']['enable_publish']}}

    @app.post('/api/v1/admin/users')
    def add_user(body: UserInput, user=Depends(admin)):
        if body.role not in ('ADMIN','EDITOR') or len(body.password) < 12: raise HTTPException(422, '密码至少12字符；角色为ADMIN或EDITOR')
        with lock, engine.begin() as c:
            if c.execute(select(db.users.c.id).where(db.users.c.username == body.username)).first(): raise HTTPException(409, '用户名已存在')
            uid = c.execute(insert(db.users).values(username=body.username,password_hash=password_hasher.hash(body.password),role=body.role,status='active',created_at=time.time())).inserted_primary_key[0]
            log(c,user['username'],'user_created',uid)
        return {'id':uid}

    @app.post('/api/v1/admin/users/{uid}/status')
    def set_user_status(uid:int, body:StatusInput, user=Depends(admin)):
        if uid == user['id'] or body.status not in ('active','disabled'): raise HTTPException(422, '不能修改自身状态或状态无效')
        with lock, engine.begin() as c:
            row(c,db.users,uid)
            c.execute(update(db.users).where(db.users.c.id==uid).values(status=body.status))
            c.execute(delete(db.sessions).where(db.sessions.c.user_id==uid))
            log(c,user['username'],'user_status',f'{uid}:{body.status}')
        return {'ok':True}

    @app.delete('/api/v1/admin/users/{uid}')
    def delete_user(uid:int,user=Depends(admin)):
        if uid==user['id']: raise HTTPException(422,'不能删除自己')
        with lock, engine.begin() as c:
            row(c,db.users,uid)
            c.execute(delete(db.sessions).where(db.sessions.c.user_id==uid))
            c.execute(delete(db.users).where(db.users.c.id==uid)); log(c,user['username'],'user_deleted',uid)
        return {'ok':True}

    @app.post('/api/v1/admin/tokens')
    def add_token(body:TokenInput,user=Depends(admin)):
        token='pub_'+secrets.token_urlsafe(32)
        with engine.begin() as c:
            c.execute(insert(db.tokens).values(name=body.name,prefix=token[:10],token_hash=digest(token),scope='article:ingest',created_at=time.time(),expires_at=time.time()+body.days*86400))
            log(c,user['username'],'token_created',body.name)
        return {'token':token, 'notice':'仅此一次显示，请保存到GitHub Secret'}

    @app.delete('/api/v1/admin/tokens/{tid}')
    def revoke_token(tid:int,user=Depends(admin)):
        with engine.begin() as c:
            row(c,db.tokens,tid)
            c.execute(update(db.tokens).where(db.tokens.c.id==tid).values(revoked_at=time.time()))
            log(c,user['username'],'token_revoked',tid)
        return {'ok':True}

    dist=ROOT/'frontend/dist'
    if dist.exists():
        app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app
