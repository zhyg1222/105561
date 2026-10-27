# Graphiti 长期记忆运行手册

## 当前模式

- `XJJ_GRAPHITI_ENABLED=true` 时，新 Agent 使用 `GraphitiMemoryProvider`。
- 旧 SQLite/JSONL 仍然同步写入，作为回滚和故障 fallback。
- Graphiti episode 后台异步写回，避免拖慢聊天回复。
- 召回设置 8 秒超时；Graphiti 不可用时自动使用旧记忆。
- 联系人隔离通过 `contact_<contact_key>` group_id 实现。

## 依赖

- `graphiti-core==0.31.2`
- Neo4j 5.26
- DeepSeek API 用于实体/关系抽取
- 本地 `HashEmbedder`：当前是字符 n-gram 确定性向量，主要保证链路可运行；后续可替换为专用 embedding 模型。

## 配置

API 启动脚本设置：

```text
XJJ_GRAPHITI_ENABLED=true
XJJ_NEO4J_URI=neo4j://127.0.0.1:7687
XJJ_NEO4J_USER=neo4j
XJJ_NEO4J_PASSWORD=<本地开发密码>
```

## 验证

```powershell
D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe -m pytest tests/agent/test_graphiti_memory.py -q
```

真实 Neo4j 验证结果：

- 写入 episode 后，抽取 2 个实体、1 条关系。
- 查询“老大喜欢什么表达方式”召回图谱事实：
  `老大喜欢小居居给出直接、简短的回答`
- 旧 SQLite memory 同步保留。

## 持久化写入队列（2026-10-27）

旧实现使用进程内 `asyncio.create_task`，API 在写回前重启时 episode 可能丢失。现在改为 PostgreSQL 事务内写候选行，独立 worker 顺序写 Graphiti。

### 迁移

```powershell
$env:PYTHONPATH='D:\yige-personal-kb\xiaojuju\src'
.\.venv\Scripts\python.exe scripts\migrate_platform.py
```

迁移会创建 `app_memory_candidates`，不会删除现有事件或记忆。

### 启动 worker

```powershell
$env:XJJ_GRAPHITI_ENABLED='true'
$env:XJJ_NEO4J_URI='neo4j://127.0.0.1:7687'
$env:XJJ_NEO4J_USER='neo4j'
$env:XJJ_NEO4J_PASSWORD='xjj-dev-neo4j'
$env:XJJ_DEEPSEEK_API_KEY=$env:DEEPSEEK_API_KEY
.\.venv\Scripts\python.exe scripts\run_memory_worker.py
```

Windows 登录任务为 `XiaoJuJu-Memory-Worker`，执行 `scripts/start_memory_worker.vbs`。单次验收：

```powershell
.\.venv\Scripts\python.exe scripts\run_memory_worker.py --once
```

### 状态

```powershell
Invoke-RestMethod http://127.0.0.1:12402/v1/memory/queue
```

状态含义：

- `queued`：等待处理
- `processing`：已被 worker 租约持有
- `done`：已写入 Graphiti
- `failed`：超过重试上限，需要人工检查或调用 `requeue_failed`

### 幂等与重试

- 事件结果与候选行在同一 PostgreSQL 事务提交。
- `FOR UPDATE SKIP LOCKED` 保证多个 worker 不会同时领取同一候选。
- Graphiti episode 使用业务键 `conversation:<event_id>`；worker 在重试前先检查该键，避免部分写入后重复建 episode。
- 失败按指数退避重试，默认最多 5 次；`lease_seconds` 默认 300 秒，崩溃后过期可重新领取。
- worker 是顺序处理，避免 Graphiti 同一联系人的 episode 并发写入导致上下文顺序漂移。

### 验收证据

- 全量测试：`148 passed`
- 真实候选 `queue-smoke-20261027-1` 写入 Neo4j 成功
- 队列最终状态：`done`
- 重复回放后 Neo4j 中同名 episode 数量仍为 `1`