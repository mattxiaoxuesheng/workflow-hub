"""Run inside the container: python -m publisher.backend.cli create-admin."""
import argparse
import getpass
import os
import time
from pathlib import Path
from sqlalchemy import insert, select
from .db import open_db, users
from .main import password_hasher

def main():
    p=argparse.ArgumentParser(); p.add_argument('command', choices=['create-admin','reset-password']); p.add_argument('--username',default='admin'); args=p.parse_args()
    path=Path(os.getenv('PUBLISHER_DATA_DIR','publisher/data')); path.mkdir(parents=True,exist_ok=True)
    engine=open_db(path/'publisher.db')
    password=getpass.getpass('Password (12+ characters): ')
    if len(password)<12 or password != getpass.getpass('Repeat password: '): raise SystemExit('密码过短或不一致')
    with engine.begin() as c:
        u=c.execute(select(users).where(users.c.username==args.username)).mappings().first()
        if args.command=='create-admin':
            if u: raise SystemExit('用户已存在')
            c.execute(insert(users).values(username=args.username,password_hash=password_hasher.hash(password),role='ADMIN',status='active',created_at=time.time()))
        else:
            if not u: raise SystemExit('用户不存在')
            from sqlalchemy import update, delete
            from .db import sessions
            c.execute(update(users).where(users.c.id==u['id']).values(password_hash=password_hasher.hash(password)))
            c.execute(delete(sessions).where(sessions.c.user_id==u['id']))
    print('Done')
if __name__=='__main__': main()
