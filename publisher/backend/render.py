import os
from pathlib import Path
from urllib.parse import quote
from bs4 import BeautifulSoup
from premailer import transform
from .content import MD, asset_path, image_refs

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / 'templates'

def templates():
    return sorted(p.stem for p in TEMPLATE_DIR.glob('*.css'))

def render(markdown, template, assets, version_id=None, wechat_urls=None, template_css=None):
    if template_css is None and template not in templates():
        raise ValueError('未知版式')
    for name in image_refs(markdown):
        if name not in assets:
            raise ValueError(f'此版本没有图片：{name}')
    soup = BeautifulSoup(MD.render(markdown), 'html.parser')
    for img in soup.find_all('img'):
        name = asset_path(img['src'])
        img['src'] = (wechat_urls[name] if wechat_urls is not None else
                      f'{os.getenv("PUBLISHER_BASE_PATH", "").rstrip("/")}/api/v1/versions/{version_id}/assets/{quote(name)}')
        img.attrs = {k: v for k, v in img.attrs.items() if k in ('src', 'alt')}
    html = '<section class="article">' + str(soup) + '</section>'
    css = template_css if template_css is not None else (TEMPLATE_DIR / f'{template}.css').read_text()
    html = transform(html, css_text=css,
                     allow_network=False, allow_loading_external_files=False,
                     remove_classes=True, disable_leftover_css=True)
    result = BeautifulSoup(html, 'html.parser')
    return ''.join(str(x) for x in result.body.contents)
