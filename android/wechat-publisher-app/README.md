# Workflow Hub 公众号 Android App

这是服务器端 Publisher 的 Android 客户端。V1 采用原生 Android WebView 安全容器加载现有移动端工作台：

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

Publisher 的账号、权限、CSRF、版本控制、图片管理、草稿和正式发布都已经由 FastAPI 实现。App 直接复用该 UI，不重复保存公众号密码或 AppSecret，也不在 APK 中放置上传 Token。服务器 UI 更新后 App 可直接获得新页面功能。

App 仅允许站内 `https://stocklab.hardway.top/publisher` 导航；其他主页面链接交给系统浏览器。HTTP 明文流量被禁用，HTTPS 证书错误不会被忽略。

## 构建

需要 JDK 17、Android SDK Platform 36、Build Tools 36.0.0、Gradle 9.6.0。

```bash
gradle -p android/wechat-publisher-app lintDebug testDebugUnitTest assembleDebug
```

APK：

```text
android/wechat-publisher-app/app/build/outputs/apk/debug/app-debug.apk
```

GitHub Actions `Android WeChat Publisher App` 会先运行 lint 和 JVM 单元测试，再构建 Debug APK 并上传 Artifact。

## 后续可扩展

如果以后需要离线草稿、推送通知、原生 Markdown 编辑器或生物识别解锁，可在保持 FastAPI API 不变的前提下逐步替换 WebView 页面，不需要重写服务端发布流程。
