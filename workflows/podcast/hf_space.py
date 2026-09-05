"""Qwen Space adapter. No model weights or HF credentials are stored in outputs."""
import asyncio
import hashlib
import os
from pathlib import Path
import re
import tempfile

SPACE = 'Qwen/Qwen3-TTS'
API = '/generate_voice_clone'
ADAPTER_VERSION = 1


def validate(voice):
    allowed = {'provider', 'voice', 'rate', 'reference_audio', 'reference_text', 'model_size', 'language'}
    if set(voice) - allowed or voice.get('voice') != SPACE:
        raise ValueError(f'hf-space 目前仅支持 voice: {SPACE}')
    for field in ('reference_audio', 'reference_text'):
        if not isinstance(voice.get(field), str) or not voice[field].strip():
            raise ValueError(f'hf-space 缺少 {field}')
    if len(voice['reference_text']) > 2000:
        raise ValueError('reference_text 超过 2000 字符')
    if voice.get('model_size', '0.6B') not in ('0.6B', '1.7B'):
        raise ValueError('model_size 只能为 0.6B 或 1.7B')
    if voice.get('language', 'Chinese') not in ('Chinese', 'English', 'Auto', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'):
        raise ValueError('不支持的 language')
    value = voice['reference_audio']
    if Path(value).is_absolute() or '..' in Path(value).parts or not value.startswith('assets/podcast/voices/'):
        raise ValueError('reference_audio 必须是 assets/podcast/voices/ 内的仓库相对路径')


def split_text(text, limit=180):
    """Keep punctuation and all characters; bound requests to the demo runtime."""
    parts, current = [], ''
    for piece in re.findall(r'[^。！？!?；;\n]+[。！？!?；;\n]*|[。！？!?；;\n]+', text):
        while piece:
            take, piece = piece[:limit], piece[limit:]
            if len(current) + len(take) > limit:
                parts.append(current)
                current = ''
            current += take
    if current:
        parts.append(current)
    return parts


def prepare(voice, root, probe, offline=False):
    validate(voice)
    path = (root / voice['reference_audio']).resolve()
    base = (root / 'assets/podcast/voices').resolve()
    if not path.is_relative_to(base):
        raise ValueError('参考录音路径越界')
    if not path.is_file():
        if offline:
            return None
        raise ValueError(f'缺少参考录音: {voice["reference_audio"]}；请按 HF_SPACE.md 配置')
    if path.suffix.lower() not in ('.wav', '.mp3', '.m4a', '.flac', '.ogg') or path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('参考录音须为 wav/mp3/m4a/flac/ogg，且不超过 10 MB')
    if not 3 <= probe(path) <= 30:
        raise ValueError('参考录音须为 3–30 秒清晰单人录音')
    return {'path': path, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'adapter_version': ADAPTER_VERSION}


class HFSpaceProvider:
    def __init__(self, voice, reference, client_factory=None):
        self.voice, self.reference = voice, reference
        self.client_factory = client_factory
        self.client = None

    def _generate(self, text, output, run, valid_audio):
        # Anonymous access is deliberately disabled: use the user's own quota.
        if not os.environ.get('HF_TOKEN'):
            raise ValueError('缺少 HF_TOKEN：请在 GitHub Actions Secrets 添加 HF_TOKEN；Edge 和离线校验不需要它')
        try:
            from gradio_client import Client, handle_file
            with tempfile.TemporaryDirectory(prefix='hf-podcast-') as folder:
                if self.client is None:
                    factory = self.client_factory or Client
                    self.client = factory(SPACE, token=os.environ['HF_TOKEN'], verbose=False, analytics_enabled=False, httpx_kwargs={'timeout': 30})
                job = self.client.submit(
                    ref_audio=handle_file(str(self.reference['path'])),
                    ref_text=self.voice['reference_text'], target_text=text,
                    language=self.voice.get('language', 'Chinese'), use_xvector_only=False,
                    model_size=self.voice.get('model_size', '0.6B'), api_name=API,
                )
                try:
                    result = job.result(timeout=240)
                except TimeoutError:
                    job.cancel()
                    raise ValueError('HF Space 排队或生成超时；已保留完成片段，请稍后重试') from None
                if not isinstance(result, (tuple, list)) or len(result) < 2 or not result[0]:
                    raise ValueError('HF Space 没有返回音频')
                if str(result[1]).lower().startswith('error'):
                    raise ValueError('HF Space 返回生成失败')
                source = Path(result[0])
                if not source.is_file() or not valid_audio(source):
                    raise ValueError('HF Space 返回无效音频')
                factor = 1 + int(self.voice.get('rate', '+0%')[:-1]) / 100
                run('ffmpeg', '-y', '-i', source, '-af', f'atempo={factor}', '-ar', '24000', '-ac', '1', '-c:a', 'libmp3lame', '-b:a', '128k', output)
                if not valid_audio(output):
                    raise ValueError('克隆音频转换失败')
        except Exception as exc:
            # Do not echo remote exceptions, which may contain tokens or uploaded paths.
            output.unlink(missing_ok=True)
            message = str(exc).lower()
            if 'quota' in message or 'zerogpu' in message or 'gpu quota' in message:
                raise ValueError('HF ZeroGPU 额度不足或资源不可用；已保留完成片段，不自动重试或切换声音') from None
            if isinstance(exc, ValueError) and str(exc).startswith(('HF Space', '克隆音频')):
                raise ValueError(str(exc)) from None
            raise ValueError('HF Space 调用失败：请检查 Token 权限、Space 状态和剩余额度；不会自动切换声音，已保留完成片段') from None

    async def synthesize(self, text, output, run, valid_audio):
        await asyncio.to_thread(self._generate, text, output, run, valid_audio)
