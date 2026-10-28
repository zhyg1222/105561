# Open-LLM-VTuber 接入 Runbook

## 目标

把本地 VTuber 表现层接到新的 Agent API，而不是旧的 Brain Gateway：

- UI/WebSocket：`http://127.0.0.1:12393`
- Agent API：`http://127.0.0.1:12402/v1`
- 模型名：`xiaojuju`
- 复用 `vendor/open-llm-vtuber`，不重写 Live2D/TTS/ASR。

## 启动

```powershell
wscript.exe D:\yige-personal-kb\xiaojuju\scripts\start_vtuber.vbs
```

Windows 登录任务：`XiaoJuJu-VTuber`。

检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:12393/ | Select-Object StatusCode
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*run_server.py*' }
```

## 配置来源

`vendor/open-llm-vtuber/conf.yaml` 的 `openai_compatible_llm.base_url` 已改为：

`http://127.0.0.1:12402/v1`

该目录属于外部 vendor submodule，不把其配置或生成的 `tts-previews/` 提交到主仓库。升级 vendor 后必须重新核对这一行。

## 边界

- 当前只验证了 VTuber 前端服务启动和 Agent API 配置接线；真实麦克风、TTS、Live2D 语音互动仍需人工验收。
- 语音输出必须继承 AI 身份，不冒充真人。
- 真实直播推流、平台弹幕接入、AI 标识、人工停止开关尚未完成。
## 启动包装器

`scripts/start_vtuber.vbs` 现在调用 `scripts/run_vtuber.py`，启动前会强制检查 `base_url`，并把 stdout/stderr 写到：

- `D:\yige-personal-kb\.runtime\vtuber\server.out.log`
- `D:\yige-personal-kb\.runtime\vtuber\server.err.log`

这样 vendor 配置被升级脚本覆盖时也不会静默接回旧 Gateway。
## 资源策略（2026-10-28）

当前主机只有约 8 GB 内存，VTuber 只作为按需本地表现层，不默认常驻：

- 登录启动任务 `XiaoJuJu-VTuber` 已禁用
- 需要时手动运行 `wscript.exe scripts\start_vtuber.vbs`
- 不再把 VTuber 在线作为核心 Agent 健康检查的硬条件
- 核心 API、微信、记忆和自主生活保持常驻