# Workflow Hub 公众号 Android App

这是服务器端 Publisher 的 Android 客户端。V1 采用原生 Android WebView 安全容器加载现有移动端工作台。个人版 App 不显示用户名/密码登录页，启动时使用与 APK 同批生成的 App 专用凭证向 FastAPI 换取管理员 Session：

- 查看文章与历史版本
- 编辑标题和 Markdown
- 手机宽度预览
- 上传或替换 JPEG/PNG 图片
- 保存新版本
- 发送/检查微信草稿
- ADMIN 账号可确认正式发布并查询结果

入口固定为：

```text
https://stocklab.hardway.top/publisher/
```

## 为什么 V1 复用 Web UI

Publisher 的权限、CSRF、版本控制、图片管理、草稿和正式发布都由 FastAPI 实现。App 直接复用该 UI，不保存微信公众号 AppSecret，也不使用 GitHub 上传 Token。个人版 APK 内含一个仅用于 App 自动登录的高熵凭证；服务器只在该凭证匹配时创建 `admin` Session。普通浏览器访问仍使用原用户名/密码登录。服务器 UI 更新后 App 可直接获得新页面功能。

App 仅允许站内 `https://stocklab.hardway.top/publisher` 导航；其他主页面链接交给系统浏览器。HTTP 明文流量被禁用，HTTPS 证书错误不会被忽略。

## 个人 App 自动登录

GitHub Actions 每次构建都会临时生成一个新的 App 凭证，同时产出：

```text
app-debug.apk
publisher-android.env
```

把 `publisher-android.env` 中的两行合并到服务器的 `/opt/wechat-publisher/secrets/publisher.env`，部署当前版本 Publisher 并重启容器后，再安装同一次构建产生的 APK。两者必须配套使用。

这个凭证等价于“这份 APK 的登录钥匙”。不要公开分发 APK 或 `publisher-android.env`。公众号 `WECHAT_APP_SECRET` 仍然只保存在服务器，不进入 APK。

## 构建

需要 JDK 17、Android SDK Platform 36、Build Tools 36.0.0、Gradle 9.6.0。

```bash
gradle -p android/wechat-publisher-app lintDebug testDebugUnitTest assembleDebug -PpublisherAppToken='本机专用高熵Token'
```

APK：

```text
android/wechat-publisher-app/app/build/outputs/apk/debug/app-debug.apk
```

GitHub Actions `Android WeChat Publisher App` 会先运行 lint 和 JVM 单元测试，再构建 Debug APK 并上传 Artifact。

## 后续可扩展

如果以后需要离线草稿、推送通知、原生 Markdown 编辑器或生物识别解锁，可在保持 FastAPI API 不变的前提下逐步替换 WebView 页面，不需要重写服务端发布流程。
