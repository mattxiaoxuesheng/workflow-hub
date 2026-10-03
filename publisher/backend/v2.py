"""V2 working drafts, immutable snapshots, assets and reviewed WeChat payloads."""

import difflib
import hashlib
import io
import json
import secrets
import time
from pathlib import Path
from urllib.parse import quote
import cssutils
from bs4 import BeautifulSoup
from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import select, insert, update, func
from . import db
from .content import read_package
from .richtext import EMPTY, from_markdown, validate_doc, render_doc, css_for
from .wechat import WeChatError
from .images import publication_image, LIMITS
from .shared_assets import install_shared_assets, read_upload, ensure_shared


class ArticleInput(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    template: str = "clean"


class DraftInput(ArticleInput):
    content_json: dict
    revision: int = Field(ge=1)
    cover: str | None = None


class Revision(BaseModel):
    revision: int = Field(ge=1)


class Confirmation(BaseModel):
    html_hash: str


class MarkdownInput(ArticleInput):
    markdown: str = Field(max_length=500_000)


def install(app, engine, blobs, lock, cfg, current, row, log, asset_map):
    def libmap(c, aid):
        return {
            r["path"]: dict(r)
            for r in c.execute(
                select(db.library).where(
                    db.library.c.article_id == aid, db.library.c.deleted_at.is_(None)
                )
            ).mappings()
        }

    def register_asset(c, aid, sha, mime, content=None):
        ensure_shared(
            c, sha, mime, len(content) if content else (blobs / sha).stat().st_size
        )
        suffix = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
        name = f"uploads/{sha}.{suffix}"
        old = (
            c.execute(
                select(db.library).where(
                    db.library.c.article_id == aid, db.library.c.path == name
                )
            )
            .mappings()
            .first()
        )
        if not old:
            c.execute(
                insert(db.library).values(
                    article_id=aid,
                    path=name,
                    sha256=sha,
                    mime=mime,
                    size=len(content) if content else (blobs / sha).stat().st_size,
                    created_at=time.time(),
                )
            )
        elif old["deleted_at"]:
            c.execute(
                update(db.library)
                .where(db.library.c.id == old["id"])
                .values(deleted_at=None)
            )
        return name

    def normalize_version(c, v):
        if not v["content_json"]:
            mapping = {}
            for name, a in asset_map(c, v["id"]).items():
                canonical = register_asset(c, v["article_id"], a["sha256"], a["mime"])
                mapping[name] = canonical
                if (
                    canonical != name
                    and not c.execute(
                        select(db.assets.c.id).where(
                            db.assets.c.version_id == v["id"],
                            db.assets.c.path == canonical,
                        )
                    ).first()
                ):
                    c.execute(
                        insert(db.assets).values(
                            version_id=v["id"],
                            path=canonical,
                            sha256=a["sha256"],
                            mime=a["mime"],
                        )
                    )
            doc = from_markdown(v["markdown"] or "", mapping)
            rendered = render_doc(
                doc,
                v["template"],
                asset_map(c, v["id"]),
                version_id=v["id"],
                template_css=v["template_css"],
            )
            c.execute(
                update(db.versions)
                .where(db.versions.c.id == v["id"])
                .values(
                    content_json=json.dumps(doc, ensure_ascii=False),
                    rendered_html=rendered,
                )
            )
            v = {
                **v,
                "content_json": json.dumps(doc, ensure_ascii=False),
                "rendered_html": rendered,
            }
        return v

    def draft_row(c, aid):
        row(c, db.articles, aid)
        d = (
            c.execute(select(db.drafts).where(db.drafts.c.article_id == aid))
            .mappings()
            .first()
        )
        if not d:
            v = (
                c.execute(
                    select(db.versions)
                    .where(db.versions.c.article_id == aid)
                    .order_by(db.versions.c.number.desc())
                )
                .mappings()
                .first()
            )
            if v:
                v = normalize_version(c, dict(v))
                cover = v["cover"]
                amap = asset_map(c, v["id"])
                if cover in amap:
                    cover = register_asset(
                        c, aid, amap[cover]["sha256"], amap[cover]["mime"]
                    )
                values = dict(
                    base_version_id=v["id"],
                    title=v["title"],
                    content_json=v["content_json"],
                    template=v["template"],
                    cover=cover,
                )
            else:
                a = row(c, db.articles, aid)
                values = dict(
                    base_version_id=None,
                    title=a["title"],
                    content_json=json.dumps(EMPTY),
                    template="clean",
                    cover=None,
                )
            c.execute(
                insert(db.drafts).values(
                    article_id=aid,
                    revision=1,
                    updated_at=time.time(),
                    updated_by="migration",
                    follow_latest=True,
                    **values,
                )
            )
            d = (
                c.execute(select(db.drafts).where(db.drafts.c.article_id == aid))
                .mappings()
                .one()
            )
        return dict(d)

    def serialize(d):
        return {**d, "content_json": json.loads(d["content_json"])}

    def conflict(d, revision):
        if d["revision"] != revision:
            raise HTTPException(
                409, "工作稿已被其他窗口修改，请重新打开文章；本地修改仍保留"
            )

    def validated(doc, theme, amap, cover=None):
        try:
            css_for(theme)
            validate_doc(doc, amap)
            if cover and cover not in amap:
                raise ValueError("封面图片不存在")
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            raise HTTPException(422, str(e)) from e

    @app.get("/api/v2/templates")
    def template_list(user=Depends(current)):
        from .render import templates

        result = []
        for name in ["none", *templates()]:
            css = css_for(name)
            sheet = cssutils.parseString(css)
            for rule in sheet:
                if rule.type == rule.STYLE_RULE:
                    rule.selectorText = ", ".join(
                        (
                            ".tiptap.article"
                            if s.strip() == ".article"
                            else ".tiptap.article " + s.strip()
                        )
                        for s in rule.selectorText.split(",")
                    )
            result.append({"id": name, "css": sheet.cssText.decode()})
        return result

    @app.post("/api/v2/articles")
    def create_article(body: ArticleInput, user=Depends(current)):
        validated(EMPTY, body.template, {})
        with lock, engine.begin() as c:
            aid = c.execute(
                insert(db.articles).values(
                    slug="article-" + secrets.token_hex(8),
                    title=body.title,
                    created_at=time.time(),
                    updated_at=time.time(),
                )
            ).inserted_primary_key[0]
            c.execute(
                insert(db.drafts).values(
                    article_id=aid,
                    title=body.title,
                    content_json=json.dumps(EMPTY),
                    follow_latest=True,
                    template=body.template,
                    revision=1,
                    updated_at=time.time(),
                    updated_by=user["username"],
                )
            )
            log(c, user["username"], "article_created", aid)
        return {"article_id": aid}

    @app.get("/api/v2/articles/{aid}/draft")
    def get_draft(aid: int, user=Depends(current)):
        with lock, engine.begin() as c:
            d = draft_row(c, aid)
            latest = (
                c.execute(
                    select(db.versions)
                    .where(db.versions.c.article_id == aid)
                    .order_by(db.versions.c.number.desc())
                )
                .mappings()
                .first()
            )
            if (
                latest
                and latest["id"] != d["base_version_id"]
                and d["base_version_id"]
                and d["follow_latest"]
            ):
                baseline = normalize_version(
                    c, row(c, db.versions, d["base_version_id"])
                )
                old_assets = asset_map(c, baseline["id"])
                baseline_cover = baseline["cover"]
                if baseline_cover in old_assets:
                    a = old_assets[baseline_cover]
                    baseline_cover = register_asset(c, aid, a["sha256"], a["mime"])
                clean = (
                    d["title"] == baseline["title"]
                    and d["template"] == baseline["template"]
                    and d["cover"] == baseline_cover
                    and json.loads(d["content_json"])
                    == json.loads(baseline["content_json"])
                )
                if clean:
                    latest = normalize_version(c, dict(latest))
                    amap = asset_map(c, latest["id"])
                    cover = latest["cover"]
                    if cover in amap:
                        a = amap[cover]
                        cover = register_asset(c, aid, a["sha256"], a["mime"])
                    values = dict(
                        title=latest["title"],
                        template=latest["template"],
                        cover=cover,
                        content_json=latest["content_json"],
                        base_version_id=latest["id"],
                        revision=d["revision"] + 1,
                        updated_at=time.time(),
                        updated_by="version_sync",
                    )
                    c.execute(
                        update(db.drafts)
                        .where(db.drafts.c.article_id == aid)
                        .values(**values)
                    )
                    d = {**d, **values}
            return {
                **serialize(d),
                "latest_version_id": latest["id"] if latest else None,
                "latest_version_number": latest["number"] if latest else None,
                "has_newer_version": bool(
                    latest and latest["id"] != d["base_version_id"]
                ),
            }

    @app.put("/api/v2/articles/{aid}/draft")
    def save_draft(aid: int, body: DraftInput, user=Depends(current)):
        with lock, engine.begin() as c:
            d = draft_row(c, aid)
            conflict(d, body.revision)
            validated(body.content_json, body.template, libmap(c, aid), body.cover)
            values = dict(
                title=body.title,
                template=body.template,
                content_json=json.dumps(body.content_json, ensure_ascii=False),
                cover=body.cover,
                revision=d["revision"] + 1,
                updated_at=time.time(),
                updated_by=user["username"],
            )
            c.execute(
                update(db.drafts).where(db.drafts.c.article_id == aid).values(**values)
            )
            c.execute(
                update(db.articles)
                .where(db.articles.c.id == aid)
                .values(title=body.title, updated_at=time.time())
            )
            return serialize({**d, **values})

    @app.post("/api/v2/articles/{aid}/versions")
    def snapshot(aid: int, body: Revision, user=Depends(current)):
        with lock, engine.begin() as c:
            d = draft_row(c, aid)
            conflict(d, body.revision)
            doc = json.loads(d["content_json"])
            amap = libmap(c, aid)
            validated(doc, d["template"], amap, d["cover"])
            refs = validate_doc(doc, amap)
            css = css_for(d["template"])
            n = (
                c.execute(
                    select(func.coalesce(func.max(db.versions.c.number), 0)).where(
                        db.versions.c.article_id == aid
                    )
                ).scalar_one()
                + 1
            )
            vid = c.execute(
                insert(db.versions).values(
                    article_id=aid,
                    number=n,
                    title=d["title"],
                    markdown="",
                    content_json=d["content_json"],
                    template=d["template"],
                    template_css=css,
                    cover=d["cover"],
                    created_by=user["username"],
                    created_at=time.time(),
                )
            ).inserted_primary_key[0]
            for name in set(refs + ([d["cover"]] if d["cover"] else [])):
                a = amap[name]
                c.execute(
                    insert(db.assets).values(
                        version_id=vid, path=name, sha256=a["sha256"], mime=a["mime"]
                    )
                )
            rendered = render_doc(
                doc, d["template"], amap, version_id=vid, template_css=css
            )
            c.execute(
                update(db.versions)
                .where(db.versions.c.id == vid)
                .values(rendered_html=rendered)
            )
            c.execute(
                update(db.drafts)
                .where(db.drafts.c.article_id == aid)
                .values(
                    base_version_id=vid,
                    follow_latest=True,
                    revision=d["revision"] + 1,
                    updated_at=time.time(),
                )
            )
            log(c, user["username"], "version_created", vid)
        return {
            "article_id": aid,
            "version_id": vid,
            "number": n,
            "revision": d["revision"] + 1,
            "updated_at": time.time(),
        }

    @app.post("/api/v2/articles/{aid}/restore/{vid}")
    def restore(aid: int, vid: int, body: Revision, user=Depends(current)):
        with lock, engine.begin() as c:
            d = draft_row(c, aid)
            conflict(d, body.revision)
            v = normalize_version(c, row(c, db.versions, vid))
            if v["article_id"] != aid:
                raise HTTPException(409, "版本不属于此文章")
            mapping = {
                name: register_asset(c, aid, a["sha256"], a["mime"])
                for name, a in asset_map(c, vid).items()
            }
            doc = json.loads(v["content_json"])

            def rewrite(node):
                if node["type"] == "image":
                    node["attrs"]["src"] = mapping[node["attrs"]["src"]]
                for child in node.get("content", []):
                    rewrite(child)

            rewrite(doc)
            values = dict(
                base_version_id=vid,
                follow_latest=vid
                == c.execute(
                    select(db.versions.c.id)
                    .where(db.versions.c.article_id == aid)
                    .order_by(db.versions.c.number.desc())
                    .limit(1)
                ).scalar_one(),
                title=v["title"],
                content_json=json.dumps(doc, ensure_ascii=False),
                template=v["template"],
                cover=mapping.get(v["cover"]),
                revision=d["revision"] + 1,
                updated_at=time.time(),
                updated_by=user["username"],
            )
            c.execute(
                update(db.drafts).where(db.drafts.c.article_id == aid).values(**values)
            )
            log(c, user["username"], "version_restored", vid)
            c.execute(
                update(db.articles)
                .where(db.articles.c.id == aid)
                .values(title=v["title"], updated_at=time.time())
            )
            return serialize({**d, **values})

    def image_info(a, name, root):
        result = {}
        for role in LIMITS:
            _, info = publication_image(blobs, a["sha256"], role)
            result[role] = {
                **info,
                "url": f"{root}/publication-image/{role}/{quote(name, safe='/')}",
            }
        return result

    def asset_details(a, aid):
        return {
            **a,
            "publication_images": image_info(a, a["path"], f"/api/v2/articles/{aid}"),
        }

    @app.get("/api/v2/articles/{aid}/publication-image/{role}/{name:path}")
    def serve_article_copy(aid: int, role: str, name: str, user=Depends(current)):
        with engine.begin() as c:
            a = libmap(c, aid).get(name)
        if not a or role not in LIMITS:
            raise HTTPException(404, "图片不存在")
        path, info = publication_image(blobs, a["sha256"], role)
        return FileResponse(path, media_type=info["mime"])

    @app.get("/api/v2/versions/{vid}/publication-image/{role}/{name:path}")
    def serve_version_copy(vid: int, role: str, name: str, user=Depends(current)):
        with engine.begin() as c:
            a = asset_map(c, vid).get(name)
        if not a or role not in LIMITS:
            raise HTTPException(404, "图片不存在")
        path, info = publication_image(blobs, a["sha256"], role)
        return FileResponse(path, media_type=info["mime"])

    @app.get("/api/v2/articles/{aid}/assets")
    def list_assets(aid: int, user=Depends(current)):
        with engine.begin() as c:
            row(c, db.articles, aid)
            return [asset_details(a, aid) for a in libmap(c, aid).values()]

    @app.post("/api/v2/articles/{aid}/assets")
    async def upload(aid: int, file: UploadFile = File(...), user=Depends(current)):
        content, mime = await read_upload(file)
        sha = hashlib.sha256(content).hexdigest()
        with lock, engine.begin() as c:
            row(c, db.articles, aid)
            dest = blobs / sha
            if not dest.exists():
                tmp = blobs / (sha + "." + secrets.token_hex(6))
                tmp.write_bytes(content)
                tmp.replace(dest)
            name = register_asset(c, aid, sha, mime, content)
            ensure_shared(c, sha, mime, len(content), file.filename)
            log(c, user["username"], "asset_uploaded", name)
            return asset_details(libmap(c, aid)[name], aid)

    @app.get("/api/v2/articles/{aid}/assets/{name:path}")
    def serve(aid: int, name: str, user=Depends(current)):
        with engine.begin() as c:
            a = libmap(c, aid).get(name)
        if not a:
            raise HTTPException(404, "图片不存在")
        return FileResponse(blobs / a["sha256"], media_type=a["mime"])

    @app.delete("/api/v2/articles/{aid}/assets/{asset_id}")
    def remove_asset(aid: int, asset_id: int, user=Depends(current)):
        with lock, engine.begin() as c:
            a = row(c, db.library, asset_id)
            if a["article_id"] != aid:
                raise HTTPException(404)
            d = draft_row(c, aid)
            refs = validate_doc(json.loads(d["content_json"]), libmap(c, aid))
            used = c.execute(
                select(db.assets.c.id)
                .join(db.versions)
                .where(
                    db.versions.c.article_id == aid, db.assets.c.sha256 == a["sha256"]
                )
            ).first()
            if a["path"] in refs or a["path"] == d["cover"] or used:
                raise HTTPException(409, "工作稿或历史版本仍引用此图片，不能永久删除")
            c.execute(
                update(db.library)
                .where(db.library.c.id == asset_id)
                .values(deleted_at=time.time())
            )
            # Shared content-addressed blobs are removed only when no article/version references them.
            live = c.execute(
                select(db.library.c.id).where(
                    db.library.c.sha256 == a["sha256"],
                    db.library.c.deleted_at.is_(None),
                )
            ).first()
            frozen = c.execute(
                select(db.assets.c.id).where(db.assets.c.sha256 == a["sha256"])
            ).first()
            shared = c.execute(
                select(db.shared_assets.c.id).where(
                    db.shared_assets.c.sha256 == a["sha256"],
                    db.shared_assets.c.deleted_at.is_(None),
                )
            ).first()
            if not live and not frozen and not shared:
                (blobs / a["sha256"]).unlink(missing_ok=True)
            log(c, user["username"], "asset_deleted", asset_id)
        return {"ok": True}

    install_shared_assets(
        app,
        engine,
        blobs,
        lock,
        current,
        row,
        log,
        register_asset,
        image_info,
        asset_details,
    )

    @app.post("/api/v2/import/markdown")
    def import_markdown(body: MarkdownInput, user=Depends(current)):
        try:
            doc = from_markdown(body.markdown)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        validated(doc, body.template, {})
        aid = create_article(
            ArticleInput(title=body.title, template=body.template), user
        )["article_id"]
        with engine.begin() as c:
            c.execute(
                update(db.drafts)
                .where(db.drafts.c.article_id == aid)
                .values(content_json=json.dumps(doc, ensure_ascii=False))
            )
        return {"article_id": aid}

    @app.post("/api/v2/import/package")
    async def import_package(file: UploadFile = File(...), user=Depends(current)):
        limit = int(cfg["article"]["max_upload_mb"] * 1024**2)
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise HTTPException(413, "内容包过大")
        try:
            manifest, files, markdown, refs, cover, _ = read_package(
                content,
                int(cfg["article"]["max_unpacked_mb"] * 1024**2),
                cfg["article"]["max_files"],
            )
        except Exception as e:
            raise HTTPException(422, "内容包校验失败：" + str(e)[:200]) from e
        with lock, engine.begin() as c:
            aid = c.execute(
                insert(db.articles).values(
                    slug="import-" + secrets.token_hex(8),
                    title=manifest["title"],
                    created_at=time.time(),
                    updated_at=time.time(),
                )
            ).inserted_primary_key[0]
            mapping = {}
            for name in set(refs + [cover]):
                sha = hashlib.sha256(files[name]).hexdigest()
                with Image.open(io.BytesIO(files[name])) as im:
                    mime = Image.MIME[im.format]
                (blobs / sha).write_bytes(files[name])
                mapping[name] = register_asset(c, aid, sha, mime, files[name])
            doc = from_markdown(markdown, mapping)
            validated(doc, "clean", libmap(c, aid), mapping[cover])
            c.execute(
                insert(db.drafts).values(
                    article_id=aid,
                    title=manifest["title"],
                    template="clean",
                    follow_latest=True,
                    content_json=json.dumps(doc, ensure_ascii=False),
                    cover=mapping[cover],
                    revision=1,
                    updated_at=time.time(),
                    updated_by=user["username"],
                )
            )
            log(c, user["username"], "package_imported", aid)
        return {"article_id": aid}

    @app.post("/api/v2/versions/{vid}/prepare")
    def prepare(vid: int, user=Depends(current)):
        if not cfg["wechat"]["enable_draft"]:
            raise HTTPException(403, "草稿功能已关闭")
        with lock, engine.begin() as c:
            v = normalize_version(c, row(c, db.versions, vid))
            amap = asset_map(c, vid)
            if not v["cover"] or v["cover"] not in amap:
                raise HTTPException(422, "请先选择封面并保存为版本")
            p = (
                c.execute(
                    select(db.publications).where(db.publications.c.version_id == vid)
                )
                .mappings()
                .first()
            )
            if p and p["status"] == "prepared":
                return {
                    "html": p["html_sent"],
                    "html_hash": p["html_hash"],
                    "version_id": vid,
                    "images": json.loads(p["prepared_images"] or "[]"),
                    "compression_notice": (
                        ""
                        if p["prepared_images"]
                        else "此预览在自动压缩功能上线前已生成，保留原发送内容；如需自动压缩请保存新版本。"
                    ),
                }
            if p and p["status"] != "prepare_failed":
                raise HTTPException(409, "此版本已处理，请查看微信草稿或保存新版本")
            values = dict(status="preparing", updated_at=time.time())
            if p:
                pid = p["id"]
                c.execute(
                    update(db.publications)
                    .where(db.publications.c.id == pid)
                    .values(**values)
                )
            else:
                pid = c.execute(
                    insert(db.publications).values(
                        version_id=vid, created_at=time.time(), **values
                    )
                ).inserted_primary_key[0]
        try:
            doc = json.loads(v["content_json"])
            names = validate_doc(doc, amap)
            images = []
            for name, role in [(n, "body") for n in names] + [(v["cover"], "cover")]:
                info = image_info(amap[name], name, f"/api/v2/versions/{vid}")[role]
                images.append(
                    {
                        **info,
                        "name": name,
                        "original_url": f"/api/v1/versions/{vid}/assets/{quote(name, safe='/')}",
                    }
                )
            urls = {}
            w = app.state.wechat
            for name in validate_doc(doc, amap):
                a = amap[name]
                path, info = publication_image(blobs, a["sha256"], "body")
                suffix = ".png" if info["mime"] == "image/png" else ".jpg"
                urls[name] = w.upload(
                    path.read_bytes(), Path(name).stem + suffix, info["mime"]
                )
                if not urls[name].startswith(
                    (
                        "https://mmbiz.qpic.cn/",
                        "http://mmbiz.qpic.cn/",
                        "https://mmbiz.qlogo.cn/",
                    )
                ):
                    raise WeChatError("微信图片地址不符合预期")
            a = amap[v["cover"]]
            path, info = publication_image(blobs, a["sha256"], "cover")
            suffix = ".png" if info["mime"] == "image/png" else ".jpg"
            media = w.upload(
                path.read_bytes(),
                Path(v["cover"]).stem + suffix,
                info["mime"],
                cover=True,
            )
            html = render_doc(
                doc,
                v["template"],
                amap,
                version_id=vid,
                urls=urls,
                template_css=v["template_css"],
            )
            hash = hashlib.sha256(html.encode()).hexdigest()
            with engine.begin() as c:
                c.execute(
                    update(db.publications)
                    .where(db.publications.c.id == pid)
                    .values(
                        status="prepared",
                        html_sent=html,
                        html_hash=hash,
                        cover_media_id=media,
                        prepared_images=json.dumps(images, ensure_ascii=False),
                        updated_at=time.time(),
                    )
                )
                log(c, user["username"], "wechat_prepared", vid)
            return {
                "html": html,
                "html_hash": hash,
                "version_id": vid,
                "images": images,
                "compression_notice": "",
            }
        except Exception as e:
            with engine.begin() as c:
                c.execute(
                    update(db.publications)
                    .where(db.publications.c.id == pid)
                    .values(status="prepare_failed", updated_at=time.time())
                )
            raise HTTPException(
                502,
                (
                    str(e)
                    if isinstance(e, WeChatError)
                    else "微信预览准备失败，可重试；尚未创建草稿"
                ),
            ) from e

    @app.post("/api/v2/versions/{vid}/send")
    def send(vid: int, body: Confirmation, user=Depends(current)):
        if not cfg["wechat"]["enable_draft"]:
            raise HTTPException(403, "草稿功能已关闭")
        with lock, engine.begin() as c:
            v = row(c, db.versions, vid)
            p = (
                c.execute(
                    select(db.publications).where(db.publications.c.version_id == vid)
                )
                .mappings()
                .first()
            )
            if not p or p["status"] != "prepared" or p["html_hash"] != body.html_hash:
                raise HTTPException(409, "预览确认不匹配或版本已发送")
            p = dict(p)
            c.execute(
                update(db.publications)
                .where(db.publications.c.id == p["id"])
                .values(status="drafting", updated_at=time.time())
            )
        try:
            result = app.state.wechat.call(
                "draft/add",
                {
                    "articles": [
                        {
                            "title": v["title"],
                            "content": p["html_sent"],
                            "thumb_media_id": p["cover_media_id"],
                            "need_open_comment": 0,
                            "only_fans_can_comment": 0,
                        }
                    ]
                },
            )
            with engine.begin() as c:
                c.execute(
                    update(db.publications)
                    .where(db.publications.c.id == p["id"])
                    .values(
                        status="draft",
                        draft_media_id=result["media_id"],
                        updated_at=time.time(),
                    )
                )
                log(c, user["username"], "draft_created", vid)
        except Exception as e:
            with engine.begin() as c:
                c.execute(
                    update(db.publications)
                    .where(db.publications.c.id == p["id"])
                    .values(status="draft_unknown", updated_at=time.time())
                )
            raise HTTPException(
                502, "草稿结果不确定，请核对微信后台；已阻止重复提交"
            ) from e
        return {"draft_media_id": result["media_id"], "status": "draft"}

    @app.get("/api/v2/versions/{vid}/diff")
    def diff(vid: int, user=Depends(current)):
        with engine.begin() as c:
            p = (
                c.execute(
                    select(db.publications).where(db.publications.c.version_id == vid)
                )
                .mappings()
                .first()
            )
            if not p:
                raise HTTPException(404)

        def lines(s):
            return BeautifulSoup(s or "", "html.parser").prettify().splitlines()

        return {
            "diff": "\n".join(
                difflib.unified_diff(
                    lines(p["html_sent"]),
                    lines(p["html_returned"]),
                    fromfile="发送版本",
                    tofile="微信返回版本",
                    lineterm="",
                )
            )
        }

    # Additive content migration: preserve original Markdown and original asset aliases.
    with lock, engine.begin() as c:
        for v in (
            c.execute(select(db.versions).where(db.versions.c.content_json.is_(None)))
            .mappings()
            .all()
        ):
            normalize_version(c, dict(v))
    return normalize_version
