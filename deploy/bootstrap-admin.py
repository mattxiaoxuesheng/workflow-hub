"""One-time server bootstrap; mount a root-only directory at /bootstrap."""
import os
import secrets
import time
from pathlib import Path
from sqlalchemy import insert, select
from publisher.backend.db import open_db, users
from publisher.backend.main import password_hasher

engine = open_db(Path(os.environ['PUBLISHER_DATA_DIR']) / 'publisher.db')
with engine.begin() as connection:
    if connection.execute(select(users.c.id).where(users.c.username == 'admin')).first():
        raise SystemExit('Admin already exists; password unchanged.')
    password = secrets.token_urlsafe(24)
    destination = Path('/bootstrap/admin-login.txt')
    with destination.open('x', encoding='utf-8') as stream:
        os.chmod(destination, 0o600)
        stream.write('URL: https://stocklab.hardway.top/publisher/\nUsername: admin\nPassword: ' + password + '\n')
    connection.execute(insert(users).values(username='admin', password_hash=password_hasher.hash(password), role='ADMIN', status='active', created_at=time.time()))
print('Admin created; credentials saved to the mounted bootstrap directory.')
