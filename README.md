# Workflow Hub

面向人和 AI Agent 的可扩展工作流仓库。每项工作流独立保存规范、样板、运行说明与 Docker 程序。

| 工作流 | 功能 | 入口 |
|---|---|---|
| 文稿转播客 | 标准 MD → 单人或双人 MP3，含前奏片尾；无需大模型 API | [播客说明](workflows/podcast/README.md) |

## 给 ChatGPT / Codex 的提示词

> 请读取本仓库 AGENTS.md 及播客 SCRIPT_SPEC.md，使用我提供的材料，在当前对话中编写完整播客文稿。采用中文双人预设，上传至 inputs/podcast/节目ID/script.md。先不要启动音频制作。需要运行时，读取 CLI.md 并按说明触发 Actions、追踪本次任务和提供下载链接。

- AI 入口：[AGENTS.md](AGENTS.md)
- 文稿规范：[SCRIPT_SPEC.md](workflows/podcast/SCRIPT_SPEC.md)
- 命令速查：[CLI.md](workflows/podcast/CLI.md)
- 外部 AI 编稿提示词：[WRITE_PROMPT.md](workflows/podcast/WRITE_PROMPT.md)
- [单人样板](workflows/podcast/templates/solo.md) / [双人样板](workflows/podcast/templates/duo.md) / [自定义音色样板](workflows/podcast/templates/custom.md)
- [制作播客](https://github.com/mattxiaoxuesheng/workflow-hub/actions/workflows/podcast.yml) / [试听音色](https://github.com/mattxiaoxuesheng/workflow-hub/actions/workflows/podcast-voices.yml)

**上传文稿不会自动配音。** 音频制作与音色试听都需手动触发。修改程序会运行离线测试，不会调用 TTS。

本仓库为公开仓库：提交的文稿可公开读取。Edge 配音会把台词发送给在线语音服务；需要保密的材料请使用合适的私有存储与语音方案。

## Hugging Face 声音克隆

hf-space 已支持 Qwen 官方 Space，单人、双人或与 Edge 混合使用。需要 HF_TOKEN 和短参考录音；上传文稿不自动生成。配置、Secret 和命令见 [workflows/podcast/HF_SPACE.md](workflows/podcast/HF_SPACE.md)。旧 clone provider 仍为占位。

[仓库架构图](ARCHITECTURE.md)
