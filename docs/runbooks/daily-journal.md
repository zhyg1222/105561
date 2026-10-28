# 每日日录 Runbook

## 目标

每天从真实的 Agent 事件、自主活动、外部发送、健康状态和反思中生成一份 Markdown 日录，写入小居居知识库：

`D:\yige-personal-kb\12_社交代理\小居居\每日日录\YYYY-MM-DD.md`

不把评测、审批测试、工具测试和纯问号消息写进日录。

## 手动生成

```powershell
$env:PYTHONPATH='D:\yige-personal-kb\xiaojuju\src'
D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe scripts\generate_daily_journal.py --day 2026-10-27
```

## 自动任务

任务名：`XiaoJuJu-Daily-Journal`

- 每天 06:00 运行
- 生成前一天日录
- 包装器：`scripts/start_daily_journal.vbs`
- 心跳：`D:\yige-personal-kb\.runtime\daily-journal\last_run.json`

健康检查会把日录心跳纳入检查；超过 36 小时未生成会尝试启动该计划任务。

## 数据来源

- Postgres `app_events`：真实完成的对话事件
- Postgres `app_outbox`：对外发送记录
- `自主生活/活动日志/<day>.jsonl`：自主研究活动
- `自主生活/反思/<day>.md`：已有反思
- `.runtime/health/latest.json`：当天健康快照
- `app_memory_candidates` 状态统计

## 验收证据

2026-10-27 日录已生成：

- 真实对话：3 条
- 自主活动：3 完成、1 失败
- Memory 队列：239 `done`
- 健康检查：正常
- 文件：`D:\yige-personal-kb\12_社交代理\小居居\每日日录\2026-10-27.md`