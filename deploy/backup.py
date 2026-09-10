"""Consistent SQLite snapshot plus immutable content-addressed assets."""
import argparse
import sqlite3
import tarfile
import tempfile
from pathlib import Path
from datetime import datetime, timezone

p=argparse.ArgumentParser(); p.add_argument('--data',default='/opt/wechat-publisher/data'); p.add_argument('--output',default='/opt/wechat-publisher/backups'); a=p.parse_args()
data=Path(a.data); out=Path(a.output); out.mkdir(parents=True,exist_ok=True,mode=0o700)
name=out/('publisher-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.tar.gz')
with tempfile.TemporaryDirectory() as temp:
    snapshot=Path(temp)/'publisher.db'
    with sqlite3.connect(f'file:{data / "publisher.db"}?mode=ro',uri=True) as source, sqlite3.connect(snapshot) as target:
        source.backup(target)
    with sqlite3.connect(snapshot) as c: hashes=[r[0] for r in c.execute('SELECT DISTINCT sha256 FROM article_assets')]
    with name.open('xb') as output:
        name.chmod(0o600)
        with tarfile.open(fileobj=output,mode='w:gz') as tar:
            tar.add(snapshot,arcname='publisher.db')
            for sha in hashes: tar.add(data/'assets'/sha,arcname='assets/'+sha)
print(name)
