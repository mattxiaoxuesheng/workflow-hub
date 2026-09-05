# 命令速查与 Agent 运行协议

所有命令在安装并登录 GitHub CLI（`gh auth login`）后使用。账号须有对应仓库与 Actions 权限，工作流须已提交到默认分支 main。文稿必须已提交，CLI 不会上传本地文件。

参考：[gh workflow run](https://cli.github.com/manual/gh_workflow_run)。下列单行命令同时适用于常见 Bash / PowerShell 环境。

## 制作一期节目

```bash
gh workflow run podcast.yml -R mattxiaoxuesheng/workflow-hub --ref main -f script="inputs/podcast/demo/script.md"
```

只做离线格式检查：

```bash
gh workflow run podcast.yml -R mattxiaoxuesheng/workflow-hub --ref main -f script="inputs/podcast/demo/script.md" -f validate_only=true
```

覆盖音色并强制重做：

```bash
gh workflow run podcast.yml -R mattxiaoxuesheng/workflow-hub --ref main -f script="inputs/podcast/demo/script.md" -f voice_preset="zh-duo-female-male" -f force=true
```

| 参数 | 默认值 | 说明 |
|---|---|---|
| -R | 无 | owner/repo；在仓库内执行 gh 时可省略 |
| --ref | 默认分支 | 使用哪个分支/标签上的文稿和代码，建议 main |
| script | demo 路径 | 必填，inputs/podcast/ 内 MD 的仓库相对路径 |
| voice_preset | 空 | 空表示使用文稿配置；非空覆盖预设，人数仍需匹配 |
| validate_only | false | true 只生成 validation.json，不联网验证声音 |
| force | false | true 忽略分段缓存，重新配音 |
| request_id | 空 | 建议 Agent 提供唯一值，精确识别本次任务 |

## 精确跟踪一次运行

执行端生成新的 UUID，替换下面的 `UNIQUE_ID`，不要每次使用相同值。触发前可读取 main 的提交 SHA；触发后核对任务 headSha，防止期间 main 更新导致误认文稿版本。

```bash
gh workflow run podcast.yml -R mattxiaoxuesheng/workflow-hub --ref main -f script="inputs/podcast/demo/script.md" -f request_id="UNIQUE_ID"
gh run list -R mattxiaoxuesheng/workflow-hub --workflow podcast.yml --event workflow_dispatch --limit 30 --json databaseId,displayTitle,headSha,status,conclusion,url
```

查找 displayTitle 中含本次 UNIQUE_ID 的记录，核对 headSha，取 databaseId 作为 RUN_ID。列表可能短暂延迟，稍后重试；不要选择不匹配的“最新一条”。

```bash
gh run watch RUN_ID -R mattxiaoxuesheng/workflow-hub --exit-status
gh run view RUN_ID -R mattxiaoxuesheng/workflow-hub --json status,conclusion,url,headSha
gh run download RUN_ID -R mattxiaoxuesheng/workflow-hub --dir ./podcast-output/RUN_ID
```

失败时：

```bash
gh run view RUN_ID -R mattxiaoxuesheng/workflow-hub --log-failed
```

上传新的文稿版本后应发起新的 workflow run；重跑旧 run 使用的是旧版本。只有 conclusion 为 success 且产物包含 episode.mp3 才算完成制作。validate_only 成功不代表有音频。

## 音色目录与试听

仅更新中文目录：

```bash
gh workflow run podcast-voices.yml -R mattxiaoxuesheng/workflow-hub -f locale=zh -f sample=""
```

生成两个音色的试听：

```bash
gh workflow run podcast-voices.yml -R mattxiaoxuesheng/workflow-hub -f locale=zh -f sample="zh-CN-XiaoxiaoNeural,zh-CN-YunxiNeural"
```

也可在本地执行：

```bash
python workflows/podcast/podcast.py voices --locale zh --output output/voices
python workflows/podcast/podcast.py voices --sample "zh-CN-XiaoxiaoNeural,zh-CN-YunxiNeural" --output output/voices
```

## 本地校验与制作

需要 Python 3.10+，生成/音频检查还需要 ffmpeg 和 ffprobe。

```bash
python -m pip install -r workflows/podcast/requirements.txt
python workflows/podcast/podcast.py build --script inputs/podcast/demo/script.md --validate-only
python workflows/podcast/podcast.py build --script inputs/podcast/demo/script.md --output output/demo
python workflows/podcast/podcast.py build --help
```

## 插件通过 GitHub API 执行

具备相应能力的插件可调用：

`POST /repos/mattxiaoxuesheng/workflow-hub/actions/workflows/podcast.yml/dispatches`

JSON 请求体：

```json
{
  "ref": "main",
  "inputs": {
    "script": "inputs/podcast/demo/script.md",
    "voice_preset": "",
    "validate_only": "false",
    "force": "false",
    "request_id": "本次唯一标识"
  }
}
```

读取运行列表并按 request_id 和 head_sha 确认任务。插件缺少 POST/Actions 权限时不能靠只读 fetch 工具触发，应改由有权限的 CLI 或 GitHub 网页操作。

## 覆盖本期音乐选择

先把自有素材上传至 assets/podcast/music/。以下示例文件名需自行上传；程序不会联网下载音乐。

```bash
gh workflow run podcast.yml -R mattxiaoxuesheng/workflow-hub -f script="inputs/podcast/demo/script.md" -f intro_music="intro/tech.mp3" -f outro_music="outro/warm.mp3" -f background_music="background/calm.mp3"
```

三个新参数均可选：留空沿用文稿；default 合成和弦；none 关闭；其他值是素材相对路径。网页 Run workflow 也有这三个输入框。

不需上传文件即可试用合成背景音乐：

```bash
gh workflow run podcast.yml -R mattxiaoxuesheng/workflow-hub -f script="inputs/podcast/demo/script.md" -f background_music=default
```

本地参数用连字符：

```bash
python workflows/podcast/podcast.py build --script inputs/podcast/demo/script.md --intro-music intro/tech.mp3 --outro-music none --background-music background/calm.mp3
```

intro_seconds、outro_seconds、background_volume_db 在 MD 中设定，不额外增加 Actions 输入。工作流同时支持 workflow_call，可由其他已授权的工作流传入相同参数调用。
