# Agent Platform Operations Runbook

> 适用计划：`docs/superpowers/plans/2026-10-26-01-agent-platform-foundation.md`  
> 当前阶段：影子运行，禁止真实发送

## 1. 前置条件

- Windows 已启用 `Microsoft-Windows-Subsystem-Linux`。
- Windows 已启用 `VirtualMachinePlatform`。
- 上述功能启用后必须重启一次。
- 重启后安装 Docker Desktop，并将 Docker data-root 和 `XJJ_STACK_DATA` 指向 D 盘。
- 本项目使用 Python 3.12 和 `uv`。

检查：

```powershell
wsl --status
docker version
uv --version
```

## 2. 启动基础设施

```powershell
Copy-Item deploy/compose/.env.example deploy/compose/.env
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env up -d
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env ps
```

要求 Postgres、Valkey、Neo4j、OPA 全部为 `healthy`。

## 3. 配置 Agent

```powershell
Copy-Item deploy/agent.env.example deploy/agent.env
```

填写：

- `XJJ_DATABASE_URL`
- `XJJ_VALKEY_URL`
- `XJJ_OPA_URL`
- `XJJ_DEEPSEEK_API_KEY`
- 可选：`XJJ_OTEL_EXPORTER_OTLP_ENDPOINT`

`deploy/agent.env` 不得进入 Git。

加载环境：

```powershell
Get-Content deploy/agent.env | ForEach-Object {
  if ($_ -and -not $_.StartsWith('#')) {
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$name" -Value $value
  }
}
```

## 4. 执行迁移

```powershell
uv run python scripts/migrate_platform.py
```

迁移只创建或补齐平台表，不删除现有数据。

## 5. 启动 Agent 与 Worker

终端 A：

```powershell
uv run python scripts/run_agent_api.py --host 127.0.0.1 --port 12400
```

终端 B：

```powershell
uv run celery -A xiaojuju_agent.queue_app.celery_app worker --pool=solo --loglevel=INFO
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:12400/healthz
Invoke-RestMethod http://127.0.0.1:12400/readyz
```

要求：`healthz=ok`，`readyz=ready`。

## 6. 影子回放

回放前记录 outbox：

```powershell
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env exec -T postgres psql -U xiaojuju -d xiaojuju -c "select count(*) from app_outbox;"
```

执行：

```powershell
uv run python scripts/replay_shadow.py `
  --input tests/fixtures/shadow_sample.jsonl `
  --output D:/yige-personal-kb/.runtime/agent-shadow/result.jsonl
```

再次查询 outbox，数量必须不变。

## 7. 故障语义

- Postgres 不可用：`/v1/events` 返回 503；不能写入 SQLite 或报告成功。
- OPA 不可用：所有副作用工具 fail-closed；readiness 返回 503。
- Valkey 不可用：事件进入失败/重试路径，worker 不伪装完成。
- Neo4j 不可用：Plan 1 暂不依赖；Plan 2 接 Graphiti 后必须阻断记忆检索并记录降级。
- DeepSeek 超时/空回复：Celery 有限重试；超过上限后事件标记 failed。

## 8. 回滚

Plan 1 只做影子运行。回滚步骤：

1. 停止新 Agent API 和 worker。
2. 不删除新数据库，保留审计和回放结果。
3. 继续使用旧 `run_brain_gateway.py` 和现有发送链路。
4. 只有在旧链路也停止后，才可整体停止 Compose。

## 9. 数据导出

Postgres：

```powershell
docker compose -f deploy/compose/compose.yaml --env-file deploy/compose/.env exec -T postgres pg_dump -U xiaojuju -d xiaojuju -Fc > D:/yige-personal-kb/.runtime/backups/xiaojuju-agent.dump
```

Plan 1 不接 Neo4j 记忆数据，因此本阶段没有 Neo4j 业务导出。

## 10. 禁止事项

- 不使用 `latest` 镜像或依赖。
- 不把 `deploy/compose/.env`、`deploy/agent.env`、聊天正文提交到 Git。
- 不在影子模式向真实微信、直播、浏览器或手机发送。
- 不通过修改 Prompt 绕过 OPA。
- 不在未完成真实收发验收时宣称手机链路可用。