#!/usr/bin/env python3
"""Deterministic Markdown-to-podcast CLI. No language-model calls."""
import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave

import yaml

HERE = Path(__file__).resolve().parent
VERSION = '1.0.0'

class UniqueLoader(yaml.SafeLoader):
    pass

def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, (str, int)) or key in result:
            raise ValueError(f'配置键重复或无效: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result

UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def safe_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'路径超出允许目录: {value}')
    return path

def parse_script(path, override=''):
    if path.stat().st_size > 200_000:
        raise ValueError('文稿超过 200 KB，请拆分节目')
    raw = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
    match = re.fullmatch(r'---\n(.*?)\n---\n(.*)', raw, re.S)
    if not match:
        raise ValueError('文稿必须以 YAML 配置区开始，前后各一行 ---')
    cfg = yaml.load(match[1], Loader=UniqueLoader)
    if not isinstance(cfg, dict):
        raise ValueError('配置区必须是键值表')
    allowed = {'schema_version', 'episode_id', 'title', 'mode', 'voice_preset', 'speakers', 'intro_music', 'outro_music', 'gap_ms', 'background_music', 'background_volume_db', 'intro_seconds', 'outro_seconds'}
    if set(cfg) - allowed:
        raise ValueError(f'未知配置字段: {sorted(set(cfg) - allowed)}')
    if type(cfg.get('schema_version')) is not int or cfg['schema_version'] != 1:
        raise ValueError('schema_version 必须为 1')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', str(cfg.get('episode_id', ''))):
        raise ValueError('episode_id 必须是 1–64 位小写字母、数字或连字符')
    if not isinstance(cfg.get('title'), str) or not cfg['title'].strip():
        raise ValueError('title 必须是非空字符串')
    if cfg.get('mode') not in ('solo', 'duo'):
        raise ValueError('mode 必须为 solo 或 duo')
    presets = yaml.safe_load((HERE / 'presets.yaml').read_text(encoding='utf-8'))
    preset = override or cfg.get('voice_preset', '')
    if preset == 'custom':
        speakers = cfg.get('speakers')
    else:
        if 'speakers' in cfg:
            raise ValueError('自定义 speakers 时必须选择 voice_preset: custom')
        if preset not in presets:
            raise ValueError(f'未知声音预设 {preset!r}，可选: {", ".join(presets)}, custom')
        speakers = presets[preset]['speakers']
    expected = {'A'} if cfg['mode'] == 'solo' else {'A', 'B'}
    if not isinstance(speakers, dict) or set(speakers) != expected:
        raise ValueError(f'{cfg["mode"]} 必须且只能定义角色 {sorted(expected)}')
    for role, voice in speakers.items():
        if not isinstance(voice, dict) or set(voice) - {'provider', 'voice', 'rate'}:
            raise ValueError(f'角色 {role} 声音配置错误')
        if voice.get('provider') not in ('edge', 'clone'):
            raise ValueError(f'角色 {role}: provider 只能为 edge 或 clone')
        if not isinstance(voice.get('voice'), str) or not voice['voice'].strip():
            raise ValueError(f'角色 {role} 缺少 voice')
        if not re.fullmatch(r'[+-](?:[0-9]|[1-4][0-9]|50)%', voice.get('rate', '+0%')):
            raise ValueError('rate 必须为 -50% 到 +50%，包含正负号')
    gap = cfg.get('gap_ms', 350)
    if type(gap) is not int or not 0 <= gap <= 5000:
        raise ValueError('gap_ms 必须是 0–5000 的整数')
    for key in ('intro_music', 'outro_music', 'background_music'):
        default = 'none' if key == 'background_music' else 'default'
        value = cfg.get(key, default)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{key} 必须为 default、none 或素材相对路径')
    for key, default, low, high in [('intro_seconds', 5, .1, 60), ('outro_seconds', 6, .1, 60), ('background_volume_db', -18, -40, -6)]:
        value = cfg.get(key, default)
        if type(value) not in (int, float) or not low <= value <= high:
            raise ValueError(f'{key} 必须为 {low} 到 {high} 的数值')
    body = match[2]
    blocks = list(re.finditer(r'^## ([0-9]{3}) ([AB])\s*$', body, re.M))
    if not blocks or body[:blocks[0].start()].strip():
        raise ValueError('正文必须从 ## 001 A 这样的段落标题开始')
    segments, ids = [], set()
    for i, block in enumerate(blocks):
        ident, role = block.groups()
        text = body[block.end():blocks[i+1].start() if i+1 < len(blocks) else len(body)].strip()
        if ident in ids or role not in speakers:
            raise ValueError(f'段落 {ident}: 编号重复或角色未定义')
        if not text or len(text) > 4000:
            raise ValueError(f'段落 {ident}: 台词为空或超过 4000 字符')
        if re.search(r'(^\s*#|```|<!--|https?://|\[[^\]]*\]\(|^\s*[-*] |\|)', text, re.M):
            raise ValueError(f'段落 {ident}: 请仅保留口播文字，不要放标题、链接、表格或舞台注释')
        ids.add(ident)
        segments.append({'id': ident, 'role': role, 'text': text})
    if {s['role'] for s in segments} != expected:
        raise ValueError('文稿须实际使用配置中所有角色')
    if len(segments) > 200 or sum(len(s['text']) for s in segments) > 30000:
        raise ValueError('单期最多 200 段、30000 字符')
    cfg.update(voice_preset=preset, speakers=speakers, gap_ms=gap)
    return cfg, segments

def run(*args):
    subprocess.run(list(map(str, args)), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(path)], text=True).strip())

def valid_audio(path):
    try:
        return path.exists() and duration(path) > 0.02
    except (subprocess.CalledProcessError, ValueError):
        return False

async def voice_catalog():
    import edge_tts
    return await edge_tts.list_voices()

class EdgeProvider:
    async def synthesize(self, text, voice, rate, output):
        import edge_tts
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text, voice, rate=rate).save(str(output))
                if not valid_audio(output):
                    raise ValueError('语音服务返回无效音频')
                return
            except Exception:
                output.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

class CloneProvider:
    async def synthesize(self, text, voice, rate, output):
        raise ValueError('声音克隆服务尚未接入。请实现 CloneProvider 并配置服务，或改选 Edge 预设；不会自动替换声音。')

PROVIDERS = {'edge': EdgeProvider(), 'clone': CloneProvider()}

def music(path, seconds=5, ending=False):
    """Original synthesized three-note cue; no downloaded music assets."""
    sr = 24000
    notes = [392.0, 329.63, 261.63] if ending else [261.63, 329.63, 392.0]
    with wave.open(str(path), 'wb') as out:
        out.setparams((1, 2, sr, 0, 'NONE', 'not compressed'))
        buf = bytearray()
        for i in range(int(seconds * sr)):
            t = i / sr
            env = min(t / .5, 1, (seconds - t) / 1.5)
            value = sum(math.sin(2 * math.pi * f * t) for f in notes) / 3
            buf.extend(struct.pack('<h', int(value * max(0, env) * 4500)))
        out.writeframes(buf)

def resolve_music(cfg, root):
    """Resolve and verify all assets before paid/online work; hash selected bytes."""
    assets, identities = {}, {}
    base = root / 'assets/podcast/music'
    for key in ('intro_music', 'outro_music', 'background_music'):
        value = cfg.get(key, 'none' if key == 'background_music' else 'default')
        if value in ('default', 'none'):
            assets[key] = value
            identities[key] = {'selection': value}
            continue
        path = safe_path(base, value)
        if Path(value).is_absolute() or path.suffix.lower() not in ('.mp3', '.wav', '.m4a', '.flac', '.ogg'):
            raise ValueError(f'{key}: 仅允许素材目录内 mp3/wav/m4a/flac/ogg 文件')
        if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError(f'{key}: 素材不存在或超过 50 MB: {value}')
        if not valid_audio(path):
            raise ValueError(f'{key}: 素材不是有效音频: {value}')
        assets[key] = path
        identities[key] = {'selection': value, 'sha256': digest(path.read_bytes())}
    return assets, identities


def render(audio_files, cfg, output, work, assets=None):
    assets = assets or {key: cfg.get(key, 'none' if key == 'background_music' else 'default') for key in ('intro_music', 'outro_music', 'background_music')}
    clips = []
    def pcm(source, name):
        target = work / name
        run('ffmpeg', '-y', '-i', source, '-af', 'loudnorm=I=-19:TP=-2:LRA=7', '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le', target)
        return target
    def cue(key, seconds, name, gain=0):
        selected = assets[key]
        target = work / name
        source = selected
        if selected == 'default':
            source = work / (key + '-source.wav')
            music(source, max(2, seconds), key == 'outro_music')
        fade = min(1.5, seconds / 3)
        filters = f'loudnorm=I=-19:TP=-2:LRA=7,volume={gain}dB,afade=t=in:d={fade},afade=t=out:st={seconds-fade}:d={fade}'
        run('ffmpeg', '-y', '-stream_loop', '-1', '-i', source, '-t', seconds, '-af', filters, '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le', target)
        return target
    def concat(paths, name):
        listing = work / (name + '.txt')
        listing.write_text(''.join(f"file '{p.name}'\n" for p in paths), encoding='utf-8')
        target = work / name
        run('ffmpeg', '-y', '-f', 'concat', '-safe', '1', '-i', listing, '-c:a', 'pcm_s16le', target)
        return target
    for i, source in enumerate(audio_files):
        clips.append(pcm(source, f'speech-{i:03d}.wav'))
        if i < len(audio_files) - 1 and cfg['gap_ms']:
            silence = work / 'gap.wav'
            if not silence.exists():
                run('ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', str(cfg['gap_ms'] / 1000), silence)
            clips.append(silence)
    speech = concat(clips, 'speech.wav')
    if assets['background_music'] != 'none':
        bed = cue('background_music', duration(speech), 'background.wav', cfg.get('background_volume_db', -18))
        mixed = work / 'mixed.wav'
        run('ffmpeg', '-y', '-i', speech, '-i', bed, '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.891:level=false:latency=true', '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le', mixed)
        speech = mixed
    sequence = []
    if assets['intro_music'] != 'none':
        sequence.append(cue('intro_music', cfg.get('intro_seconds', 5), 'intro.wav'))
    sequence.append(speech)
    if assets['outro_music'] != 'none':
        sequence.append(cue('outro_music', cfg.get('outro_seconds', 6), 'outro.wav'))
    combined = concat(sequence, 'combined.wav')
    run('ffmpeg', '-y', '-i', combined, '-c:a', 'libmp3lame', '-b:a', '128k', '-metadata', f'title={cfg["title"]}', output)

async def build(args):
    root = Path(args.root).resolve()
    path = safe_path(root / 'inputs/podcast', str(Path(args.script).relative_to('inputs/podcast')))
    if path.suffix != '.md':
        raise ValueError('script 必须是 inputs/podcast/ 内的 .md 文件')
    cfg, segments = parse_script(path, args.voice_preset)
    for key in ('intro_music', 'outro_music', 'background_music'):
        override = getattr(args, key, '')
        if override:
            cfg[key] = override
    assets, music_info = resolve_music(cfg, root)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(json.dumps({'cfg': cfg, 'music': music_info, 'segments': segments, 'source': digest(path.read_bytes()), 'code': digest(Path(__file__).read_bytes()), 'requirements': (HERE / 'requirements.txt').read_text()}, sort_keys=True, ensure_ascii=False).encode())
    report = {'valid': True, 'episode_id': cfg['episode_id'], 'segments': len(segments), 'fingerprint': fingerprint, 'voice_availability_checked': False, 'music': music_info}
    if args.validate_only:
        write_json(output / 'validation.json', report)
        print(json.dumps(report, ensure_ascii=False))
        return
    if any(v['provider'] == 'clone' for v in cfg['speakers'].values()):
        raise ValueError('声音克隆服务尚未接入；请使用 Edge 预设。')
    catalog = await voice_catalog()
    available = {v['ShortName'] for v in catalog}
    for voice in cfg['speakers'].values():
        if voice['voice'] not in available:
            raise ValueError(f'音色不可用: {voice["voice"]}，请运行 voices 更新列表')
    cache = Path(args.cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    audio_files = []
    for i, segment in enumerate(segments):
        voice = cfg['speakers'][segment['role']]
        key = digest(json.dumps([VERSION, voice, segment['text']], sort_keys=True).encode())
        target = cache / f'{key}.mp3'
        if args.force or not valid_audio(target):
            temp = cache / f'{key}.{os.getpid()}.tmp.mp3'
            try:
                await PROVIDERS[voice['provider']].synthesize(segment['text'], voice['voice'], voice.get('rate', '+0%'), temp)
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
        audio_files.append(target)
        print(f'已完成台词 {i+1}/{len(segments)}', flush=True)
    # Stage full deliverables so a failed render cannot be mistaken for a finished episode.
    with tempfile.TemporaryDirectory(prefix='podcast-') as folder:
        work = Path(folder)
        final = work / 'episode.mp3'
        render(audio_files, cfg, final, work, assets)
        meta = {'episode_id': cfg['episode_id'], 'title': cfg['title'], 'duration_seconds': duration(final), 'fingerprint': fingerprint, 'source_commit': os.environ.get('GITHUB_SHA', ''), 'run_id': os.environ.get('GITHUB_RUN_ID', ''), 'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'voices': cfg['speakers'], 'music': music_info, 'audio_sha256': digest(final.read_bytes())}
        shutil.copyfile(final, output / 'episode.mp3')
    shutil.copyfile(path, output / 'script.md')
    write_json(output / 'script.json', {'config': cfg, 'segments': segments})
    write_json(output / 'metadata.json', meta)
    print(json.dumps(meta, ensure_ascii=False, indent=2))

async def voices(args):
    catalog = await voice_catalog()
    rows = [v for v in catalog if v.get('Locale', '').lower().startswith(args.locale.lower())]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'voices.json', {'updated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'voices': rows})
    for voice in rows:
        print(voice['ShortName'], voice.get('Gender'), voice.get('Locale'))
    if args.sample:
        names = list(dict.fromkeys(s.strip() for s in args.sample.split(',') if s.strip()))
        if len(names) > 8:
            raise ValueError('每次最多试听 8 个音色')
        available = {v['ShortName'] for v in catalog}
        if any(name not in available for name in names):
            raise ValueError('试听参数包含当前不可用的音色')
        for name in names:
            await PROVIDERS['edge'].synthesize('欢迎收听。这是一段播客音色试听。今天，我们用一个具体例子，解释人工智能如何帮助日常工作。', name, '+0%', output / f'{name}.mp3')

def main():
    parser = argparse.ArgumentParser(description='标准 MD 转播客；不调用大模型 API')
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('build', help='校验或制作一期节目')
    p.add_argument('--script', required=True, help='仓库相对路径 inputs/podcast/.../script.md')
    p.add_argument('--root', default='.')
    p.add_argument('--output', default='output')
    p.add_argument('--cache', default='.podcast-cache')
    p.add_argument('--voice-preset', default='')
    for key in ('intro-music', 'outro-music', 'background-music'):
        p.add_argument('--' + key, default='', help='覆盖文稿：default、none 或 assets/podcast/music 内相对路径')
    p.add_argument('--validate-only', action='store_true', help='只做离线结构检查，不访问语音服务')
    p.add_argument('--force', action='store_true', help='忽略分段音频缓存')
    p = commands.add_parser('voices', help='更新当前音色目录，可选生成试听包')
    p.add_argument('--locale', default='zh', help='语言地区前缀，如 zh、zh-CN、en')
    p.add_argument('--sample', default='', help='逗号分隔的音色 ID，最多 8 个')
    p.add_argument('--output', default='output')
    args = parser.parse_args()
    try:
        asyncio.run(build(args) if args.command == 'build' else voices(args))
    except (ValueError, OSError, subprocess.CalledProcessError, yaml.YAMLError) as exc:
        print(f'错误: {exc}', file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr.decode(errors='replace')[-2000:], file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
