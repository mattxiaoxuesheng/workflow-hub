# 腾讯云运行记录

2026-09-09 已部署到现有 StockLab 服务器，入口为 https://stocklab.hardway.top/publisher/ 。

- 源码：`/opt/wechat-publisher/source`
- 启动：`sudo docker compose -f deploy/docker-compose.tencent.yml up -d --build`
- 数据：`/opt/wechat-publisher/data`，UID/GID 10001
- 环境：`/opt/wechat-publisher/secrets/publisher.env`，root:root 0600
- 管理员凭证：服务器受限 secrets 目录中的 `admin-login.txt`，密码不写入仓库
- 网关：StockLab 的现有 gateway 容器。Compose 增加子路径片段和 HTTPS 模板的只读挂载。
- 网关原配置备份：`/opt/wechat-publisher/backups/gateway-before-publisher-20260909`
- GitHub 的 PUBLISHER_URL、PUBLISHER_UPLOAD_TOKEN 已配置；上传 Token 有效期 90 天。

验证通过：7 个测试、Docker 构建、容器健康、HTTPS、静态资源、登录/退出与 Cookie 路径、验收文章导入、三个模板预览及图片读取、StockLab 登录页。验收样稿保存在工作台中。未调用微信草稿或正式发布接口。

微信公众号 AppID/AppSecret 尚未配置。通过本机 SSH 编辑服务器环境文件：

```sh
sudo nano /opt/wechat-publisher/secrets/publisher.env
cd /opt/wechat-publisher/source
sudo docker compose -f deploy/docker-compose.tencent.yml up -d --force-recreate publisher
```

在公众号后台添加服务器出口 IP 白名单，之后才能验收真实草稿。正式发布需要另行确认具体文章。工作流仍在 PR #1 分支，合入 main 后才可通过 GitHub Actions 的手动入口执行上传。

数据备份：`sudo python3 /opt/wechat-publisher/source/deploy/backup.py`。
回退网关：恢复上述备份目录的 compose.yml 和 nginx-https.conf 到 StockLab 的 deploy/docker 目录，运行 `sudo docker compose --env-file server.env -f compose.yml up -d --no-deps gateway`。这只撤销 Publisher 的公网入口；应用数据继续保留。
