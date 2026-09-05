import asyncio
from argparse import Namespace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import podcast
import hf_space


class HFTests(unittest.TestCase):
    def test_split_preserves_text(self):
        text = '你好。' + '测试' * 300 + '\n再见！'
        chunks = hf_space.split_text(text)
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(0 < len(c) <= 180 for c in chunks))

    def test_hf_build_cache_and_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / 'inputs/podcast/demo/script.md'
            script.parent.mkdir(parents=True)
            text = (podcast.HERE / 'templates/hf-duo.md').read_text()
            for name in ('intro_music', 'outro_music', 'background_music'):
                import re
                text = re.sub(rf'^{name}:.*$', f'{name}: none', text, flags=re.M)
            script.write_text(text)
            args = Namespace(root=str(root), script='inputs/podcast/demo/script.md', voice_preset='', output=str(root/'output'), cache=str(root/'cache'), validate_only=True, force=False)
            with patch.dict(os.environ, {}, clear=True):
                asyncio.run(podcast.build(args))
                report = json.loads((root/'output/validation.json').read_text())
                self.assertTrue(report['reference_audio']['A']['missing'])
                for role in ('a', 'b'):
                    p = root / f'assets/podcast/voices/host-{role}.wav'
                    p.parent.mkdir(parents=True, exist_ok=True)
                    podcast.music(p, 3.1)
                args.validate_only = False
                with self.assertRaisesRegex(ValueError, 'HF_TOKEN'):
                    asyncio.run(podcast.build(args))
            source = root/'generated.wav'
            podcast.music(source, .3)
            client = MagicMock()
            client.submit.return_value.result.return_value = (str(source), 'Voice clone generation completed successfully!')
            with patch.dict(os.environ, {'HF_TOKEN': 'test-secret'}), patch('gradio_client.Client', autospec=True, return_value=client) as factory, patch.object(podcast, 'voice_catalog', side_effect=AssertionError('HF must not call Edge')):
                asyncio.run(podcast.build(args))
                self.assertEqual(client.submit.call_count, 3)
                self.assertEqual(factory.call_args.kwargs['token'], 'test-secret')
                self.assertEqual(client.submit.call_args.kwargs['api_name'], '/generate_voice_clone')
                asyncio.run(podcast.build(args))
                self.assertEqual(client.submit.call_count, 3)
                podcast.music(root/'assets/podcast/voices/host-a.wav', 3.2)
                asyncio.run(podcast.build(args))
                self.assertEqual(client.submit.call_count, 5)
                meta = (root/'output/metadata.json').read_text()
                self.assertNotIn('test-secret', meta)
                args.force = True
                client.submit.side_effect = RuntimeError('quota exceeded test-secret')
                with self.assertRaisesRegex(ValueError, '额度') as exc:
                    asyncio.run(podcast.build(args))
                self.assertNotIn('test-secret', str(exc.exception))
                self.assertTrue(list((root/'cache').glob('*.mp3')))

    def test_paths_and_provider_rejected(self):
        voice = {'provider':'hf-space', 'voice':hf_space.SPACE, 'reference_audio':'assets/podcast/voices/a.wav', 'reference_text':'你好'}
        for update in ({'reference_audio':'../secret.wav'}, {'voice':'someone/other-space'}, {'reference_text':''}, {'model_size':'99B'}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                hf_space.validate({**voice, **update})
