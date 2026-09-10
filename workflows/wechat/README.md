# 微信公众号发布工作流 V1

GitHub 保存 Markdown 与本地图片，Actions 校验后打包并按需上传。腾讯云 Publisher 负责登录、编辑、版本、排版、预览和微信公众号接口。复用宿主机已有 Nginx，应用仅绑定 `127.0.0.1:8088`。

## 当前交付

- FastAPI + SQLAlchemy + SQLite；React + Vite + CodeMirror。
- 管理员 / 编辑、Argon2id 密码、服务端会话、CSRF 和来源校验。
- 上传 Token 只有 `article:ingest` 权限，数据库只存 SHA256；支持过期、吊销。
- 不覆盖历史版本；换模板、修改正文、上传/替换图片均可形成新版本。
- Clean / Business / Tech，Markdown 禁止原始 HTML 执行，CSS 内联。
- 正文图上传、永久封面素材、草稿新增和取回、HTML 对照、管理员确认发布及状态查询。
- 用户管理、Token 管理、公众号配置状态、审计日志。
- Docker Compose、Nginx 示例、备份脚本、离线验收文章及 CI。

**本地模拟测试不等于微信实测。** 上线需要真实公众号接口权限、AppID/AppSecret、固定出口IP白名单，以及手机端实际排版验收。正式发布在网页确认后执行；Actions 从不发布公众号。

## 文章目录

```text
inputs/wechat/文章ID/
  article.md
  cover.jpg
  meta.json           # 可选
  images/
    example.png
```

文章ID使用小写英文、数字、连字符。图片只支持本目录的 JPEG/PNG，不允许远程图、绝对路径、符号链接、SVG、data URL。正文图最大1MB，封面最大2MB；入包只包含正文、引用图片、封面及生成的 manifest，其他文件不会打入包。验收样稿见 `inputs/wechat/acceptance/`。

```markdown
# 本周 AI 动态

正文。

![图片说明](images/example.png)
```

可选 `meta.json`：

```json
{"title":"本周 AI 动态","cover":"cover.jpg"}
```

不提供 meta 时取首个一级标题和 cover.jpg。

## 本地校验与打包

在仓库根目录执行：

```bash
python -m pip install -r publisher/requirements.txt
python -m workflows.wechat.package --article inputs/wechat/acceptance
python -m pytest publisher/tests -q
```

安装测试工具：`python -m pip install pytest==9.1.1`。产物为 `output/wechat/article-package.zip`。

GitHub Actions → “微信公众号内容导入” → Run workflow：填写文章目录。不勾选 upload 只生成 Artifact；勾选 upload 才上传，且必须在 main 分支执行。工作流合入 main 后才会出现在手动运行列表。文章提交触发的 CI 只做离线验证，不向腾讯云或微信发送文章。

GitHub Secrets：

| 名称 | 内容 |
|---|---|
| PUBLISHER_URL | `https://publish.hardway.top`，不带API路径 |
| PUBLISHER_UPLOAD_TOKEN | 在 Publisher 管理后台创建、仅显示一次的 `pub_...` |

无需腾讯云 SecretId/SecretKey、SSH私钥或微信 AppSecret。Token 过期前创建替代 Token、更新 Secret，再吊销旧值。

## 腾讯云部署

前提：服务器已有 Docker Engine + Compose 插件，Nginx 运行在宿主机，有可用域名和证书。以下以 `publish.hardway.top` 为例；真实域名不同需同时改 Nginx、环境文件和 GitHub Secret。

1. 将此分支/合并后的仓库代码放到 `/opt/wechat-publisher/source`。
2. 准备数据和配置目录：

```bash
sudo install -d -m 700 /opt/wechat-publisher/secrets
sudo install -d -m 750 -o 10001 -g 10001 /opt/wechat-publisher/data
sudo install -d -m 700 /opt/wechat-publisher/backups
sudo install -m 600 deploy/.env.example /opt/wechat-publisher/secrets/publisher.env
sudo nano /opt/wechat-publisher/secrets/publisher.env
```

`publisher.env` 填真实 `PUBLISHER_ORIGIN`、`WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`。不把真实值提交到仓库。缺少微信值仍可使用编辑/版本/预览，微信操作会报尚未配置。`.env` 是普通明文文件，权限只约束普通用户；root/Docker管理员可读取。

3. 在仓库根目录构建启动，并交互创建管理员（没有默认密码）：

```bash
sudo docker compose -f deploy/docker-compose.yml up -d --build
sudo docker compose -f deploy/docker-compose.yml exec publisher python -m publisher.backend.cli create-admin --username admin
curl --fail http://127.0.0.1:8088/healthz
```

必须保持 `--workers 1` 和单个应用实例；V1使用进程锁和数据库唯一约束来串行分配版本/领取发布任务。暂不支持水平扩容。

4. 配置 DNS A 记录到腾讯云公网 IPv4。取得证书后调整 `deploy/nginx/publish.hardway.top.conf` 的证书路径；添加为独立站点，勿覆盖已有配置。确认该域名的配置没有重复：

```bash
sudo cp deploy/nginx/publish.hardway.top.conf /etc/nginx/conf.d/publish.hardway.top.conf
sudo nginx -t
sudo systemctl reload nginx
```

证书续期沿用原有方案。此示例不安装 Caddy，也不会自动申请证书。若原 Nginx 在容器中而非宿主机，请先调整容器网络；容器内的127.0.0.1不是宿主机。

### 复用现有 Docker Nginx 网关

若公网 80/443 已由 StockLab 的 Docker Nginx 网关占用，使用 `deploy/docker-compose.tencent.yml` 启动 Publisher。它会加入外部网络 `stocklab_application`，并以 `wechat-publisher:8000` 向网关提供服务。

此部署使用 `https://stocklab.hardway.top/publisher/`，复用现有域名和证书。`PUBLISHER_ORIGIN` 必须为 `https://stocklab.hardway.top`（不包含路径）。Compose 中的构建参数 `/publisher/` 控制前端资源和 API 路径，运行时 `PUBLISHER_BASE_PATH=/publisher` 控制预览图片 URL 与 Cookie 路径。

在网关 HTTPS `server{}` 中加入 `include /etc/nginx/publisher-subpath.conf;`，把 `deploy/nginx/publisher-subpath.conf` 只读挂载到该路径。把修改后的 HTTPS 模板只读挂载到 `/etc/nginx/templates/stocklab-https.conf`，以便网关重建后仍保留入口。先备份原 Compose 与模板，校验 `nginx -t` 后只重建 gateway 服务。原来的首页和 `/api/` 路由继续由 StockLab 处理。GitHub Secret `PUBLISHER_URL` 使用 `https://stocklab.hardway.top/publisher`。

5. 登录工作台，创建 GitHub 上传 Token，填入 GitHub Secrets；公众号后台把腾讯云实际出口 IPv4 加入 API 白名单。
6. 运行验收文章导入，检查三模板、历史版本和图片顺序；发送草稿并取回比较；在微信后台/手机检查真实显示。确认公众号具备权限后，由管理员明确确认一次测试文章的正式发布，再查询结果。

## 配置与扩展

普通配置在 `publisher/config/app.yaml`：默认版式、上传大小、会话时长、草稿/发布开关。修改后重启容器生效。增加 `publisher/templates/<name>.css` 并重启即可出现新模板，文件名作为版式ID。CSS是服务器管理员维护的可信文件，前台不接受任意CSS/模板HTML上传。新模板上线前用验收文章和微信草稿测试。

模板CSS通过只读目录挂载；每个文章版本保存当时CSS快照，之后修改同名模板不会改变历史版本的渲染或发布。保存新版本时使用当前版式文件。已发送HTML另存于publication记录。

服务端会话用高熵随机值、数据库仅存其hash，无需 SESSION_SECRET 或 DATA_ENCRYPTION_KEY。SQLite路径由 PUBLISHER_DATA_DIR 决定；未提供未实现的 DATABASE_URL 配置。

## 使用顺序

1. 上传内容包；相同内容包重试返回原版本。
2. 选择文章与历史版本，在正文中编辑并选模板。
3. 保存新版本。图片素材区可上传新图片/用同名文件替换，产生新版本；封面替换使用现有封面相同路径文件名。含目录的旧图片可通过API传同名相对路径替换，或重新打包导入。
4. 点击“发送微信草稿”，系统在服务器上传正文图和封面，再新增草稿。
5. 取回微信保存的HTML并查看文本对照。HTML差异为字符串比较，会包含无害的属性顺序/格式差异；不作为像素一致的保证。
6. 管理员点击“正式发布”，确认标题、版本、模板后提交，点击“查询发布结果”查看状态及返回文章链接。

EDITOR可以编辑和发送草稿，只有ADMIN可正式发布、创建账号/Token。上传Token不可登录、浏览文章或调用草稿/发布接口。

## 失败恢复

- 上传失败：同一内容包可重试，内容hash去重。文件损坏或图片缺失：修正后重新打包。
- `draft_unknown` / `publish_unknown`：微信可能已经接受请求，系统禁止自动重试。先在微信后台核对；已发布则在微信后台处理。V1不提供强制重置按钮，避免重复发文。
- 进程在请求中断电会留下 `drafting` / `submitting`，按上述不确定状态人工核对。
- 草稿创建成功但取回失败：已有草稿ID会保存，稍后使用“取回微信草稿”；不要再建重复草稿。
- 微信业务错误显示错误码，网络异常不泄露含 access_token 的请求URL。接口权限与错误码应结合微信后台核对。
- 忘记密码：服务器执行 `python -m publisher.backend.cli reset-password --username admin`（放在 compose exec 后）。重置会使该账号现有会话失效。

## 备份与恢复

```bash
sudo python deploy/backup.py
```

脚本使用 SQLite backup API 生成一致快照，包含快照引用的全部图片，生成权限600的压缩包。应另行备份 `publisher.env`、模板CSS、app.yaml 和 Nginx 配置到受限位置。可将上述命令加入服务器现有定时任务。

恢复：先停止 Publisher，备份现有 data；把备份压缩包恢复到空数据目录，检查 `publisher.db` 与 `assets/`，设置文件所有者为10001:10001，再启动。凭证不包含于数据备份中，需单独恢复。当前 schema 版本1；后续变更必须新增迁移，禁止直接删除数据库重建。

## 验证范围

`publisher/tests/test_workflow.py`覆盖内容包/图片校验、ZIP路径逃逸、远程图片拒绝、去重、不可变正文版本、三种模板图片顺序、会话/CSRF/Token隔离、账号禁用、Token吊销、微信HTTP契约、模拟草稿发布与不确定结果防重复。前端使用正式生产构建检查。

未将模拟请求说成真实微信验收；浏览器交互和真实手机排版仍需部署后检查。正式部署前以 GitHub CI 的 Docker 构建结果及真实服务器健康检查为准。

接口参考：[微信草稿新增](https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html)、[微信发布](https://developers.weixin.qq.com/doc/offiaccount/Publish/Publish.html)、[GitHub Artifact](https://github.com/actions/upload-artifact)。当前环境未能重新读取微信官方文档页面，具体账号可用性/限制仍需上线实测确认。
