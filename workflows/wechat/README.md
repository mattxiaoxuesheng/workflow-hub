# 微信公众号发布工作流 V2

Publisher 是网页和 Android WebView 共用的编辑、排版、素材、版本和微信发布中心。可直接新建文章，也可导入 Markdown/ZIP；GitHub 内容导入保留为手动备用入口。

## 编辑与版本

- Tiptap 所见即所得，编辑区实时套用模板，没有 Markdown/预览双栏。
- 模板是全局基础样式；文字、段落、标题、图片的人工修改保存为属性级差异。切换模板保留差异，可恢复单属性或全部恢复模板。
- 约两秒无输入自动保存工作稿；“保存修改”立即保存；只有“保存为版本”生成不可变历史快照。
- 多窗口编辑使用修订号，旧请求返回冲突，不静默覆盖新稿。冲突时可下载本地修改，再读取服务器工作稿。
- 历史版本只读；恢复时复制为工作稿。撤销/重做只处理当前编辑会话。
- 图片支持选择、粘贴、拖放、替换、说明、宽度、对齐和圆角；上传和替换不自动创建版本。第一张图默认封面，可重新选择。
- 删除正文引用不删除素材；永久删除素材需确认，工作稿或历史版本仍引用的素材禁止删除。
- 素材上传允许静态 JPEG/PNG/WebP，最大10MB（10 × 1024² 字节）、4000万像素。保留原图，上传后自动生成正文不超过1,000,000字节、封面不超过2,000,000字节的 JPEG/PNG 副本。修正 EXIF 方向，最长边最多2560像素；优先无损 PNG，必要时逐步降低 JPEG 质量和尺寸。透明图片若需转 JPEG 使用白底，并在预览中提示。
- 素材库和发送前预览支持原图/副本对比，展示大小、尺寸，可点击打开大图。发送微信使用已生成的相同副本；正文最终 HTML 仍使用微信上传返回地址。副本缓存可从原图重建，原图和历史版本不被覆盖。GIF/动态 WebP、SVG、HEIC 尚不支持；微信账号及接口校验仍以微信响应为准。

## 微信发布

“发送微信草稿”先保存工作稿并冻结为版本，上传正文图和封面，生成 inline CSS 和微信图片 URL 的最终 HTML。最终预览后点击“确认发送”，服务端使用预览时保存的原始 HTML，不重新渲染。历史版本也可独立发送。

取回后可查看微信返回版本、发送版本和 HTML 差异。管理员明确确认后才调用正式发布，结果不确定的请求禁止重复提交。开发测试使用模拟微信客户端；不等于真实微信排版验收。

## Markdown 和 GitHub 可选输入

纯 Markdown 文件可直接从网页导入（不支持远程图片）。带图片的文章使用内容包：

```text
inputs/wechat/<slug>/
  article.md
  cover.jpg
  meta.json                 # 可选：title / cover
  images/example.png
```

```bash
python -m workflows.wechat.package --article inputs/wechat/acceptance
```

生成 `output/wechat/article-package.zip` 后在网页导入，进入工作稿。正文引用仅支持目录内 JPEG/PNG，禁止路径逃逸、远程资源、符号链接和未引用文件。旧 `schema_version: 1` 内容包兼容。

GitHub Actions “微信公众号内容导入”仅人工触发，可只打包或使用 `PUBLISHER_URL` 和 `PUBLISHER_UPLOAD_TOKEN` 调用旧上传接口。旧接口保留导入版本用于来源审计，随后自动转换成 Tiptap 工作稿。上传 Token 只允许内容导入，不能登录或发布。`inputs/wechat/**` 内容变化不再触发完整软件 CI。

## 数据和权限

保留 FastAPI、SQLAlchemy、SQLite、登录、管理员/编辑角色、Argon2id、CSRF、Origin 校验和审计日志。升级采用可重复执行的添加字段/表迁移，保留原 Markdown 和版本，不删除数据库重建。版本冻结模板 CSS 和素材引用。

正文 JSON 由服务端白名单验证和语义化 HTML 渲染，不接受任意 HTML/CSS、脚本、iframe、事件处理器或 javascript URL。预览 iframe 禁止脚本运行。继续保持单实例、单 worker，避免多个进程领取同一发布任务。

## 镜像部署

GitHub Actions 测试、构建并发布 GHCR 镜像；腾讯云服务器拉取 digest 固定镜像并启动容器。生产服务器不构建应用源码。镜像包含匹配版本的配置和模板；数据、密钥文件和现有 StockLab 网络保留。

完整设置、Secrets、手动部署与回退步骤：[镜像部署说明](../../deploy/PUBLISHER-IMAGE-DEPLOYMENT.md)。旧部署记录见 [TENCENT-DEPLOYMENT.md](../../deploy/TENCENT-DEPLOYMENT.md)，其中的源码构建命令属于 V1 历史记录。

## 验证

```bash
python -m pip install -r publisher/requirements.txt pytest
python -m pytest publisher/tests -q
cd publisher/frontend
npm ci
npm run build
npx playwright install --with-deps chromium
npm run test:browser
```

浏览器测试启动隔离数据库和模拟微信服务，不使用真实公众号凭据。CI 另验证容器启动与部署成功/失败恢复。
