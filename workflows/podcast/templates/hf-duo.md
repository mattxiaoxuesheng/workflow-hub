---
schema_version: 1
episode_id: hf-duo-demo
title: "双人克隆播客"
mode: duo
voice_preset: custom
speakers:
  A:
    provider: hf-space
    voice: Qwen/Qwen3-TTS
    reference_audio: assets/podcast/voices/host-a.wav
    reference_text: "请替换为甲参考录音实际朗读的全部文字。"
    model_size: "0.6B"
    language: Chinese
    rate: "+0%"
  B:
    provider: hf-space
    voice: Qwen/Qwen3-TTS
    reference_audio: assets/podcast/voices/host-b.wav
    reference_text: "请替换为乙参考录音实际朗读的全部文字。"
    model_size: "0.6B"
    language: Chinese
    rate: "+0%"
intro_music: kevin-macleod/inspired-30s.mp3
outro_music: kevin-macleod/carefree-30s.mp3
background_music: kevin-macleod/clean-soul-30s.mp3
background_volume_db: -22
gap_ms: 350
---

## 001 A

欢迎收听本期节目。今天，我们聊聊如何把一篇文稿制作成播客。

## 002 B

先写好每个角色的台词，再选择声音。程序会逐段朗读，加入音乐，最后合成音频。

## 003 A

感谢收听，我们下期再见。
