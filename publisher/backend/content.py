"""Shared, offline package validation. Never fetch remote Markdown resources."""
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from PIL import Image

MD = MarkdownIt('commonmark', {'html': False}).enable('table')

def asset_path(value):
    value = unquote(value)
    parsed = urlsplit(value)
    p = PurePosixPath(parsed.path)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or p.is_absolute() or '..' in p.parts or '\\' in value
            or not p.parts or any(x.startswith('.') for x in p.parts)
            or any(ord(x) < 32 for x in value)):
        raise ValueError('图片必须是文章目录内的普通相对路径')
    return str(p)

def image_refs(markdown):
    refs = []
    def visit(tokens):
        for t in tokens:
            if t.type == 'image':
                refs.append(asset_path(t.attrGet('src')))
            if t.children:
                visit(t.children)
    visit(MD.parse(markdown))
    return list(dict.fromkeys(refs))

def validate(manifest, files):
    if manifest.get('schema_version') != 1 or manifest.get('entry') != 'article.md':
        raise ValueError('不支持的 manifest 格式')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', manifest.get('slug', '')):
        raise ValueError('slug 仅支持小写英文、数字和连字符，最长80字符')
    title = manifest.get('title', '')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 64:
        raise ValueError('标题须为1至64字符')
    markdown = files['article.md'].decode('utf-8')
    if not markdown.strip() or len(files['article.md']) > 500_000:
        raise ValueError('正文为空或超过500KB')
    refs = image_refs(markdown)
    cover = asset_path(manifest['cover'])
    for name in set(refs + [cover]):
        if name not in files:
            raise ValueError(f'缺少图片：{name}')
        with Image.open(io.BytesIO(files[name])) as im:
            if im.format not in ('JPEG', 'PNG') or im.width * im.height > 40_000_000:
                raise ValueError('仅支持不超过4000万像素的JPEG/PNG图片')
            im.verify()
        limit = 2_000_000 if name == cover else 1_000_000
        if len(files[name]) > limit:
            raise ValueError(f'图片过大：{name}（正文1MB、封面2MB）')
    expected = set(refs + [cover, 'article.md'])
    if set(files) != expected:
        raise ValueError('内容包包含未引用文件')
    return markdown, refs, cover

def read_package(data, max_unpacked=100 * 1024**2, max_files=100):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries = z.infolist()
        if len(entries) > max_files or sum(x.file_size for x in entries) > max_unpacked:
            raise ValueError('解压大小或文件数超限')
        files = {}
        for item in entries:
            name = asset_path(item.filename)
            mode = item.external_attr >> 16
            if name in files or item.is_dir() or stat.S_ISLNK(mode) or item.flag_bits & 1:
                raise ValueError('不允许重复路径、目录、链接或加密文件')
            files[name] = z.read(item)
        manifest = json.loads(files.pop('manifest.json'))
        markdown, refs, cover = validate(manifest, files)
        digest = hashlib.sha256()
        digest.update(json.dumps(manifest, sort_keys=True).encode())
        for name, value in sorted(files.items()):
            digest.update(name.encode() + b'\0' + hashlib.sha256(value).digest())
        return manifest, files, markdown, refs, cover, digest.hexdigest()

def build_package(directory, output, commit=''):
    root = Path(directory).resolve()
    if root.name.startswith('.') or (root / 'article.md').is_symlink():
        raise ValueError('不允许隐藏目录或符号链接')
    markdown = (root / 'article.md').read_text(encoding='utf-8')
    meta_file = root / 'meta.json'
    if meta_file.is_symlink():
        raise ValueError('不允许符号链接')
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    heading = re.search(r'^#\s+(.+)$', markdown, re.M)
    manifest = {'schema_version': 1, 'slug': root.name, 'source': 'github',
                'git_commit': commit, 'title': meta.get('title') or (heading[1] if heading else root.name),
                'entry': 'article.md', 'cover': meta.get('cover', 'cover.jpg')}
    files = {'article.md': markdown.encode()}
    for name in set(image_refs(markdown) + [asset_path(manifest['cover'])]):
        path = root / name
        if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
            raise ValueError('不允许符号链接或目录逃逸')
        files[name] = path.read_bytes()
    validate(manifest, files)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
        for name, content in files.items():
            z.writestr(name, content)
    return out
