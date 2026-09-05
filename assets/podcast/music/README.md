# 播客音乐素材

将你有使用权的 MP3、WAV、M4A、FLAC 或 OGG 上传到本目录，可建子目录。每个文件不超过 50 MB。目录已收录下方三段署名许可音乐；`default` 使用程序合成的三音和弦，不是文件名称。

例如自行上传后：

- intro/tech.mp3
- background/calm.mp3
- outro/warm.mp3

MD 配置中填写相对于此目录的路径：

```yaml
intro_music: intro/tech.mp3
outro_music: outro/warm.mp3
background_music: background/calm.mp3
intro_seconds: 5
outro_seconds: 6
background_volume_db: -18
```

也可以每项填写 `none` 关闭，或 `default` 使用合成和弦。原有文稿默认片头 5 秒、片尾 6 秒、正文无背景音乐。

素材会先统一响度，再裁剪/循环到需要的时长，开始和结束淡入淡出。片头片尾与正文按顺序播放，正文音乐只铺在台词和段间停顿下；不是人声触发的自动压低（ducking）。背景音乐在统一响度后降低指定分贝，默认 -18 dB（可选 -40 到 -6）。原始音乐的响度差异大时，建议先试听。

素材文件夹上传本身不会触发配音。选定文件必须已提交到运行分支；不存在、路径越界或音频无效时会在联网配音前报错。metadata.json 记录选择和素材 SHA256。

建议同时维护 SOURCES.md，记录音乐作者、来源及使用许可。不要上传无权公开分发的音乐。

## 已收录音乐（均为原曲前 30 秒片段）

| 音乐 | 文件 | 建议用途 |
|---|---|---|
| Inspired | [kevin-macleod/inspired-30s.mp3](kevin-macleod/inspired-30s.mp3) | 明亮、舒展，片头或知识分享 |
| Carefree | [kevin-macleod/carefree-30s.mp3](kevin-macleod/carefree-30s.mp3) | 轻快活泼，开场或片尾 |
| Clean Soul | [kevin-macleod/clean-soul-30s.mp3](kevin-macleod/clean-soul-30s.mp3) | 柔和电钢琴，正文低音量背景 |

作者均为 Kevin MacLeod，CC BY 4.0；[来源与必需署名](SOURCES.md)。用途建议根据作者描述选择，使用前可点击音频下载试听。

可直接复制到本期 MD：

```yaml
intro_music: kevin-macleod/inspired-30s.mp3
background_music: kevin-macleod/clean-soul-30s.mp3
outro_music: kevin-macleod/carefree-30s.mp3
intro_seconds: 5
outro_seconds: 6
background_volume_db: -22
```

完整原曲下载链接在 SOURCES.md。30 秒片段经过淡入淡出，长节目的循环边界可能听出变化；需要长而连续的背景时可另行下载原曲并选择它。
