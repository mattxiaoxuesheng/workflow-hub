# 微信公众号 Publisher V2 改造方案

## 1. 改造目标

现有微信公众号 Publisher 已具备文章导入、Markdown 编辑、图片上传、模板渲染、版本管理、微信草稿、正式发布等能力，但当前编辑方式仍以 Markdown + 独立预览为主，日常编辑体验与 Word、微信公众号编辑器相比不够直观。

V2 的核心目标是将 Publisher 升级为一个完整的公众号内容编辑、排版、版本和发布系统：

- 使用 Tiptap 富文本编辑器替代当前以 CodeMirror 为主的 Markdown 编辑模式。
- 编辑区本身即为所见即所得的最终排版效果，不再设置“编辑窗口 + 实时预览窗口”双栏结构。
- 支持模板实时切换。
- 支持局部样式覆盖模板，但只作用于被修改的文字、段落、标题或图片。
- 支持局部样式一键恢复模板。
- 区分“自动保存 / 保存修改 / 保存为版本”。
- 支持直接从网页或 Android App 新建文章、上传图片、删除图片、替换图片，不再要求必须从 GitHub 导入。
- GitHub 作为可选内容来源，不再承担公众号文章上传后的 CI 流程。
- 发送微信前提供最终 HTML 预览。
- 从微信公众号取回草稿后提供微信返回版本预览与 HTML 对照。
- Android App 与网页共用同一套 Publisher UI，大多数功能升级只需重新部署服务器容器，不需要重新安装 App。

---

# 2. 总体架构

```text
                  ┌──────────────────────┐
                  │  ChatGPT / GitHub    │
                  │ Markdown + 图片      │
                  └──────────┬───────────┘
                             │ 可选导入
                             ▼

┌─────────────────────────────────────────────────────┐
│                  Publisher V2                       │
│                                                     │
│  新建文章 / 网页导入 / GitHub 导入                   │
│                     ↓                               │
│                Working Draft                        │
│                     ↓                               │
│             Tiptap 富文本编辑器                      │
│                     ↓                               │
│       CSS 模板 + 局部样式 Override 实时渲染          │
│                     ↓                               │
│       自动保存 / 保存修改 / 保存为正式版本            │
│                     ↓                               │
│                 V1 / V2 / V3                       │
│                     ↓                               │
│             生成最终微信 HTML                       │
│                     ↓                               │
│          【发送微信前最终预览】                      │
│                     ↓                               │
│             微信公众号草稿                          │
│                     ↓                               │
│          【取回微信后的最终预览】                    │
│                     ↓                               │
│                  正式发布                           │
└─────────────────────────────────────────────────────┘
```

---

# 3. 编辑器核心方案

## 3.1 使用 Tiptap

Tiptap 作为可视化富文本编辑器内核。

它负责：

- 文本编辑
- 标题
- 段落
- 粗体
- 斜体
- 下划线
- 引用
- 列表
- 链接
- 图片
- 图片说明
- 对齐
- 撤销
- 重做
- 局部样式
- 文档结构管理

Tiptap 不作为最终样式模板系统。

建议将文章保存为：

```text
Tiptap JSON
+
template_id
+
local overrides
+
working draft metadata
```

最终发布时再生成 HTML。

---

## 3.2 Tiptap 与 Markdown 的关系

Tiptap 不是 Markdown。

建议将两者定位为不同的内容输入形式：

```text
Markdown
更适合：
- AI 自动生成
- GitHub 保存
- Git diff
- 程序批量处理

Tiptap
更适合：
- 人工编辑
- 手机编辑
- 所见即所得
- 图片操作
- 撤销 / 重做
- 局部排版
```

推荐流程：

```text
ChatGPT
   ↓
Markdown + 图片
   ↓
GitHub（可选）
   ↓
Publisher
   ↓
转换为 Tiptap 文档
   ↓
人工可视化编辑
   ↓
HTML
   ↓
CSS 模板
   ↓
微信最终 HTML
```

---

# 4. 编辑页面重新设计

编辑区与渲染区合二为一。

不再采用：

```text
左侧 Markdown 编辑
右侧 HTML 实时预览
```

而是：

```text
┌─────────────────────────────────────────────────────┐
│ ← 文章列表      未来战争正在发生      已保存 22:43   │
├─────────────────────────────────────────────────────┤
│ 模板：[科技杂志 ▼]                                  │
├─────────────────────────────────────────────────────┤
│ ↶  ↷ │ B I U │ H1 H2 H3 │ 引用 │ 列表 │ 链接 │ 图片│
├─────────────────────────────────────────────────────┤
│                                                     │
│                 未来战争正在发生                     │
│                                                     │
│  2026 年，一架廉价无人机从树林上方掠过……            │
│                                                     │
│              ┌────────────────┐                     │
│              │   战争插图     │                     │
│              └────────────────┘                     │
│                                                     │
│  战争形态已经开始改变。                              │
│                                                     │
├─────────────────────────────────────────────────────┤
│ 自动保存 ✓       保存修改        保存为 V4           │
│                              发送微信草稿 →          │
└─────────────────────────────────────────────────────┘
```

编辑区本身直接套用当前 CSS 模板。

用户看到的效果应尽量接近最终公众号样式。

---

# 5. 模板系统

## 5.1 模板下拉列表

顶部提供模板选择：

```text
模板：

[ 不使用模板 ▼ ]
[ 简洁阅读      ]
[ 商务报告      ]
[ 科技杂志      ]
[ 私人银行      ]
```

现有模板可继续复用：

- Clean
- Business
- Tech

以后可继续增加：

- Private Banking
- Research Note
- AI Magazine
- Minimal
- Corporate

---

## 5.2 模板本质

模板主要由 CSS 控制。

例如：

```css
h2 {
  font-size: 24px;
  font-weight: 700;
  color: #3157d5;
  margin-top: 30px;
}

p {
  font-size: 16px;
  line-height: 1.9;
}

img {
  width: 100%;
  border-radius: 12px;
}
```

设计原则：

```text
Tiptap：
决定“这是什么”

CSS：
决定“它长什么样”
```

例如：

```text
Tiptap：
heading
paragraph
blockquote
image
bold
link
list

CSS：
字号
颜色
行距
段距
边距
图片圆角
引用框样式
```

---

# 6. 模板与局部样式冲突机制

## 6.1 核心原则

不采用全局的：

```text
模板优先
编辑优先
```

而采用：

> 全局模板 + 局部 Override

模板永远作为整个文章的基础样式。

只有用户手工修改过的某一处内容，才保存该处的局部样式。

其他未修改内容仍完全继承模板。

---

## 6.2 示例

模板：

```css
h2 {
  color: blue;
  font-size: 24px;
  margin-top: 30px;
  text-align: left;
}
```

文章中有：

```text
标题 A
标题 B
标题 C
```

只把标题 B 改成红色、居中。

最终：

```text
标题 A
color       → 模板 blue
font-size   → 模板 24px
margin-top  → 模板 30px
text-align  → 模板 left

标题 B
color       → 红色（局部 override）
font-size   → 模板 24px
margin-top  → 模板 30px
text-align  → center（局部 override）

标题 C
全部继承模板
```

局部修改绝不全局扩散。

---

## 6.3 属性级覆盖

局部 override 应精确到属性级。

例如用户只改：

```text
text-align = center
```

则：

```text
color       → 模板
font-size   → 模板
margin-top  → 模板
text-align  → center
```

公式：

```text
最终样式
=
模板样式
+
当前节点或当前文本的局部差异
```

而不是：

```text
模板样式 OR 人工样式
```

---

# 7. 恢复模板

## 7.1 自动出现恢复按钮

当用户选中：

- 某段文字
- 某个标题
- 某个段落
- 某张图片

如果该对象存在局部 override，则上下文工具栏自动显示：

```text
↺ 恢复模板
```

如果完全继承模板，则不显示该按钮。

---

## 7.2 示例

某段当前为：

```text
颜色：红色 *
字号：20px *
对齐：居中 *
```

浮动工具栏：

```text
┌─────────────────────────────────────────────┐
│ B I U │ 颜色 │ 字号 │ 对齐 │ ↺ 恢复模板    │
└─────────────────────────────────────────────┘
```

点击：

```text
↺ 恢复模板
```

删除该对象全部局部 override。

正文内容本身不变化。

---

## 7.3 单属性恢复

除“全部恢复模板”外，每一个属性也应支持单独恢复。

例如：

```text
颜色：红色        [↺]
字号：20px        [↺]
对齐：居中        [↺]

[↺ 全部恢复模板]
```

用户可以只将字号恢复模板，但保留红色与居中。

---

## 7.4 人工修改标识

建议所有局部 override 使用醒目标记：

```text
颜色 ● 红色
字号 ● 20px
对齐 ● 居中
```

或：

```text
颜色：红色 *
字号：20px *
```

明确告诉用户：

> 这是手工修改，不是模板样式。

---

# 8. 编辑样式范围

不建议允许任意 CSS。

建议允许以下局部 override：

## 文本

- 粗体
- 斜体
- 下划线
- 字号
- 文字颜色
- 背景强调
- 链接

## 段落 / 标题

- 左对齐
- 居中
- 右对齐
- 有限的段前段后设置
- 引用样式类型

## 图片

- 宽度
- 对齐
- 圆角
- 图片说明
- 替换
- 删除

不建议开放：

- position
- transform
- absolute positioning
- 任意 margin
- 任意 padding
- 自定义 HTML
- 任意 CSS 文本

避免公众号 HTML 失控。

---

# 9. 工作稿与版本系统

必须明确区分：

```text
自动保存
保存修改
保存为版本
```

三者不同。

---

## 9.1 Working Draft

每篇文章当前只能存在一个最新工作稿。

结构：

```text
Article
   ↓
Base Version V3
   ↓
Working Draft
```

工作稿可以反复修改。

---

## 9.2 自动保存

停止编辑一定时间，例如 2 秒后：

```text
编辑
↓
2 秒无输入
↓
自动保存 Working Draft
```

显示：

```text
✓ 已保存 22:46
```

自动保存不产生版本。

---

## 9.3 保存修改

点击：

```text
保存修改
```

立即把当前状态写入 Working Draft。

不产生：

```text
V4
```

用于：

- 强制保存
- 手机退出前保存
- 网络状态不稳定时确认保存

---

## 9.4 保存为版本

只有点击：

```text
保存为 V4
```

才执行：

```text
Working Draft
     ↓
冻结
     ↓
Version 4
```

正式 Version 一旦生成，不允许原地覆盖。

后续：

```text
V4
↓
Working Draft
↓
继续编辑
↓
保存为 V5
```

---

# 10. 撤销与重做

工具栏：

```text
↶ 撤销
↷ 重做
```

桌面支持：

```text
Ctrl + Z
Ctrl + Shift + Z
```

手机直接点击按钮。

作用范围：

```text
当前编辑会话
```

例如：

```text
删除一段
↓
删除图片
↓
修改一句
↓
撤销
↓
恢复修改
↓
再撤销
↓
图片恢复
```

历史版本恢复仍通过：

```text
V1 / V2 / V3
```

完成。

---

# 11. 图片管理

## 11.1 图片上传入口

支持：

- 网页选择图片
- 拖放图片
- Ctrl + V 粘贴图片
- Android App 从相册选择图片
- GitHub 导入
- ZIP / Markdown 内容包导入

GitHub 不再是唯一入口。

---

## 11.2 插入图片

光标所在位置：

```text
点击图片
↓
选择文件
↓
上传 Publisher
↓
返回素材地址
↓
插入 Tiptap 图片节点
```

---

## 11.3 图片上下文菜单

点击图片：

```text
┌─────────────────────────┐
│          图片           │
└─────────────────────────┘

替换
删除
左对齐
居中
右对齐
小图
中图
大图
满宽
图片说明
↺ 恢复模板
```

---

## 11.4 删除行为

应区分：

### 从文章中删除

只删除正文引用。

素材仍保存在服务器中。

### 从素材库永久删除

真正删除服务器图片。

应增加二次确认。

---

# 12. 新建文章

Publisher 首页增加：

```text
＋ 新建文章
```

新建时填写：

```text
标题
模板（可选）
```

创建后直接进入：

```text
Working Draft
```

不要求先创建 GitHub 文件。

---

# 13. 内容来源

V2 支持三种主要入口：

| 内容来源 | 场景 |
|---|---|
| Publisher 直接新建 | 网页 / 手机直接写 |
| Markdown / ZIP 导入 | AI 生成整篇内容 |
| GitHub 导入 | AI / Git 工作流产物 |

三种入口最终统一进入：

```text
Working Draft
```

后续编辑、模板、版本、微信发布流程完全一致。

---

# 14. GitHub 改造

## 14.1 GitHub 定位

GitHub 以后主要承担：

- AI 内容交付
- Markdown 保存
- 图片保存
- 代码版本管理
- 可选内容归档

不承担：

```text
公众号文章上传后的完整 CI
```

---

## 14.2 删除公众号内容 CI

现有：

```text
.github/workflows/wechat-ci.yml
```

不再因为：

```text
inputs/wechat/**
```

变化而运行：

- pytest
- npm build
- Docker build
- container smoke test

公众号文章内容修改不需要触发完整软件 CI。

---

## 14.3 软件 CI 与内容流分离

如果仍希望保留软件本身 CI，应只监听：

```text
publisher/**
workflows/wechat/**
deploy/**
.github/workflows/**
```

但不监听：

```text
inputs/wechat/**
```

如果决定彻底取消公众号 Publisher CI，也可删除该 workflow。

---

## 14.4 wechat-ingest.yml

原来的：

```text
微信公众号内容导入
```

不再作为主流程。

可选择：

### 方案 A

保留为人工备用导入方式。

### 方案 B

彻底移除，所有导入由 Publisher Web API 完成。

推荐长期采用方案 B。

---

# 15. 微信发送前最终预览

编辑阶段不需要单独预览窗口。

只有点击：

```text
发送微信草稿
```

后进入：

# 微信发送预览

```text
┌───────────────────────────────────────┐
│ ← 返回编辑       微信发送预览         │
├───────────────────────────────────────┤
│                                       │
│        ┌──────────────────────┐       │
│        │ 微信最终文章 HTML    │       │
│        │                      │       │
│        │ CSS 已 inline        │       │
│        │ 图片已转微信 URL     │       │
│        └──────────────────────┘       │
│                                       │
├───────────────────────────────────────┤
│ 版本：V4                              │
│ 模板：科技杂志                        │
│                                       │
│     返回修改      确认发送微信草稿     │
└───────────────────────────────────────┘
```

这里显示的应该尽可能接近：

> 真正准备提交给微信 API 的 HTML。

---

# 16. 微信图片处理

编辑期间图片可以使用 Publisher 自己的素材 URL。

发送微信草稿前：

```text
Publisher 图片
      ↓
上传微信公众号接口
      ↓
微信返回图片 URL
      ↓
替换 HTML 中图片 src
      ↓
CSS inline
      ↓
生成最终微信 HTML
      ↓
预览
      ↓
发送草稿
```

用户不需要关心微信素材地址。

---

# 17. 微信取回预览

微信创建草稿后可以：

```text
取回微信草稿
```

进入：

# 微信返回预览

默认显示：

```text
微信公众号实际保存的 HTML
```

提供三个标签：

```text
[微信返回版本]
[发送给微信版本]
[HTML 差异]
```

普通用户主要看：

```text
微信返回版本
```

高级排错时才查看：

```text
HTML 差异
```

---

# 18. 文章主页面

建议文章页顶部增加：

```text
编辑
历史版本
微信草稿
发布记录
```

文章列表：

```text
微信公众号 Publisher

＋ 新建文章        ↑ 导入文章

────────────────────────────

未来战争正在发生
V4
工作稿：有修改
2026-10-03 08:30

AI 共创实验室第二期
V7
已发布
```

---

# 19. 手机端 UI

Android App 与网页共用同一套 Publisher UI。

手机建议：

```text
┌──────────────────────────┐
│ ← 文章          已保存 ✓ │
├──────────────────────────┤
│ 模板：科技杂志 ▼         │
├──────────────────────────┤
│ ↶  ↷  B  H2  🖼  ＋     │
├──────────────────────────┤
│                          │
│       正文编辑区          │
│                          │
│       [图片]             │
│                          │
├──────────────────────────┤
│ 保存修改     保存为 V4   │
└──────────────────────────┘
```

点击：

```text
＋
```

弹出：

```text
标题
引用
列表
链接
分割线
图片
```

---

# 20. Android App 是否需要重新安装

现有 Android App 本质是：

```text
Android WebView
      ↓
https://stocklab.hardway.top/publisher/
```

因此：

```text
修改 React
修改 FastAPI
增加 Tiptap
修改数据库
重新 build Docker
重新部署 Publisher 容器
```

之后：

```text
浏览器刷新
App 重新打开
```

即可获得新版功能。

一般不需要重新安装 APK。

只有以后增加以下原生能力时，才需要更新 APK：

- 原生相机拍照
- 生物识别
- Push Notification
- 离线草稿
- 原生分享
- 原生文件缓存
- 特殊剪贴板权限

当前 Android WebView 已支持文件选择，因此普通相册图片上传可继续使用。

---

# 21. 后端数据模型建议

## Article

```text
id
slug
title
created_at
updated_at
```

---

## WorkingDraft

```text
id
article_id
base_version_id
title
content_json
template_id
updated_at
updated_by
```

---

## ArticleVersion

```text
id
article_id
version_number
title
content_json
rendered_html
template_id
template_snapshot
created_at
created_by
```

正式 Version 不可覆盖。

---

## Asset

```text
id
article_id
path
mime_type
size
hash
created_at
deleted_at
```

---

## Publication

继续保存：

```text
version_id
draft_media_id
html_sent
html_returned
publish_id
status
result
```

---

# 22. 数据迁移

本次升级不得删除原 SQLite 数据库重建。

必须进行 Schema Migration。

现有文章：

```text
Markdown
```

可迁移为：

```text
Tiptap JSON
```

同时保留原始 Markdown，便于审计或回退。

建议：

```text
旧版本
markdown_original
content_json
rendered_html
```

逐步过渡。

---

# 23. HTML 与 CSS 输出原则

内部建议：

```text
Tiptap JSON
      ↓
Semantic HTML
      ↓
CSS Template
      ↓
Local Overrides
      ↓
Inline CSS
      ↓
WeChat HTML
```

HTML 尽量保持语义化：

```html
<h2>标题</h2>
<p>正文</p>
<blockquote>引用</blockquote>

<figure>
  <img src="...">
  <figcaption>图片说明</figcaption>
</figure>
```

避免大量无意义：

```html
<span style="...">
<div style="...">
```

---

# 24. 样式优先级最终规则

最终规则统一为：

```text
1. 当前模板 CSS
2. 当前元素 / 当前文本的局部 Override
3. 未修改属性继续继承模板
```

即：

```text
最终样式
=
Template Baseline
+
Local Property Overrides
```

如果用户点击：

```text
恢复模板
```

则删除对应 override。

---

# 25. 安全与兼容性

富文本编辑器仍需限制危险内容：

- 禁止 script
- 禁止 iframe
- 禁止 arbitrary HTML
- 禁止 event handler
- 禁止 javascript: URL
- 限制图片 MIME
- 限制图片大小
- 限制文件总大小

发送微信前继续执行 HTML sanitize。

---

# 26. 容器部署

服务器继续使用现有 Docker Compose 架构。

```text
GitHub 代码
    ↓
腾讯云服务器
    ↓
docker compose build
    ↓
重新构建 wechat-publisher
    ↓
重新创建容器
```

数据继续存放：

```text
/opt/wechat-publisher/data
        ↕
/app/data
```

因此重新构建容器不删除：

- SQLite 数据库
- 文章
- 图片
- 历史版本

---

# 27. 推荐实施顺序

## Phase 1：编辑器升级

完成：

- Tiptap
- 所见即所得编辑
- Undo / Redo
- 模板实时渲染
- 图片节点
- 手机响应式布局

---

## Phase 2：工作稿与版本

完成：

- Working Draft
- 自动保存
- 保存修改
- 保存为版本
- 历史版本切换
- 版本只读

---

## Phase 3：局部样式系统

完成：

- Local Override
- 手工修改标识
- 属性级覆盖
- 恢复单属性
- 全部恢复模板

---

## Phase 4：图片增强

完成：

- 网页上传
- 手机相册
- 拖拽
- 粘贴
- 替换
- 删除
- 图片说明
- 图片局部样式

---

## Phase 5：微信最终预览

完成：

- 微信发送前预览
- CSS inline
- 微信图片 URL 替换
- 微信返回 HTML 预览
- HTML 差异对照

---

## Phase 6：GitHub 流程简化

完成：

- inputs/wechat 不再触发 CI
- GitHub 仅作为可选内容来源
- 删除或停用旧公众号内容 CI
- 评估是否移除 wechat-ingest.yml

---

# 28. V2 最终产品定位

Publisher V2 不再只是：

> Markdown → 微信公众号

而是：

> 一个面向公众号内容生产的轻量 CMS + 富文本编辑器 + 模板系统 + 素材系统 + 版本系统 + 微信发布系统。

最终原则：

```text
GitHub
= 可选内容来源

Tiptap
= 内容编辑层

CSS Template
= 全局样式层

Local Override
= 局部差异层

Working Draft
= 临时编辑状态

Article Version
= 正式历史版本

Publisher
= 编辑、素材、版本、预览、发布中心

Android App
= Publisher 的移动端入口

微信预览
= 发布前与取回后的最终确认层
```

---

# 29. 核心结论

V2 的关键不是简单安装 Tiptap，而是同时重构以下几个概念：

1. 编辑与预览合一。
2. 模板是全局基础样式。
3. 手工修改只保存局部差异。
4. 每个局部差异都可以恢复模板。
5. 自动保存、保存修改、保存版本严格区分。
6. 图片可以直接从网页和手机上传。
7. GitHub 不再是必经流程。
8. GitHub 内容修改不再运行公众号完整 CI。
9. 微信发送前才生成最终预览。
10. 微信取回后显示微信实际保存效果。
11. Android App 继续复用服务器 Web UI，大部分升级无需重新安装 APK。
12. 数据库通过 Migration 平滑升级，禁止删除重建。

这份方案可作为微信公众号 Publisher V2 的正式产品与技术改造说明。
