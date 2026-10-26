# 手机访问

## 当前可用：同一 Wi-Fi

- 电脑地址：`192.168.0.18`
- Open-LLM-VTuber：`http://192.168.0.18:12393`
- 二维码：`mobile-preview.png`（本地生成，不提交）
- 防火墙：仅允许 `LocalSubnet` 访问 TCP 12393

已验证：

- 手机同一网段可打开页面
- 可通过局域网 WebSocket 进行文字对话
- 可通过统一 Brain Gateway 生成回复
- 可返回 Live2D 音频数据

## 限制

浏览器麦克风通常要求 HTTPS。当前局域网 HTTP 页面可文字聊天和听语音，但手机麦克风输入可能被浏览器拒绝。

## 远程/麦克风方案

需要以下任一条：

1. Tailscale 登录后使用私有 HTTPS 入口
2. 自有域名 + Cloudflare Tunnel/Access
3. 云服务器部署并配置 HTTPS

当前 Tailscale 客户端处于未登录状态，因此尚未启用远程入口。