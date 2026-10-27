# 微信真机发送 Runbook（OPPO A96 / ColorOS 12）

> 适用对象：现有 `apps/phone_agent/phone_agent.py` 的微信收发链路。  
> 本文只描述专用测试机，不包含账号密码、聊天正文或设备序列号。

## 1. 一次性准备

1. 打开 USB 调试，并将 USB 用途设为文件传输。
2. 在 `设置 -> 系统设置 -> 开发者选项` 打开 `禁止权限监控`，随后重启手机。
3. 安装 ADBKeyboard，并确认输入法已启用：

```powershell
adb -s <serial> shell ime list -s
adb -s <serial> shell ime enable com.android.adbkeyboard/.AdbIME
adb -s <serial> shell ime set com.android.adbkeyboard/.AdbIME
```

ColorOS 会为首次 ADB 安装弹系统确认页。该确认页必须保留到安装提交完成；不要在
`install-commit` 等待时杀掉 ADB 客户端。

## 2. 发送链路的设计约束

- 不写死微信输入框高度。百度输入法和 ADBKeyboard 的键盘高度不同，输入框可能在屏幕
  60% 到 95% 的区域。
- 输入完成后对整张截图做 OCR，验证文字确实进入输入框，再从同一张截图定位 `发送`。
- 发送后必须再次截图，确认输入框已清空且右侧出现对应气泡；不能仅凭点击坐标返回成功。
- 发送前读取当前输入法，发送完成后恢复到发送前的输入法，而不是假设固定为某个输入法。
- ADBKeyboard 未启用、输入法切换失败或 OCR 无法验证时，记录失败并返回 `False`，不冒充发送成功。

## 3. 运行与验收

单次检查（不会向外部发送新消息，除非检测到新的入站消息）：

```powershell
$env:TMP='D:\yige-personal-kb\.runtime\phone-agent\tmp'
$env:TEMP=$env:TMP
$env:PYTHONPATH='D:\yige-personal-kb\xiaojuju\src'
D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe `
  apps\phone_agent\phone_agent.py --once
```

后台循环由计划任务 `XiaoJuJu-Phone-Agent` 启动，登录后延迟 20 秒运行。日志：

`D:\yige-personal-kb\.runtime\phone-agent\phone-agent.log`

真机验收标准：

- `ime set` 成功切换到 ADBKeyboard；
- 中文文字进入微信输入框；
- 点击 `发送` 后输入框清空；
- 聊天页右侧出现相同文字，并完成发送后截图；
- 恢复原输入法；
- 不再出现错误的固定裁剪区域验证。

## 4. 常见故障

### `uid 2000 does not have android.permission.WRITE_SECURE_SETTINGS`

ColorOS 权限监控拦截了 `ime` 命令。打开开发者选项中的 `禁止权限监控`，重启后再试。

### `ADBKeyboard is not active`

先确认包已安装：

```powershell
adb -s <serial> shell pm list packages | Select-String adbkeyboard
```

再执行 `ime enable` 和 `ime set`。如果安装提交卡住，检查手机是否停在系统安装确认页。

### `composer verification failed`

先截图确认文字是否真的进入输入框。不要直接修改裁剪比例；不同输入法的键盘高度不同，
应使用整屏 OCR 或动态定位输入栏。

### `send button not found`

从当前整屏 OCR 结果中定位 `发送`，不要用固定 `h * 0.68` 偏移。ADBKeyboard 可能只占
屏幕底部很小的高度，发送按钮仍会靠近屏幕底部。

## 5. 最近一次验收

- 设备型号：OPPO A96 5G / PFUM10，Android 12。
- `xjj-test` 成功出现在右侧绿色气泡。
- 中文 `你好，我是小居居。` 成功出现在右侧绿色气泡。
- 发送后输入框为空，输入法恢复为系统百度输入法。
- 全仓测试：106 passed。

## App Outbox 桥接（2026-10-27）

新 Agent API 现在可以生成 `app_outbox` 消息，手机 worker 通过内部 HTTP 端点消费：

- `POST /v1/outbox/claim`
- `POST /v1/outbox/{message_id}/ack`
- `POST /v1/outbox/{message_id}/retry`
- `POST /v1/outbox/{message_id}/fail`

phone_agent 优先消费 `app_outbox`，没有消息时回退旧的 `待发送.json`。联系人 `owner` 映射到配置里的微信聊天名。

真实验收：

- 入队 `bridge-ascii-20261027`，文本 `bridge OK`
- 手机 worker 成功发送并回写 `sent`
- 日志：`[大哥] sent app outbox message bridge-ascii-20261027`

中文短消息可能因 OCR 对输入框文本检查过严而进入重试；这不是消息桥本身失败。后续应把输入框验证从“完整 OCR 相等”改为键盘/UI 状态与发送后气泡的联合校验。