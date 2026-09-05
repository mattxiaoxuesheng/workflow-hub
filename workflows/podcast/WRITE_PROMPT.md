# 复制给外部 AI 的编稿提示词

请先读取此仓库 `workflows/podcast/SCRIPT_SPEC.md`、`presets.yaml` 和对应模板，然后根据我提供的材料制作完整标准播客 MD。

要求：
- 先遵守我明确指定的主题、单人/双人、时长和声音；未指定时采用中文双人、约 8 分钟、zh-duo-female-male。
- 内容基于我提供的材料，通俗、适合听；双人由 A 引导提问、B 解释举例，避免机械轮流朗读。
- 写齐开场、正文、总结与结束语，不留占位文字，不补造数据或来源。
- 输出严格符合 SCRIPT_SPEC.md 的 YAML 配置与 ## 001 A 段落格式，正文仅含要读出的台词。
- 保留 schema_version: 1；创建有意义且唯一的 episode_id。
- 配置 intro_music: default、outro_music: default、gap_ms: 350；不把音乐或动作提示写入台词。
- 生成前奏片尾是程序职责，不需编写音乐描述。
- 如具备 GitHub 写入能力，读取目标是否存在后，将 MD 提交至 inputs/podcast/<episode_id>/script.md；否则提供完整 MD 并说明未上传。
- 先上传，默认不运行音频制作。只有我要求生成时才读取 CLI.md 并触发 Actions，跟踪对应 run ID。

用户要求配乐时，先读取 assets/podcast/music/README.md 并查看实际文件列表，只选择已存在且可使用的素材。分别设置 intro_music、outro_music、background_music；不编造文件名。用户未指定时 background_music: none。

## Hugging Face 声音克隆

hf-space 已支持 Qwen 官方 Space，单人、双人或与 Edge 混合使用。需要 HF_TOKEN 和短参考录音；上传文稿不自动生成。配置、Secret 和命令见 [HF_SPACE.md](HF_SPACE.md)。旧 clone provider 仍为占位。
