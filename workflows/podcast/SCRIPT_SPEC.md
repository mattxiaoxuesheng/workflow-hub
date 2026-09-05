# 播客 MD 规范 v1

唯一输入格式为 UTF-8 Markdown，建议无 BOM；LF/CRLF 均可。每期存为 `inputs/podcast/<episode_id>/script.md`。完整录好的播客、Word 或 PDF 不属于本工作流文稿输入；hf-space 可另外提供短参考录音；请先在外部 AI 中完成编稿。

## YAML 配置

文件第一行必须为 `---`，配置结束后再放一行 `---`。见 [完整双人样板](templates/duo.md)。不接受未知字段和重复键。

| 字段 | 必填 | 规则 |
|---|---|---|
| schema_version | 是 | 整数 1 |
| episode_id | 是 | 1–64 位小写字母、数字、连字符，第一位字母或数字 |
| title | 是 | 非空标题，建议加引号 |
| mode | 是 | solo 或 duo |
| voice_preset | 是 | presets.yaml 中预设名称，或 custom |
| speakers | custom 时 | solo 仅 A；duo 必须且只能 A、B；普通预设不要填写 |
| intro_music | 否 | default（默认）、none 或音乐素材相对路径 |
| outro_music | 否 | default（默认）、none 或音乐素材相对路径 |
| gap_ms | 否 | 段间停顿，整数 0–5000，默认 350 |

`custom` 的每个角色必须有 `provider` 和 `voice`；可选 `rate`（如 `'+0%'`、`'-5%'`，范围 -50% 到 +50%）。provider 支持 edge、hf-space（详见 [克隆接入说明](HF_SPACE.md)）；clone 只允许结构校验，实际生成会报“尚未接入”，不会替换声音。参见 [自定义样板](templates/custom.md)。

## 台词段落

每段标题严格为 `## 001 A`：三个数字、空格、角色。编号唯一，推荐从 001 递增；程序按文稿出现顺序播放。双人必须实际使用 A 和 B，单人只能使用 A。

段落正文只放完整口播文字。不要包含新的标题、代码块、HTML 注释、链接、表格、列表或舞台提示。不要把“音乐响起”“此处展开”“略”等写进台词。标题与配置不会被朗读，正文中的任何其他文字会被朗读。

- 外部 AI 必须写好开场、正文、总结和结束语。程序不会补写、纠错或核实事实。
- 每段 1–4000 字符，每期最多 200 段、30000 字符，文件不超过 200 KB。
- 数字与缩写按听觉理解需要处理，例如“三点五个百分点”。不要为了凑时长编造内容。
- 时长为编稿目标，生成后 metadata.json 提供实际秒数，不自动压缩或改写。
- 引用资料不要混入口播正文；可另存一期目录中的 sources.md，程序不会读取。

## 声音选择

先用 presets.yaml 的三种常用预设。需要其他声音时，运行音色目录/试听工作流，查看实时 voices.json 并听样例，再使用 custom 配置。内置 voices.json 是手选种子列表，不代表实时完整目录；不宣称具有特定情绪或播音风格。

配置优先级：CLI 非空 voice_preset > 文稿 voice_preset > 预设内的角色配置。覆盖预设的角色数量必须匹配 mode；带 speakers 的 custom 文稿不能直接覆盖成普通预设，请先移除 speakers。

离线 validate-only 只做结构校验，不检查远程音色是否在线。实际生成会联网校验音色，无效时直接报错。

## 选择片头、片尾及正文背景音乐

音乐文件统一放在 `assets/podcast/music/`，字段只填相对于该目录的路径，不接受 URL 或绝对路径。支持 mp3/wav/m4a/flac/ogg，单文件最多 50 MB。三项独立选择：

```yaml
intro_music: intro/tech.mp3
outro_music: outro/warm.mp3
background_music: background/calm.mp3
intro_seconds: 5
outro_seconds: 6
background_volume_db: -18
```

上面是上传自有素材后的示意文件名，不是内置文件。`default` 是合成三音和弦；`none` 关闭该项。background_music 默认 none，旧文稿继续支持。intro_seconds / outro_seconds 为 0.1–60 秒；background_volume_db 为 -40 到 -6 dB，默认 -18。

文件会循环/裁剪到需要长度，并淡入淡出。背景音乐只覆盖正文（包括段间停顿），不会延长正文；片头片尾额外增加节目总时长。三项音乐选择都可由 CLI/Actions 覆盖，空值沿用 MD，none 表示明确关闭。时长和音量在 MD 中设置。

选择自有素材时，离线校验也需要 ffprobe 检查文件；不存在或无效时在 TTS 前失败。见 [素材目录说明](../../assets/podcast/music/README.md)。
