import io
import subprocess
import sys
import tarfile

from PIL import Image
from publisher.tests.test_workflow import env as env
from publisher.tests.test_v2 import new, save


def test_shared_upload_cross_article_replacement_and_deletion(env):
    _, c, *_ = env
    buf = io.BytesIO()
    Image.new("RGB", (80, 60), "blue").save(buf, format="PNG")
    data = buf.getvalue()
    upload = lambda: c.post(
        "/api/v2/shared-assets", files={"file": ("shared-blue.png", data, "image/png")}
    )
    asset = upload().json()
    assert upload().json()["id"] == asset["id"]
    assert c.get("/api/v2/shared-assets?q=shared-blue").json()["total"] == 1
    assert c.get(asset["original_url"]).content == data
    first, second = new(c), new(c)
    for aid in (first, second):
        attached = c.post(f"/api/v2/articles/{aid}/shared-assets/{asset['id']}")
        assert attached.status_code == 200
        path = attached.json()["path"]
        d = c.get(f"/api/v2/articles/{aid}/draft").json()
        saved = save(
            c,
            aid,
            d,
            cover=path,
            content_json={
                "type": "doc",
                "content": [{"type": "image", "attrs": {"src": path}}],
            },
        )
        assert saved.status_code == 200
        if aid == first:
            encoded = save(
                c,
                aid,
                saved.json(),
                cover=None,
                content_json={
                    "type": "doc",
                    "content": [
                        {"type": "image", "attrs": {"src": path.replace("/", "%2F")}}
                    ],
                },
            )
            assert encoded.status_code == 200
            assert c.delete(f"/api/v2/shared-assets/{asset['id']}").status_code == 409
    assert c.delete(f"/api/v2/shared-assets/{asset['id']}").status_code == 409
    # Clearing one article must still protect the other article's image.
    empty = {"type": "doc", "content": [{"type": "paragraph"}]}
    for aid in (first, second):
        d = c.get(f"/api/v2/articles/{aid}/draft").json()
        assert save(c, aid, d, cover=None, content_json=empty).status_code == 200
        if aid == first:
            assert c.delete(f"/api/v2/shared-assets/{asset['id']}").status_code == 409
    assert c.delete(f"/api/v2/shared-assets/{asset['id']}").status_code == 200
    assert c.get("/api/v2/shared-assets").json()["total"] == 0
    assert c.get(asset["original_url"]).status_code == 404
    assert (
        c.post(f"/api/v2/articles/{first}/shared-assets/{asset['id']}").status_code
        == 404
    )


def test_article_upload_shared_history_and_unattached_backup(env, tmp_path):
    app, c, *_ = env
    aid = new(c)
    buf = io.BytesIO()
    Image.new("RGB", (60, 60), "green").save(buf, format="PNG")
    a = c.post(
        f"/api/v2/articles/{aid}/assets",
        files={"file": ("article-green.png", buf.getvalue(), "image/png")},
    ).json()
    shared = c.get("/api/v2/shared-assets?q=article-green").json()["items"][0]
    # Removing an unused article attachment must leave the shared original available.
    assert c.delete(f"/api/v2/articles/{aid}/assets/{a['id']}").status_code == 200
    assert c.get(shared["original_url"]).status_code == 200
    assert (
        c.post(f"/api/v2/articles/{aid}/shared-assets/{shared['id']}").status_code
        == 200
    )
    d = c.get(f"/api/v2/articles/{aid}/draft").json()
    d = save(c, aid, d, cover=a["path"]).json()
    assert (
        c.post(
            f"/api/v2/articles/{aid}/versions", json={"revision": d["revision"]}
        ).status_code
        == 200
    )
    assert c.delete(f"/api/v2/shared-assets/{shared['id']}").status_code == 409
    # A shared upload with no article association must be in the deployment backup.
    Image.new("RGB", (10, 10), "red").save(buf := io.BytesIO(), format="PNG")
    unattached = c.post(
        "/api/v2/shared-assets",
        files={"file": ("unattached.png", buf.getvalue(), "image/png")},
    ).json()
    database = app.state.engine.url.database
    from pathlib import Path

    output = subprocess.check_output(
        [
            sys.executable,
            "deploy/backup.py",
            "--data",
            str(Path(database).parent),
            "--output",
            str(tmp_path),
        ],
        text=True,
    ).strip()
    with tarfile.open(output) as archive:
        assert f"assets/{unattached['sha256']}" in archive.getnames()
