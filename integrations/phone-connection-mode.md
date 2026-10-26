# 手机连接模式

## 当前：USB-only

配置位置：

```text
D:\yige-personal-kb\12_社交代理\小居居\配置\私有.json
runtime.phone_control
```

当前值：

```json
{
  "mode": "usb_only",
  "wireless_enabled": false,
  "usb_serial": "VO6XX4W445AUUWXW",
  "wireless_serial": "192.168.0.14:5555"
}
```

行为：

- 只使用 USB 序列号。
- 即使无线 ADB 仍然在线，也不会使用。
- 没插 USB 时，worker 不操控手机，只定期记录“等待 USB 连接”。
- 不会自动执行 `adb connect`。

## 独立手机到货后

将私有配置改为：

```json
{
  "mode": "wireless_only",
  "wireless_enabled": true,
  "usb_serial": "",
  "wireless_serial": "新手机IP:5555"
}
```

然后重启 `XiaoJuJu-Phone-Agent`。人格、记忆、Brain Gateway 和社交配置无需改变。