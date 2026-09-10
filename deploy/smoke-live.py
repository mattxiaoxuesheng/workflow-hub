"""Verify deployed subpath, import sample, and provision a GitHub ingest token.

Run once with /bootstrap bound to the root-only secrets directory and /work
bound to the source repository. Never calls WeChat draft or publish endpoints.
"""
import os
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from publisher.backend.content import build_package

origin = 'https://stocklab.hardway.top'
base = origin + '/publisher'
credentials = dict(line.split(': ', 1) for line in Path('/bootstrap/admin-login.txt').read_text().splitlines())
with httpx.Client(timeout=30, headers={'Origin': origin}) as client:
    page = client.get(base + '/')
    page.raise_for_status()
    soup = BeautifulSoup(page.text, 'html.parser')
    for script in soup.find_all('script', src=True):
        assert script['src'].startswith('/publisher/assets/')
        client.get(origin + script['src']).raise_for_status()
    login = client.post(base + '/api/v1/login', json={'username': credentials['Username'], 'password': credentials['Password']})
    login.raise_for_status()
    assert 'Path=/publisher/' in login.headers['set-cookie']
    client.headers['x-csrf-token'] = login.json()['csrf']
    client.get(base + '/api/v1/me').raise_for_status()
    token_file = Path('/bootstrap/github-upload-token.txt')
    if not token_file.exists():
        response = client.post(base + '/api/v1/admin/tokens', json={'name': 'github-actions', 'days': 90})
        response.raise_for_status()
        with token_file.open('x') as stream:
            os.chmod(token_file, 0o600)
            stream.write(response.json()['token'])
    package = build_package(Path('/work/inputs/wechat/acceptance'), '/tmp/publisher-acceptance.zip', '')
    with package.open('rb') as stream:
        response = client.post(base + '/api/v1/ingest', headers={'Authorization': 'Bearer ' + token_file.read_text()}, files={'package': ('acceptance.zip', stream, 'application/zip')})
    response.raise_for_status()
    version_id = response.json()['version_id']
    response = client.get(base + f'/api/v1/versions/{version_id}')
    response.raise_for_status()
    version = response.json()
    themes = client.get(base + '/api/v1/templates').json()
    for theme in themes:
        response = client.post(base + '/api/v1/preview', json={'title': version['title'], 'markdown': version['markdown'], 'template': theme, 'base_version_id': version_id})
        response.raise_for_status()
        preview = BeautifulSoup(response.json()['html'], 'html.parser')
        for image in preview.find_all('img'):
            assert image['src'].startswith('/publisher/api/')
            client.get(origin + image['src']).raise_for_status()
    admin = client.get(base + '/api/v1/admin').json()
    client.post(base + '/api/v1/logout').raise_for_status()
    assert client.get(base + '/api/v1/me').status_code == 401
    assert client.get(origin + '/login').status_code == 200
    print('PASS: HTTPS, assets, login/logout, cookie path, import, three templates, preview images, StockLab login.')
    print('WeChat configured:', bool(admin['wechat']['secret_configured']))
