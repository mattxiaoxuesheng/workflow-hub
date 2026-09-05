# 文稿转播客

标准 MD → 校验 → Edge TTS 分角色合成 → 统一台词响度 → 添加段间停顿与前奏片尾 → MP3。没有大模型调用，不接收已经录好的节目。

## 快速开始

1. 让外部 AI 按 [编稿提示词](WRITE_PROMPT.md) 和 [文稿规范](SCRIPT_SPEC.md) 编写 MD。
2. 上传至 `inputs/podcast/<episode_id>/script.md` 并提交到 main。此时不会配音。
3. Actions → 文档转播客 → Run workflow → 填写 script；或复制 [CLI.md](CLI.md) 的命令。
4. 成功后在运行页面 Artifacts 下载 `podcast-运行ID-尝试次数`。默认保留 30 天，请自行长期归档。

| 产物 | 内容 |
|---|---|
| episode.mp3 | 128 kbps、24 kHz、单声道节目 |
| script.md | 原始文稿 |
| script.json | 实际解析的角色、台词和生效配置 |
| metadata.json | 标题、时长、音色、文稿版本、任务 ID、音频校验值 |
| validation.json | 仅 validate-only 模式生成的离线校验结果 |

前奏为 5 秒、片尾为 6 秒，使用程序原创合成的三音和弦短提示音乐，含淡入淡出；位于口播前后，不在台词下持续铺音乐。可分别设为 none。第一版暂不支持用户音乐路径。

## 音色试听

Actions → 播客音色目录与试听。默认生成晓晓、云希试听；可填入逗号分隔的其他音色 ID，最多 8 个。sample 留空则只获取目录。输出 voices.json 与试听 MP3，不自动写回仓库种子目录。

Edge TTS 使用在线服务、无需 API Key，但需要联网，可能限流或不可用；失败会重试三次，不保证永久免费或服务稳定。在线验证失败不会换成其他音色。初次部署建议先运行 demo 验证所在网络可用。源码：[edge-tts](https://github.com/rany2/edge-tts)。

## Docker / 轻量服务器

仓库根目录执行：

```bash
docker build -f workflows/podcast/Dockerfile -t workflow-hub-podcast .
docker run --rm -v "$PWD:/workspace" workflow-hub-podcast build --script inputs/podcast/demo/script.md
```

上面是 Linux Bash 写法，产物在 output，缓存在 .podcast-cache。容器需要访问在线语音服务，不需要 GPU。默认 CLI 是一次性批处理程序，并非 HTTP 上传服务；未来可以在外层增加鉴权与任务队列。Pages 可另行展示已生成音频，不能运行此 Docker。

## 缓存与限制

按台词和声音配置缓存分段 MP3，每段读取前用 ffprobe 检查可解码和时长。缓存仅是加速，可能被 GitHub 淘汰。force 跳过缓存并重新生成。源码合成逻辑改变时提升 VERSION 以失效分段缓存。

Actions 按分支恢复最近保存的缓存；并发不同节目可能影响下一次可复用的缓存覆盖范围，但不会改变生成内容。相同路径的节目串行执行，等待队列行为遵循 GitHub concurrency，不能视为无限任务队列。容器输出用户可指定独立目录，避免本地并行任务写同一个 output。

## 克隆扩展接口

`podcast.py` 的 `CloneProvider.synthesize(text, voice, rate, output)` 是预留接口，输出必须是 ffprobe 可读的音频。接入时实现对应服务、显式读取服务密钥，并替换 build 中 clone 的未配置检查。`voice` 表示该服务注册后的声音 ID；参考录音上传和声音注册应由服务适配层处理。没有任何声音克隆功能被默认启用。

## 验证

```bash
python -m pip install -r workflows/podcast/requirements.txt
python -m unittest discover -s workflows/podcast/tests -v
python workflows/podcast/podcast.py build --script inputs/podcast/demo/script.md --validate-only
```

音频渲染测试需要 ffmpeg 与 ffprobe。程序检查工作流仅对源码/配置变化执行离线测试，不对 inputs 上传配音。真实 Edge 连通性需显式运行制作或试听验证。
