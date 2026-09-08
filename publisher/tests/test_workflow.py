import io
import json
import time
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from publisher.backend import db
from publisher.backend.content import build_package, read_package, image_refs
from publisher.backend.main import create_app, password_hasher
from publisher.backend.render import render
from publisher.backend.wechat import WeChat, WeChatError

class FakeWeChat:
    def __init__(self): self.calls=[]; self.html=''; self.fail_publish=False
    def upload(self, data, filename, mime, cover=False):
        self.calls.append(('cover' if cover else 'image',filename))
        return 'cover-1' if cover else 'https://mmbiz.qpic.cn/'+filename
    def call(self, endpoint, payload):
        self.calls.append((endpoint,payload))
        if endpoint=='draft/add': self.html=payload['articles'][0]['content']; return {'media_id':'draft-1'}
        if endpoint=='draft/get': return {'news_item':[{'content':self.html}]}
        if endpoint=='freepublish/submit':
            if self.fail_publish: raise WeChatError('timeout')
            return {'publish_id':'publish-1'}
        if endpoint=='freepublish/get': return {'publish_status':0,'article_detail':{'item':[{'article_url':'https://mp.weixin.qq.com/s/example'}]}}
        raise AssertionError(endpoint)

@pytest.fixture
def env(tmp_path):
    fake=FakeWeChat(); app=create_app(tmp_path/'data',testing=True,wechat=fake)
    with app.state.engine.begin() as c:
        for username,role in [('admin','ADMIN'),('editor','EDITOR')]:
            c.execute(insert(db.users).values(username=username,password_hash=password_hasher.hash('test-password-123'),role=role,status='active',created_at=time.time()))
    client=TestClient(app,headers={'origin':'http://testserver'})
    login=client.post('/api/v1/login',json={'username':'admin','password':'test-password-123'})
    assert login.status_code==200
    client.headers['x-csrf-token']=login.json()['csrf']
    token=client.post('/api/v1/admin/tokens',json={'name':'ci'}).json()['token']
    package=build_package('inputs/wechat/acceptance',tmp_path/'article.zip','testcommit').read_bytes()
    def ingest(content=package,secret=token):
        return client.post('/api/v1/ingest',headers={'authorization':'Bearer '+secret},files={'package':('article.zip',content,'application/zip')})
    yield app,client,fake,ingest,token,package
    client.close(); app.state.engine.dispose()

def test_full_version_draft_publish_and_idempotency(env):
    app,c,w,ingest,token,package=env
    first=ingest(); assert first.status_code==200,first.text
    vid=first.json()['version_id']; aid=first.json()['article_id']
    assert ingest().json()['duplicate'] is True
    v1=c.get(f'/api/v1/versions/{vid}').json()
    body={'title':'新标题','markdown':v1['markdown']+'\n新内容','template':'tech','base_version_id':vid}
    changed=c.post(f'/api/v1/articles/{aid}/versions',json=body)
    assert changed.status_code==200,changed.text
    vid2=changed.json()['version_id']; assert changed.json()['number']==2
    assert c.get(f'/api/v1/versions/{vid}').json()['markdown']==v1['markdown']
    # Publishing older version stays explicitly bound to that version.
    draft=c.post(f'/api/v1/versions/{vid}/draft'); assert draft.status_code==200,draft.text
    assert w.html.count('https://mmbiz.qpic.cn/')==3
    assert '/api/v1/versions/' not in w.html and '<style' not in w.html
    assert c.post(f'/api/v1/versions/{vid}/draft').status_code==409
    assert c.post(f'/api/v1/versions/{vid}/publish',json={'confirm_version_id':vid2}).status_code==409
    assert c.post(f'/api/v1/versions/{vid}/publish',json={'confirm_version_id':vid}).json()['status']=='publishing'
    assert c.post(f'/api/v1/versions/{vid}/publish',json={'confirm_version_id':vid}).status_code==409
    assert c.post(f'/api/v1/versions/{vid}/publish/check').json()['status']=='published'
    assert c.get(f'/api/v1/versions/{vid2}').json()['publication'] is None

def test_auth_scope_csrf_revocation_and_disabled_user(env):
    app,c,w,ingest,token,package=env
    assert ingest(secret='bad').status_code==401
    assert c.post('/api/v1/admin/tokens',json={'name':'bad'},headers={'origin':'https://evil.example'}).status_code==403
    assert c.post('/api/v1/admin/tokens',json={'name':'bad'},headers={'x-csrf-token':'bad'}).status_code==403
    c2=TestClient(app,headers={'origin':'http://testserver','authorization':'Bearer '+token})
    assert c2.get('/api/v1/articles').status_code==401
    assert c2.post('/api/v1/versions/1/publish',json={'confirm_version_id':1}).status_code==401
    editor=c2.post('/api/v1/login',json={'username':'editor','password':'test-password-123'}).json()
    c2.headers['x-csrf-token']=editor['csrf']
    assert c2.get('/api/v1/admin').status_code==403
    assert c2.post('/api/v1/versions/1/publish',json={'confirm_version_id':1}).status_code==403
    assert c.post('/api/v1/admin/users/2/status',json={'status':'disabled'}).status_code==200
    assert c2.get('/api/v1/articles').status_code==401
    assert c.delete('/api/v1/admin/tokens/1').status_code==200
    assert ingest().status_code==401
    with app.state.engine.begin() as conn:
        stored=conn.execute(select(db.tokens)).mappings().first()
        assert stored['token_hash'] != token and token not in str(stored)
    c2.close()

def test_untrusted_packages_and_markdown(env):
    app,c,w,ingest,token,package=env
    with zipfile.ZipFile(io.BytesIO(package)) as z: files={n:z.read(n) for n in z.namelist()}
    def zipped(changes):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for n,v in {**files,**changes}.items(): z.writestr(n,v)
        return out.getvalue()
    for bad in ('../escape.png','/tmp/escape.png','images/../../escape.png','images/%2e%2e/escape.png'):
        assert ingest(zipped({bad:b'bad'})).status_code==422
    assert ingest(zipped({'article.md':b'![x](https://127.0.0.1/secret)'})).status_code==422
    assert ingest(zipped({'article.md':b'![x](images/missing.png)'})).status_code==422
    assert ingest(zipped({'images/landscape.png':b'not an image'})).status_code==422
    with pytest.raises(ValueError): read_package(package,max_unpacked=10)
    # Raw HTML is text, not an executable image/script.
    html=render('<script>alert(1)</script>\n\n[x](javascript:alert(1))','clean',{})
    assert '<script>' not in html and 'href="javascript:' not in html
    assert image_refs('![x][img]\n\n[img]: ./images/photo.png')==['images/photo.png']

def test_publish_uncertain_never_retries(env):
    app,c,w,ingest,token,package=env
    vid=ingest().json()['version_id']
    assert c.post(f'/api/v1/versions/{vid}/draft').status_code==200
    w.fail_publish=True
    assert c.post(f'/api/v1/versions/{vid}/publish',json={'confirm_version_id':vid}).status_code==502
    assert c.post(f'/api/v1/versions/{vid}/publish',json={'confirm_version_id':vid}).status_code==409
    assert len([x for x in w.calls if x[0]=='freepublish/submit'])==1

def test_template_switch_and_missing_asset(env):
    app,c,w,ingest,token,package=env
    vid=ingest().json()['version_id'];v=c.get(f'/api/v1/versions/{vid}').json()
    outputs=[]
    for theme in ('clean','business','tech'):
        r=c.post('/api/v1/preview',json={'title':v['title'],'markdown':v['markdown'],'template':theme,'base_version_id':vid})
        assert r.status_code==200,r.text
        outputs.append(r.json()['html'])
        assert r.json()['html'].index('landscape.png')<r.json()['html'].index('portrait.png')<r.json()['html'].index('tall.png')
    assert len(set(outputs))==3
    assert c.post('/api/v1/preview',json={'title':'x','markdown':'![x](missing.png)','template':'clean','base_version_id':vid}).status_code==422
    assert c.get(f'/api/v1/versions/{vid}/assets/images/portrait.png').headers['content-type']=='image/png'

def test_wechat_http_contract_and_token_cache():
    calls=[]
    def handler(r):
        calls.append(r)
        if r.url.path.endswith('stable_token'): return httpx.Response(200,json={'access_token':'secret-test-token','expires_in':7200})
        if r.url.path.endswith('uploadimg'): return httpx.Response(200,json={'url':'https://mmbiz.qpic.cn/image'})
        return httpx.Response(200,json={'errcode':40013,'errmsg':'invalid appid'})
    client=httpx.Client(transport=httpx.MockTransport(handler))
    w=WeChat('appid','appsecret',client)
    assert w.upload(b'bytes','image.png','image/png').startswith('https://mmbiz.qpic.cn/')
    with pytest.raises(WeChatError,match='40013'): w.call('draft/add',{'articles':[]})
    assert len([r for r in calls if r.url.path.endswith('stable_token')])==1
    assert calls[1].url.params['access_token']=='secret-test-token'
