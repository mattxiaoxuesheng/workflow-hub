# Hugging Face 声音克隆

已接入 Qwen/Qwen3-TTS 的 /generate_voice_clone。无需下载模型或自有 GPU。CosyVoice/F5 的接口不同，本次未接入，不能只替换 Space 名称使用。旧 provider: clone 继续报未接入；新配置必须使用 provider: hf-space。

## 准备

1. GitHub 仓库 Settings → Secrets and variables → Actions → New repository secret，名称 HF_TOKEN。保存 Hugging Face 用户访问令牌，不写入文稿、源码或命令行参数。尚未添加时，Edge 和离线校验可用，实际克隆会明确失败。
2. 准备参考录音与准确文字，参考文件放 assets/podcast/voices/。详见该目录 README；公开仓库提交会公开录音。非公开素材可在本地挂载后运行。
3. 复制 templates/hf-duo.md 为 inputs/podcast/<episode_id>/script.md，修改参考文件名和文字、节目 ID、台词和音乐。模板是示意，未包含真人声音。

## 角色字段

| 字段 | 值／含义 |
|---|---|
| provider | hf-space |
| voice | Qwen/Qwen3-TTS，当前固定支持这一个 Space |
| reference_audio | assets/podcast/voices/ 内的仓库相对路径，3–30 秒、最多 10 MB |
| reference_text | 录音的准确文字，必填、最多 2000 字符 |
| model_size | 字符串 "0.6B"（默认）或 "1.7B" |
| language | Chinese（默认），或模型支持语言／Auto |
| rate | 默认 +0%，范围 -50% 到 +50%；HF 音频生成后用 FFmpeg 调速 |

单人：mode: solo，只保留 speakers.A，所有台词使用 A。双人：保留 A/B。混合：任一角色改成 provider: edge、voice: zh-CN-XiaoxiaoNeural、rate: '+0%'，删除该角色全部参考声音字段。

## 命令

离线检查（不需要 Secret、不会请求 HF；缺少参考文件在 validation.json 标记 missing，不代表可以配音）：

```bash
python workflows/podcast/podcast.py build --script inputs/podcast/my-episode/script.md --validate-only
```

上传配置和必要参考录音后，手动制作（自行替换路径和唯一任务标识）：

```bash
gh workflow run podcast.yml -R mattxiaoxuesheng/workflow-hub --ref main -f script="inputs/podcast/my-episode/script.md" -f request_id="my-episode-hf-001"
```

参数说明、查询和下载命令见 CLI.md。无需新增 Actions 的模型参数，读取 MD 的角色配置即可。force=true 会重新消耗 GPU，不建议常用。

本地 Docker（先在终端环境配置 HF_TOKEN，勿将实际 Token 写入命令示例）：

```bash
docker build -f workflows/podcast/Dockerfile -t workflow-hub-podcast .
docker run --rm -e HF_TOKEN -v "${PWD}:/workspace" workflow-hub-podcast build --script inputs/podcast/my-episode/script.md
```

通过可复用工作流调用时，调用方 job 还需传递 Secret：

```yaml
jobs:
  podcast:
    uses: ./.github/workflows/podcast.yml
    with:
      script: inputs/podcast/my-episode/script.md
    secrets:
      HF_TOKEN: ${{ secrets.HF_TOKEN }}
```

## 运行与限制

每段自动拆成最多 180 字符的小段、顺序调用；小段间使用 gap_ms 停顿。单次等待上限 240 秒，Space 本身另有 GPU 时长限制；长段失败可手动进一步拆短。零样本克隆不需要训练。短参考录音随请求提交，HF 客户端可复用上传缓存。

每个成功小段立即写入 .podcast-cache，key 包含文字、角色配置、模型大小、适配器版本和参考录音 SHA256。改变参考音频会重新生成。额度耗尽或其他错误均停止，不自动换音色或反复请求；Actions 即使失败也保存已完成缓存。

离线校验不验证 Token、远程额度和模型在线状态。HF-only 不调用 Edge 音色目录；混合模式只检查 Edge 角色。远程错误不原样打印，避免泄漏 Token。不要将参考音频或密钥写入日志。

输出仍是 output/episode.mp3、metadata.json、script.json、script.md，Actions 上传 artifact，保留 30 天；不自动提交音频到仓库。metadata 包含参考录音散列及配置，不包含 HF_TOKEN 或录音本身。

ZeroGPU 免费额度、队列优先级可能调整，以 [官方规则](https://huggingface.co/docs/hub/spaces-zerogpu) 为准；不同 Space 共享调用账户额度。此次接入先通过离线模拟接口测试，添加 Token 和录音后才可做真实端到端试听。
