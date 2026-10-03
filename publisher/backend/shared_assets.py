"""Shared image catalog, with per-article attachments and reference-safe deletion."""

import hashlib
import io
import secrets
import time
from pathlib import Path

from fastapi import Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import insert, select, update, func

from . import db
from .images import LIMITS, publication_image
from .content import asset_path

UPLOAD_LIMIT = 10 * 1024**2


async def read_upload(file):
    content = await file.read(UPLOAD_LIMIT + 1)
    if len(content) > UPLOAD_LIMIT:
        raise HTTPException(413, "图片最大10MB")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if (
                image.format not in ("JPEG", "PNG", "WEBP")
                or getattr(image, "is_animated", False)
                or image.width * image.height > 40_000_000
            ):
                raise ValueError()
            mime = Image.MIME[image.format]
            image.verify()
    except Exception as exc:
        raise HTTPException(
            422, "需要有效静态JPEG/PNG/WebP图片，最多4000万像素"
        ) from exc
    return content, mime


def ensure_shared(c, sha, mime, size, filename=None):
    suffix = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
    path = f"uploads/{sha}.{suffix}"
    old = (
        c.execute(select(db.shared_assets).where(db.shared_assets.c.sha256 == sha))
        .mappings()
        .first()
    )
    if not old:
        c.execute(
            insert(db.shared_assets).values(
                sha256=sha,
                path=path,
                filename=(filename or Path(path).name)[:200],
                mime=mime,
                size=size,
                created_at=time.time(),
            )
        )
    elif old["deleted_at"]:
        c.execute(
            update(db.shared_assets)
            .where(db.shared_assets.c.id == old["id"])
            .values(deleted_at=None, filename=(filename or old["filename"])[:200])
        )
    elif filename:
        c.execute(
            update(db.shared_assets)
            .where(db.shared_assets.c.id == old["id"])
            .values(filename=filename[:200])
        )
    return (
        c.execute(select(db.shared_assets).where(db.shared_assets.c.sha256 == sha))
        .mappings()
        .one()
    )


def install_shared_assets(
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
):
    # Existing article images become selectable across articles without moving files.
    with engine.begin() as c:
        for a in c.execute(
            select(db.library).where(db.library.c.deleted_at.is_(None))
        ).mappings():
            ensure_shared(c, a["sha256"], a["mime"], a["size"])

    def active(c, sid):
        a = row(c, db.shared_assets, sid)
        if a["deleted_at"]:
            raise HTTPException(404, "素材不存在")
        return a

    def details(a):
        root = f"/api/v2/shared-assets/{a['id']}"
        return {
            **dict(a),
            "original_url": root + "/content",
            "publication_images": image_info(a, a["path"], root),
        }

    @app.get("/api/v2/shared-assets")
    def listing(
        q: str = Query("", max_length=200),
        offset: int = Query(0, ge=0),
        limit: int = Query(30, ge=1, le=100),
        user=Depends(current),
    ):
        where = [db.shared_assets.c.deleted_at.is_(None)]
        if q:
            where.append(db.shared_assets.c.filename.contains(q, autoescape=True))
        with engine.begin() as c:
            total = c.execute(
                select(func.count()).select_from(db.shared_assets).where(*where)
            ).scalar_one()
            entries = (
                c.execute(
                    select(db.shared_assets)
                    .where(*where)
                    .order_by(db.shared_assets.c.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return {
            "items": [details(a) for a in entries],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @app.post("/api/v2/shared-assets")
    async def upload(file: UploadFile = File(...), user=Depends(current)):
        content, mime = await read_upload(file)
        sha = hashlib.sha256(content).hexdigest()
        with lock, engine.begin() as c:
            dest = blobs / sha
            if not dest.exists():
                temp = blobs / (sha + "." + secrets.token_hex(6))
                temp.write_bytes(content)
                temp.replace(dest)
            a = dict(
                ensure_shared(
                    c,
                    sha,
                    mime,
                    len(content),
                    Path((file.filename or "图片").replace("\\", "/")).name,
                )
            )
            result = details(a)
            log(c, user["username"], "shared_asset_uploaded", a["id"])
        return result

    @app.get("/api/v2/shared-assets/{sid}/content")
    def original(sid: int, user=Depends(current)):
        with engine.begin() as c:
            a = active(c, sid)
        return FileResponse(blobs / a["sha256"], media_type=a["mime"])

    @app.get("/api/v2/shared-assets/{sid}/publication-image/{role}/{name:path}")
    def copy(sid: int, role: str, name: str, user=Depends(current)):
        with engine.begin() as c:
            a = active(c, sid)
        if role not in LIMITS or name != a["path"]:
            raise HTTPException(404, "图片不存在")
        path, info = publication_image(blobs, a["sha256"], role)
        return FileResponse(path, media_type=info["mime"])

    @app.post("/api/v2/articles/{aid}/shared-assets/{sid}")
    def attach(aid: int, sid: int, user=Depends(current)):
        with lock, engine.begin() as c:
            row(c, db.articles, aid)
            a = active(c, sid)
            name = register_asset(c, aid, a["sha256"], a["mime"])
            attached = (
                c.execute(
                    select(db.library).where(
                        db.library.c.article_id == aid, db.library.c.path == name
                    )
                )
                .mappings()
                .one()
            )
            log(c, user["username"], "shared_asset_attached", f"{sid}:{aid}")
            return asset_details(dict(attached), aid)

    @app.delete("/api/v2/shared-assets/{sid}")
    def remove(sid: int, user=Depends(current)):
        import json

        def uses(node, path):
            if node.get("type") == "image":
                try:
                    if asset_path(node.get("attrs", {}).get("src", "")) == path:
                        return True
                except ValueError as exc:
                    raise HTTPException(
                        409, "工作稿图片路径异常，请修正后再删除素材"
                    ) from exc
            return any(uses(child, path) for child in node.get("content", []))

        with lock, engine.begin() as c:
            a = active(c, sid)
            if c.execute(
                select(db.assets.c.id).where(db.assets.c.sha256 == a["sha256"])
            ).first():
                raise HTTPException(409, "历史版本仍引用此素材，不能永久删除")
            associations = (
                c.execute(select(db.library).where(db.library.c.sha256 == a["sha256"]))
                .mappings()
                .all()
            )
            for association in associations:
                d = (
                    c.execute(
                        select(db.drafts).where(
                            db.drafts.c.article_id == association["article_id"]
                        )
                    )
                    .mappings()
                    .first()
                )
                if d and (
                    d["cover"] == association["path"]
                    or uses(json.loads(d["content_json"]), association["path"])
                ):
                    raise HTTPException(409, "工作稿或封面仍引用此素材，不能永久删除")
            c.execute(
                update(db.shared_assets)
                .where(db.shared_assets.c.id == sid)
                .values(deleted_at=time.time())
            )
            c.execute(
                update(db.library)
                .where(db.library.c.sha256 == a["sha256"])
                .values(deleted_at=time.time())
            )
            log(c, user["username"], "shared_asset_deleted", sid)
        # Retain bytes for concurrent readers; deleted assets are no longer selectable.
        return {"ok": True}
