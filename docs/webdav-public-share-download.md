# WebDAV Public Share Download

公开分享下载保持两种路径：

- 非苹果设备：校验分享签名后继续返回 `307`，浏览器直连带 WebDAV 凭据的真实文件地址，避免业务服务器中转下载流量。
- 苹果设备：当 `User-Agent` 包含 `iPhone`、`iPad`、`iPod` 或 `Macintosh` 时，后端使用已配置的 WebDAV 账号拉取文件并流式返回给访问者，避免 Safari、iOS 或 macOS 在直连 WebDAV 时弹出账号密码认证框。

这个策略只解决苹果设备下载体验问题。非苹果设备仍会收到带 WebDAV 凭据的重定向地址，公开分享账号应使用专用只读账号，并限制到外发目录。
