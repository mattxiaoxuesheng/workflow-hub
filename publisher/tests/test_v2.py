from publisher.tests.test_workflow import env as env
import io
import sqlite3
from PIL import Image
from sqlalchemy import select
from publisher.backend import db

DOC = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Hello V2"}]}
    ],
}


def new(c):
    r = c.post("/api/v2/articles", json={"title": "New article", "template": "clean"})
    assert r.status_code == 200, r.text
    return r.json()["article_id"]


def save(c, aid, draft, **changes):
    return c.put(
        f"/api/v2/articles/{aid}/draft",
        json={
            **{
                k: draft[k]
                for k in ("title", "template", "content_json", "cover", "revision")
            },
            **changes,
        },
    )


def test_draft_conflicts_versions_restore(env):
    app, c, w, *_ = env
    aid = new(c)
    d = c.get(f"/api/v2/articles/{aid}/draft").json()
    assert c.get("/api/v1/articles").json()[0]["versions"] == []
    r = save(c, aid, d, content_json=DOC)
    assert r.status_code == 200, r.text
    assert save(c, aid, d, title="stale").status_code == 409
    d = r.json()
    snap = c.post(f"/api/v2/articles/{aid}/versions", json={"revision": d["revision"]})
    assert snap.status_code == 200, snap.text
    vid = snap.json()["version_id"]
    old = c.get(f"/api/v1/versions/{vid}").json()
    assert old["content_json"] == DOC
    d = c.get(f"/api/v2/articles/{aid}/draft").json()
    assert save(c, aid, d, title="changed").status_code == 200
    assert c.get(f"/api/v1/versions/{vid}").json()["title"] == "New article"
    assert (
        c.post(
            f"/api/v2/articles/{aid}/restore/{vid}", json={"revision": d["revision"]}
        ).status_code
        == 409
    )
    current = c.get(f"/api/v2/articles/{aid}/draft").json()
    restored = c.post(
        f"/api/v2/articles/{aid}/restore/{vid}", json={"revision": current["revision"]}
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["title"] == "New article"


def test_migrated_versions_and_templates_remain_frozen(env):
    app, c, w, ingest, *_ = env
    r = ingest().json()
    v = c.get(f"/api/v1/versions/{r['version_id']}").json()
    assert v["content_json"]["type"] == "doc" and v["markdown"]
    d = c.get(f"/api/v2/articles/{r['article_id']}/draft").json()
    assert d["base_version_id"] == r["version_id"]
    assert c.get("/api/v2/templates").json()[0]["css"]
    assert d["content_json"]["type"] == "doc"


def test_assets_and_exact_wechat_preview(env):
    app, c, w, *_ = env
    aid = new(c)
    b = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(b, format="PNG")
    uploaded = c.post(
        f"/api/v2/articles/{aid}/assets",
        files={"file": ("a.png", b.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    a = uploaded.json()
    d = c.get(f"/api/v2/articles/{aid}/draft").json()
    doc = {
        "type": "doc",
        "content": DOC["content"]
        + [
            {
                "type": "image",
                "attrs": {
                    "src": a["path"],
                    "alt": "test",
                    "caption": "caption",
                    "width": "50%",
                },
            }
        ],
    }
    d = save(c, aid, d, content_json=doc, cover=a["path"]).json()
    assert c.delete(f"/api/v2/articles/{aid}/assets/{a['id']}").status_code == 409
    vid = c.post(
        f"/api/v2/articles/{aid}/versions", json={"revision": d["revision"]}
    ).json()["version_id"]
    p = c.post(f"/api/v2/versions/{vid}/prepare")
    assert p.status_code == 200, p.text
    assert not any(x[0] == "draft/add" for x in w.calls)
    html = p.json()["html"]
    assert (
        "https://mmbiz.qpic.cn/" in html and "caption" in html and "<style" not in html
    )
    assert (
        c.post(f"/api/v2/versions/{vid}/send", json={"html_hash": "bad"}).status_code
        == 409
    )
    sent = c.post(
        f"/api/v2/versions/{vid}/send", json={"html_hash": p.json()["html_hash"]}
    )
    assert sent.status_code == 200, sent.text
    assert w.html == html
    assert (
        c.post(
            f"/api/v2/versions/{vid}/send", json={"html_hash": p.json()["html_hash"]}
        ).status_code
        == 409
    )


def test_document_validation_overrides(env):
    app, c, w, *_ = env
    aid = new(c)
    d = c.get(f"/api/v2/articles/{aid}/draft").json()
    for doc in (
        {"type": "doc", "content": [{"type": "script"}]},
        {
            "type": "doc",
            "content": [{"type": "image", "attrs": {"src": "https://evil/a.png"}}],
        },
        {
            "type": "doc",
            "content": [{"type": "paragraph", "attrs": {"textAlign": "absolute"}}],
        },
    ):
        assert save(c, aid, d, content_json=doc).status_code == 422
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2, "textAlign": "center"},
                "content": [
                    {
                        "type": "text",
                        "text": "Red",
                        "marks": [{"type": "textStyle", "attrs": {"color": "#ff0000"}}],
                    }
                ],
            }
        ],
    }
    d = save(c, aid, d, content_json=doc).json()
    vid = c.post(
        f"/api/v2/articles/{aid}/versions", json={"revision": d["revision"]}
    ).json()["version_id"]
    html = c.get(f"/api/v1/versions/{vid}").json()["preview_html"]
    assert "text-align:center" in html.replace(" ", "") and (
        "#f00" in html or "#ff0000" in html
    )


def test_sqlite_additive_migration(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as c:
        c.executescript(
            "CREATE TABLE schema_version(version INTEGER PRIMARY KEY); INSERT INTO schema_version VALUES(1); CREATE TABLE article_versions(id INTEGER PRIMARY KEY,article_id INTEGER,number INTEGER,title TEXT,markdown TEXT,template TEXT,template_css TEXT,cover TEXT,git_commit TEXT,package_hash TEXT,created_by TEXT,created_at FLOAT); INSERT INTO article_versions(id,article_id,number,markdown) VALUES(7,1,1,'# Original');"
        )
    engine = db.open_db(path)
    with engine.connect() as c:
        v = c.execute(select(db.versions)).mappings().one()
        assert v["id"] == 7 and v["markdown"] == "# Original"
        assert "content_json" in v
    engine.dispose()
    engine = db.open_db(path)
    engine.dispose()


def test_prepare_retry_and_uncertain_send_never_repeats(env):
    app, c, w, ingest, *_ = env
    vid = ingest().json()["version_id"]
    original_upload = w.upload

    def fail_upload(*args, **kwargs):
        from publisher.backend.wechat import WeChatError

        raise WeChatError("upload timeout")

    w.upload = fail_upload
    assert c.post(f"/api/v2/versions/{vid}/prepare").status_code == 502
    assert not any(x[0] == "draft/add" for x in w.calls)
    w.upload = original_upload
    prepared = c.post(f"/api/v2/versions/{vid}/prepare").json()
    calls = len(w.calls)
    assert c.post(f"/api/v2/versions/{vid}/prepare").json() == prepared
    assert len(w.calls) == calls
    original_call = w.call
    attempts = []

    def fail_send(endpoint, payload):
        if endpoint == "draft/add":
            attempts.append(payload)
            from publisher.backend.wechat import WeChatError

            raise WeChatError("uncertain timeout")
        return original_call(endpoint, payload)

    w.call = fail_send
    body = {"html_hash": prepared["html_hash"]}
    assert c.post(f"/api/v2/versions/{vid}/send", json=body).status_code == 502
    assert c.post(f"/api/v2/versions/{vid}/send", json=body).status_code == 409
    assert len(attempts) == 1


def test_browser_imports_security_and_diff(env):
    app, c, w, ingest, token, package = env
    r = c.post(
        "/api/v2/import/package",
        files={"file": ("article.zip", package, "application/zip")},
    )
    assert r.status_code == 200, r.text
    aid = r.json()["article_id"]
    d = c.get(f"/api/v2/articles/{aid}/draft").json()
    assert d["cover"] and d["content_json"]["type"] == "doc"
    assert not next(a for a in c.get("/api/v1/articles").json() if a["id"] == aid)[
        "versions"
    ]
    bad = c.post(
        "/api/v2/import/markdown",
        json={"title": "remote", "markdown": "![x](https://evil/x.png)"},
    )
    assert bad.status_code == 422
    safe = c.post(
        "/api/v2/import/markdown",
        json={
            "title": "safe",
            "markdown": "<script>alert(1)</script>\n\n[x](javascript:alert(1))",
        },
    )
    assert safe.status_code == 200
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "bad",
                        "marks": [
                            {"type": "link", "attrs": {"href": "javascript:alert(1)"}}
                        ],
                    }
                ],
            }
        ],
    }
    assert save(c, aid, d, content_json=doc).status_code == 422
    vid = c.post(
        f"/api/v2/articles/{aid}/versions", json={"revision": d["revision"]}
    ).json()["version_id"]
    p = c.post(f"/api/v2/versions/{vid}/prepare").json()
    assert (
        c.post(
            f"/api/v2/versions/{vid}/send", json={"html_hash": p["html_hash"]}
        ).status_code
        == 200
    )
    w.html += "<p>微信调整</p>"
    assert c.post(f"/api/v1/versions/{vid}/draft/check").json()["html_changed"]
    diff = c.get(f"/api/v2/versions/{vid}/diff")
    assert diff.status_code == 200, diff.text
    assert "微信调整" in diff.json()["diff"]


def test_backup_includes_unsnapshotted_assets(env, tmp_path):
    import subprocess, sys, tarfile

    app, c, w, *_ = env
    aid = new(c)
    b = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(b, format="PNG")
    a = c.post(
        f"/api/v2/articles/{aid}/assets",
        files={"file": ("draft.png", b.getvalue(), "image/png")},
    ).json()
    path = app.state.engine.url.database
    result = subprocess.run(
        [
            sys.executable,
            "deploy/backup.py",
            "--data",
            str(__import__("pathlib").Path(path).parent),
            "--output",
            str(tmp_path / "backups"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    with tarfile.open(result.stdout.strip()) as archive:
        assert "publisher.db" in archive.getnames()
        assert "assets/" + a["sha256"] in archive.getnames()
    assert c.delete(f"/api/v2/articles/{aid}/assets/{a['id']}").status_code == 200
    assert c.get(f"/api/v2/articles/{aid}/assets/{a['path']}").status_code == 404


def test_markdown_tight_lists_and_tables_preserve_text_and_marks():
    from publisher.backend.richtext import from_markdown, render_doc

    source = "- **first item**\n- second item\n\n| Name | Value |\n| :--- | ---: |\n| Revenue | 123 |"
    doc = from_markdown(source)
    html = render_doc(doc, "clean", {})
    for text in ("first item", "second item", "Name", "Value", "Revenue", "123"):
        assert text in html
    assert "<strong" in html and "<table" in html and "<li" in html


def test_tiptap_list_and_table_attributes(env):
    app, c, w, *_ = env
    aid = new(c)
    d = c.get(f"/api/v2/articles/{aid}/draft").json()
    paragraph = {
        "type": "paragraph",
        "attrs": {"textAlign": None, "spacing": None},
        "content": [{"type": "text", "text": "text"}],
    }
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "orderedList",
                "attrs": {"start": 1, "type": None},
                "content": [{"type": "listItem", "content": [paragraph]}],
            },
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "attrs": {
                                    "colspan": 1,
                                    "rowspan": 1,
                                    "colwidth": None,
                                    "align": None,
                                },
                                "content": [paragraph],
                            }
                        ],
                    }
                ],
            },
        ],
    }
    r = save(c, aid, d, content_json=doc)
    assert r.status_code == 200, r.text


def test_markdown_encoded_image_names_and_empty_code():
    from publisher.backend.richtext import from_markdown, validate_doc

    mapping = {
        "images/中文.png": "uploads/chinese.png",
        "images/space name.png": "uploads/space.png",
    }
    doc = from_markdown(
        "![x](<images/中文.png>)\n\n![y](<images/space name.png>)", mapping
    )
    assert validate_doc(doc, {name: {} for name in mapping.values()}) == list(
        mapping.values()
    )
    assert validate_doc(from_markdown("```\n```"), {}) == []


def test_snapshot_returns_exact_revision_for_browser(env):
    app, c, w, *_ = env
    aid = new(c)
    d = c.get(f"/api/v2/articles/{aid}/draft").json()
    result = c.post(
        f"/api/v2/articles/{aid}/versions", json={"revision": d["revision"]}
    ).json()
    assert result.get("revision") == d["revision"] + 1
