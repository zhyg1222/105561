# Agent Platform Operations Runbook

> 适用计划：`docs/superpowers/plans/2026-10-26-01-agent-platform-foundation.md`
> 当前阶段：影子运行，禁止真实发送

## 1. 运行架构

- Windows WSL2 发行版：`UbuntuAgent`
- WSL 虚拟磁盘：`D:\yige-personal-kb\.runtime\wsl\UbuntuAgent`
- Docker Engine：`29.1.3`
- Docker Compose：`2.40.3`
- 数据存储：Docker 命名卷，实际位于 D 盘的 WSL 虚拟磁盘
- 镜像缓存：`docker.m.daocloud.io`

不再依赖 Docker Desktop。WSL 内的 systemd 管理 Docker Engine。

## 2. 启动常驻栈

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\start_agent_stack.ps1
```

该脚本会：

1. 启动 `UbuntuAgent`。
2. 启动 Docker Compose 服务。
3. 保持一个 `sleep infinity` 前台进程，防止 WSL2 空闲自动停止。

检查：

```powershell
wsl -d UbuntuAgent -u root -- bash -lc "docker ps --format '{{.Names}} {{.Status}}'"
```

要求：

- `xiaojuju-agent-postgres-1` healthy
- `xiaojuju-agent-valkey-1` healthy
- `xiaojuju-agent-neo4j-1` healthy
- `xiaojuju-agent-opa-1` healthy

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
wsl -d UbuntuAgent -u root -- bash -lc "docker exec xiaojuju-agent-postgres-1 psql -U xiaojuju -d xiaojuju -c 'select count(*) from app_outbox;'"
```

执行：

```powershell
uv run python scripts/replay_shadow.py `
  --input tests/fixtures/shadow_sample.jsonl `
  --output D:/yige-personal-kb/.runtime/agent-shadow/result.jsonl
```

再次查询 outbox，数量必须不变。

## 7. Registry 网络

Compose 使用 `docker.m.daocloud.io` 拉取已固定的 Docker Hub 镜像。版本标签不变。

如果镜像源不可用：

1. 先检查 `docker pull docker.m.daocloud.io/library/hello-world:latest`。
2. 不要改回无代理的 `docker.io` 盲试。
3. 选择新的可信 registry 后，逐镜像校验 digest，再更新 Compose。

## 8. 故障语义

- Postgres 不可用：`/v1/events` 返回 503；不能写 SQLite 或报告成功。
- OPA 不可用：所有副作用工具 fail-closed；readiness 返回 503。
- Valkey 不可用：事件进入重试/未发布状态，worker 不伪装完成。
- Neo4j 不可用：Plan 1 暂不依赖；Plan 2 接 Graphiti 后阻断记忆检索并记录降级。
- DeepSeek 超时/空回复：Celery 有限重试；超过上限后事件标记 failed。
- WSL 停止：运行 `scripts/start_agent_stack.ps1`，命名卷数据不会丢失。

## 9. 回滚

Plan 1 只做影子运行。回滚步骤：

1. 停止新 Agent API 和 worker。
2. 不删除 Docker 命名卷，保留事件、结果和审计。
3. 继续使用旧 `run_brain_gateway.py` 和现有发送链路。
4. 最后才执行 `docker compose down`，不要使用 `-v`。

## 10. 数据导出

Postgres：

```powershell
New-Item -ItemType Directory -Force D:/yige-personal-kb/.runtime/backups | Out-Null
wsl -d UbuntuAgent -u root -- bash -lc "docker exec xiaojuju-agent-postgres-1 pg_dump -Fc -f /tmp/xiaojuju-agent.dump -U xiaojuju -d xiaojuju"
wsl -d UbuntuAgent -u root -- bash -lc "docker cp xiaojuju-agent-postgres-1:/tmp/xiaojuju-agent.dump /mnt/d/yige-personal-kb/.runtime/backups/xiaojuju-agent.dump"
```

Plan 1 不接 Neo4j 记忆数据，因此本阶段没有 Neo4j 业务导出。

## 11. 开机自启

注册 Windows 登录任务：

```powershell
$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument '-NoProfile -ExecutionPolicy Bypass -File "D:\yige-personal-kb\xiaojuju\scripts\start_agent_stack.ps1"'
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask `
  -TaskName "XiaoJuJu-Agent-Stack" `
  -Action $action `
  -Trigger $trigger `
  -RunLevel Highest `
  -Force
```

## 12. 禁止事项

- 不使用 `latest` 镜像或依赖。
- 不把 `deploy/compose/.env`、`deploy/agent.env`、聊天正文提交到 Git。
- 不在影子模式向真实微信、直播、浏览器或手机发送。
- 不通过修改 Prompt 绕过 OPA。
- 不在未完成真实收发验收时宣称手机链路可用。
- 不对 Docker 命名卷执行 `docker compose down -v`。