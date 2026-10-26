# 手机设备配置与换机适配

程序不再假设所有手机都是 Xiaomi User 999。换机时先修改私有配置：

```text
D:\yige-personal-kb\12_社交代理\小居居\配置\私有.json
runtime.wechat
```

## 专用手机直接登录小居居微信

```json
{
  "package": "com.tencent.mm",
  "activity": "com.tencent.mm/.ui.LauncherUI",
  "android_user": "0",
  "variant": "primary",
  "chat_title": "大哥"
}
```

## Xiaomi 第二空间

```json
{
  "package": "com.tencent.mm",
  "activity": "com.tencent.mm/.ui.LauncherUI",
  "android_user": "999",
  "variant": "xiaomi_second_space",
  "chat_title": "大哥"
}
```

## 厂商应用分身

不同 ColorOS、OriginOS、HarmonyOS 的应用分身可能是：

- 同一用户下的独立数据容器；
- 改名后的克隆包；
- 独立 Android 用户。

必须先运行验收脚本，查看实际包名和用户。如果 `wechat_user_listed=false`，需要根据手机实际环境调整 `package` 和 `android_user`，不能直接启动 worker。

## 换机完整验收

1. USB 连接，开启 USB 调试。
2. 运行 `phone_acceptance.py`。
3. 确认截图、OCR、微信包和配置用户。
4. 修改 `runtime.wechat`。
5. 启动 worker 并让另一个真实账号发消息。
6. 验证：识别、Brain Gateway 回复、中文输入、发送、恢复键盘、不重复。
7. 通过后才切换为专用机。

只有截图能看、但完整收发没跑通，不算可用。