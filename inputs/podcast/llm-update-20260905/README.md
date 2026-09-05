# 一分钟大模型进展

双人播客，时长 62.976 秒（含 5 秒前奏、6 秒片尾）。声音：A 晓晓，B 云希。

- [下载 MP3](generated/episode.mp3)：打开文件后点击 Download raw file。
- [原始文稿](script.md)
- [来源](sources.md)
- [生成记录与音频校验值](generated/metadata.json)
- [成功的 GitHub Actions 运行](https://github.com/mattxiaoxuesheng/workflow-hub/actions/runs/33938083147)

音频由仓库的 podcast.yml 通过 workflow_call 使用同一 Docker 程序生成。本次显式运行和归档使用的一次性配置已移除。普通文稿上传仍不触发配音。

重做本期：

```bash
gh workflow run podcast.yml -R mattxiaoxuesheng/workflow-hub -f script="inputs/podcast/llm-update-20260905/script.md"
```

重做后的结果在新任务的 Artifact 中，不会自动覆盖这里已经归档的音频。
