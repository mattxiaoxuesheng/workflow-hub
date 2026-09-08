"""Offline package builder / explicit HTTPS upload. Run from repository root."""
import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit
from publisher.backend.content import build_package

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--article',required=True,help='inputs/wechat/<slug>')
    p.add_argument('--output',default='output/wechat/article-package.zip')
    p.add_argument('--commit',default=os.getenv('GITHUB_SHA',''))
    p.add_argument('--upload',action='store_true')
    args=p.parse_args()
    root=Path('inputs/wechat').resolve(); article=Path(args.article).resolve()
    if article.parent != root: raise SystemExit('article 必须为 inputs/wechat 的直接子目录')
    package=build_package(article,args.output,args.commit)
    print(f'Package: {package}')
    if args.upload:
        import httpx
        url=os.environ['PUBLISHER_URL'].rstrip('/')
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise SystemExit('PUBLISHER_URL 必须为不含路径、凭证的HTTPS源地址')
        token=os.environ['PUBLISHER_UPLOAD_TOKEN']
        with package.open('rb') as f:
            try:
                r=httpx.post(url+'/api/v1/ingest',headers={'Authorization':'Bearer '+token},files={'package':('article-package.zip',f,'application/zip')},timeout=90,follow_redirects=False)
                if r.status_code != 200: raise SystemExit(f'上传失败 HTTP {r.status_code}；检查服务端日志')
                result=r.json()
            except httpx.HTTPError: raise SystemExit('上传连接失败；同一内容包可安全重试')
        print(f'Imported version: {result["version_id"]}, V{result["number"]}')
if __name__=='__main__': main()
