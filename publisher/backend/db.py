"""Versioned schema with additive V2 migrations. JSON bodies hold immutable snapshots, IDs/constraints are relational."""

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    Boolean,
    String,
    Text,
    Float,
    ForeignKey,
    UniqueConstraint,
    event,
)

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String, unique=True, nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("role", String, nullable=False),
    Column("status", String, nullable=False, default="active"),
    Column("created_at", Float, nullable=False),
)
tokens = Table(
    "api_tokens",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("prefix", String),
    Column("token_hash", String, unique=True),
    Column("scope", String),
    Column("created_at", Float),
    Column("expires_at", Float),
    Column("last_used_at", Float),
    Column("revoked_at", Float),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String, primary_key=True),
    Column("user_id", ForeignKey("users.id"), nullable=False),
    Column("csrf", String),
    Column("expires_at", Float),
)
articles = Table(
    "articles",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("slug", String, unique=True, nullable=False),
    Column("title", String),
    Column("created_at", Float),
    Column("updated_at", Float),
)
versions = Table(
    "article_versions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("article_id", ForeignKey("articles.id"), nullable=False),
    Column("number", Integer, nullable=False),
    Column("title", String),
    Column("markdown", Text),
    Column("content_json", Text),
    Column("rendered_html", Text),
    Column("template", String),
    Column("template_css", Text),
    Column("cover", String),
    Column("git_commit", String),
    Column("package_hash", String),
    Column("created_by", String),
    Column("created_at", Float),
    UniqueConstraint("article_id", "number"),
    UniqueConstraint("article_id", "package_hash"),
)
assets = Table(
    "article_assets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("version_id", ForeignKey("article_versions.id"), nullable=False),
    Column("path", String),
    Column("sha256", String),
    Column("mime", String),
    UniqueConstraint("version_id", "path"),
)
publications = Table(
    "wechat_publications",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("version_id", ForeignKey("article_versions.id"), unique=True),
    Column("status", String),
    Column("draft_media_id", String),
    Column("publish_id", String),
    Column("html_sent", Text),
    Column("cover_media_id", String),
    Column("html_hash", String),
    Column("prepared_images", Text),
    Column("html_returned", Text),
    Column("result", Text),
    Column("created_at", Float),
    Column("updated_at", Float),
)
audit = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("actor", String),
    Column("action", String),
    Column("target", String),
    Column("created_at", Float),
)
schema = Table("schema_version", metadata, Column("version", Integer, primary_key=True))

drafts = Table(
    "working_drafts",
    metadata,
    Column("article_id", ForeignKey("articles.id"), primary_key=True),
    Column("base_version_id", ForeignKey("article_versions.id")),
    Column("follow_latest", Boolean, nullable=False, server_default="1"),
    Column("title", String),
    Column("content_json", Text),
    Column("template", String),
    Column("cover", String),
    Column("revision", Integer, nullable=False, default=1),
    Column("updated_at", Float),
    Column("updated_by", String),
)
shared_assets = Table(
    "shared_assets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("sha256", String, nullable=False, unique=True),
    Column("path", String, nullable=False),
    Column("filename", String, nullable=False),
    Column("mime", String, nullable=False),
    Column("size", Integer, nullable=False),
    Column("created_at", Float),
    Column("deleted_at", Float),
)
library = Table(
    "asset_library",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("article_id", ForeignKey("articles.id"), nullable=False),
    Column("path", String, nullable=False),
    Column("sha256", String, nullable=False),
    Column("mime", String),
    Column("size", Integer),
    Column("created_at", Float),
    Column("deleted_at", Float),
    UniqueConstraint("article_id", "path"),
)


def open_db(path):
    engine = create_engine(
        "sqlite:///" + str(path),
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def configure(dbapi, _):
        dbapi.execute("PRAGMA foreign_keys=ON")
        dbapi.execute("PRAGMA journal_mode=WAL")

    metadata.create_all(engine)
    with engine.begin() as c:
        c.exec_driver_sql("INSERT OR IGNORE INTO schema_version(version) VALUES(1)")
        additions = {
            # Existing drafts may be deliberate historical restores; preserve them.
            "working_drafts": {"follow_latest": "BOOLEAN NOT NULL DEFAULT 0"},
            "article_versions": {"content_json": "TEXT", "rendered_html": "TEXT"},
            "wechat_publications": {
                "cover_media_id": "VARCHAR",
                "html_hash": "VARCHAR",
                "prepared_images": "TEXT",
            },
        }
        for table, fields in additions.items():
            existing = {r[1] for r in c.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, sqltype in fields.items():
                if name not in existing:
                    c.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}"
                    )
        c.exec_driver_sql("INSERT OR IGNORE INTO schema_version(version) VALUES(2)")
    return engine
