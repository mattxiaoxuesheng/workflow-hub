"""V1 schema. JSON bodies hold immutable snapshots, IDs/constraints are relational."""
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, Float, ForeignKey, UniqueConstraint, event
metadata = MetaData()
users = Table('users', metadata, Column('id', Integer, primary_key=True), Column('username', String, unique=True, nullable=False), Column('password_hash', Text, nullable=False), Column('role', String, nullable=False), Column('status', String, nullable=False, default='active'), Column('created_at', Float, nullable=False))
tokens = Table('api_tokens', metadata, Column('id', Integer, primary_key=True), Column('name', String), Column('prefix', String), Column('token_hash', String, unique=True), Column('scope', String), Column('created_at', Float), Column('expires_at', Float), Column('last_used_at', Float), Column('revoked_at', Float))
sessions = Table('sessions', metadata, Column('token_hash', String, primary_key=True), Column('user_id', ForeignKey('users.id'), nullable=False), Column('csrf', String), Column('expires_at', Float))
articles = Table('articles', metadata, Column('id', Integer, primary_key=True), Column('slug', String, unique=True, nullable=False), Column('title', String), Column('created_at', Float), Column('updated_at', Float))
versions = Table('article_versions', metadata, Column('id', Integer, primary_key=True), Column('article_id', ForeignKey('articles.id'), nullable=False), Column('number', Integer, nullable=False), Column('title', String), Column('markdown', Text), Column('template', String), Column('template_css', Text), Column('cover', String), Column('git_commit', String), Column('package_hash', String), Column('created_by', String), Column('created_at', Float), UniqueConstraint('article_id', 'number'), UniqueConstraint('article_id', 'package_hash'))
assets = Table('article_assets', metadata, Column('id', Integer, primary_key=True), Column('version_id', ForeignKey('article_versions.id'), nullable=False), Column('path', String), Column('sha256', String), Column('mime', String), UniqueConstraint('version_id', 'path'))
publications = Table('wechat_publications', metadata, Column('id', Integer, primary_key=True), Column('version_id', ForeignKey('article_versions.id'), unique=True), Column('status', String), Column('draft_media_id', String), Column('publish_id', String), Column('html_sent', Text), Column('html_returned', Text), Column('result', Text), Column('created_at', Float), Column('updated_at', Float))
audit = Table('audit_logs', metadata, Column('id', Integer, primary_key=True), Column('actor', String), Column('action', String), Column('target', String), Column('created_at', Float))
schema = Table('schema_version', metadata, Column('version', Integer, primary_key=True))

def open_db(path):
    engine = create_engine('sqlite:///' + str(path), connect_args={'check_same_thread': False, 'timeout': 30})
    @event.listens_for(engine, 'connect')
    def configure(dbapi, _):
        dbapi.execute('PRAGMA foreign_keys=ON')
        dbapi.execute('PRAGMA journal_mode=WAL')
    metadata.create_all(engine)
    with engine.begin() as c:
        c.exec_driver_sql('INSERT OR IGNORE INTO schema_version(version) VALUES(1)')
    return engine
