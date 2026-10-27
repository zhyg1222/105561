# 记忆一致性回填 Runbook

## 目的

持久化队列上线前的已完成事件，可能只有 `app_events` 结果而没有 `app_memory_candidates`。回填脚本找出这些缺口，重新进入 Graphiti + SQLite/JSONL 长期记忆。

## 安全默认

默认 dry-run：

```powershell
D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe scripts\reconcile_memory.py `
  --sources wechat,live,browser --limit 1000
```

默认排除：

- `eval:`
- `approval-`
- `browser-read-`
- `graphiti-live`
- `agent-client-test`
- `unicode-header-test`
- `integration-`
- `tool-`
- `fetch-integration`

测试/评测事件不能污染真实知识库。确认 dry-run 只包含真实对话后，再执行：

```powershell
... scripts\reconcile_memory.py --sources wechat --limit 1000 --apply
```

## 执行后验证

```powershell
Invoke-RestMethod http://127.0.0.1:12402/v1/memory/queue
```

要求最终 `queued=0`、`processing=0`、`failed=0`。若 `failed>0`，查看候选的 `last_error`，禁止直接把失败当成功。

## 最近实测（2026-10-27）

- dry-run 找到 274 个历史缺失事件，过滤测试事件后 eligible=3。
- 回填 3 条真实微信对话：`d019...`、`4c46...`、`a624...`。
- 三条候选最终均为 `done`，队列 `failed=0`。