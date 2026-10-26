# OPPO A97 专用机设置

## 原则

不启用应用分身。整台 A97 作为小居居的独立手机，主微信直接登录小居居自己的微信账号。

原因：

- ColorOS 应用分身的数据路径不固定。
- 专用机不需要再隔离第二个微信。
- 主微信在 Android User 0，ADB、截图、OCR 和发送路径最稳定。

## 到机设置

1. 使用 8GB 或 12GB 内存版本。
2. 完成系统初始化，设置一个你能手动解开的锁屏密码。
3. 打开开发者选项和 USB 调试。
4. 如果 ColorOS 有“USB 调试（安全设置）”，一并开启。
5. 关闭微信电池优化，允许自启动和后台活动。
6. 屏幕超时设置长一些，充电时保持唤醒。
7. 登录小居居的独立微信账号，不登录你的主微信。
8. 在微信里把对应联系人保存为“大哥”。
9. 保持微信停在与“大哥”的聊天页，方便首次验收。

## 到机验收

```powershell
$env:TMP = "D:\yige-personal-kb\.runtime\tmp"
$env:TEMP = $env:TMP
$env:PYTHONPATH = "D:\yige-personal-kb\xiaojuju\src"
D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe D:\yige-personal-kb\xiaojuju\apps\phone_agent\phone_acceptance.py
```

必须看到：

- `passed: true`
- `wechat_installed: true`
- `wechat_android_user: 0`
- `wechat_variant: primary`
- 截图和 OCR 正常

然后做完整收发测试：

1. 切换私有配置到 A97 profile。
2. 启动 `XiaoJuJu-Phone-Agent`。
3. 用另一个账号发消息。
4. 验证自动读取、Brain Gateway 回复、中文输入、发送、恢复输入法和不重复回复。
5. 连续运行一段时间后再切无线 ADB。

## 切换文件

模板：

`config/phone-profiles/oppo-a97-primary.json`

实际私有配置：

`D:\yige-personal-kb\12_社交代理\小居居\配置\私有.json`

未完成真实收发测试前，不把 A97 标记为可用。