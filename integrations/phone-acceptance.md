# 专用手机验收

候选手机必须通过 `apps/phone_agent/phone_acceptance.py` 的实测，不能只看型号。

## 验收命令

```powershell
$env:TMP = "D:\yige-personal-kb\.runtime\tmp"
$env:TEMP = $env:TMP
$env:PYTHONPATH = "D:\yige-personal-kb\xiaojuju\src"
D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe D:\yige-personal-kb\xiaojuju\apps\phone_agent\phone_acceptance.py
```

## 必须通过

- ADB 设备状态为 `device`
- 能稳定截图并解码
- OCR 至少识别到 2 段屏幕文字
- 已安装微信
- 设备唤醒后屏幕可读

## 警告项

- Android 低于 10
- RAM 低于 4GB
- 未充电且电量低于 20%
- 可用存储低于 2GB

## 当前基线

- Redmi K50（型号 22041211AC）
- Android 14
- 11.23GB RAM
- 电量 100%，正在充电
- OCR 19 段
- 微信已安装
- 验收通过

## 候选机建议

- OPPO A97：优先，系统较新、8/12GB
- Redmi Note 9 6GB：兼容当前 Xiaomi 自动化路线
- vivo Y75 2022 8GB：可用，需检查后台保活
- Huawei Mate 30：性能好，但 HarmonyOS ADB 需要实测
- OPPO Reno2 Z：可用但不优先

没有通过验收脚本的机器，不承诺可长期无人值守运行。