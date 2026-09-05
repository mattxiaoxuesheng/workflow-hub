import asyncio
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import podcast

class PodcastTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / 'script.md'
        self.template = (podcast.HERE / 'templates/duo.md').read_text()
        self.path.write_text(self.template)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_templates(self):
        for path in (podcast.HERE / 'templates').glob('*.md'):
            cfg, segments = podcast.parse_script(path)
            self.assertGreater(len(segments), 1)
            self.assertEqual(set(s['role'] for s in segments), set(cfg['speakers']))

    def test_bad_scripts_rejected(self):
        for old, new in [('## 002 B', '## 001 B'), ('## 002 B', '## 002 C'), ('gap_ms: 350', 'gap_ms: -1'), ('mode: duo', 'mode: solo'), ('schema_version: 1', 'schema_version: 1\nschema_version: 1'), ('gap_ms: 350', 'unknown: 1'), ('欢迎收听本期节目。', '<!-- music -->')]:
            with self.subTest(new=new):
                self.path.write_text(self.template.replace(old, new))
                with self.assertRaises(ValueError):
                    podcast.parse_script(self.path)

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            podcast.safe_path(self.root, '../secret.md')
        outside = self.root.parent / 'outside-podcast-test.md'
        link = self.root / 'link'
        link.symlink_to(outside)
        with self.assertRaises(ValueError):
            podcast.safe_path(self.root, 'link')

    def test_clone_never_silently_falls_back(self):
        with self.assertRaisesRegex(ValueError, '尚未接入'):
            asyncio.run(podcast.CloneProvider().synthesize('你好', 'my-voice', '+0%', self.root / 'test.mp3'))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires ffmpeg')
    def test_render_and_offline_build(self):
        # Fake synthesis only: test real FFmpeg assembly, cache reuse and output provenance.
        from argparse import Namespace
        script = self.root / 'inputs/podcast/demo/script.md'
        script.parent.mkdir(parents=True)
        script.write_text(self.template)
        args = Namespace(root=str(self.root), script='inputs/podcast/demo/script.md', voice_preset='', output=str(self.root / 'output'), cache=str(self.root / 'cache'), validate_only=False, force=False)
        calls = []
        async def fake_voices():
            return [{'ShortName': 'zh-CN-XiaoxiaoNeural'}, {'ShortName': 'zh-CN-YunxiNeural'}]
        async def fake_tts(text, voice, rate, output):
            calls.append(text)
            # WAV content is probe-detected independently of suffix.
            podcast.music(output, .3)
        with patch.object(podcast, 'voice_catalog', fake_voices), patch.object(podcast.PROVIDERS['edge'], 'synthesize', fake_tts):
            asyncio.run(podcast.build(args))
            self.assertEqual(len(calls), 3)
            final = self.root / 'output/episode.mp3'
            meta = json.loads((self.root / 'output/metadata.json').read_text())
            self.assertAlmostEqual(meta['duration_seconds'], 12.6, delta=.4)
            self.assertEqual(meta['audio_sha256'], podcast.digest(final.read_bytes()))
            asyncio.run(podcast.build(args))
            self.assertEqual(len(calls), 3)
            # Corrupt one cached audio; it must be regenerated.
            next((self.root / 'cache').glob('*.mp3')).write_bytes(b'broken')
            asyncio.run(podcast.build(args))
            self.assertEqual(len(calls), 4)
            args.force = True
            asyncio.run(podcast.build(args))
            self.assertEqual(len(calls), 7)

if __name__ == '__main__':
    unittest.main()
