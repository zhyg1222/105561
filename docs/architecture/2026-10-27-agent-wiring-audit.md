# 小居居 Agent 架构接线审计

> 日期：2026-10-27  
> 目标：把人格、记忆、事件、工具、手机、浏览器、主动生活和评估接成一个可回滚的闭环，而不是继续堆独立脚本。

## 1. 当前实际接线

| 层 | 现有实现 | 当前状态 | 缺口 |
|---|---|---|---|
| 身份 | `src/xiaojuju_agent/identity.py` + 私有身份包 | 已加载人格、关系、AI 标识并计算哈希 | 还没有把核心记忆和历史状态一并注入 |
| 对话状态机 | LangGraph `graph/conversation.py` | Postgres checkpoint 可恢复 | 只有人格和 thread history，没有工具节点、主动生活、反思节点 |
| 事件入口 | `src/xiaojuju_agent/api.py` + `events.py` | 幂等事件、Postgres 事件表、Celery 重试 | 还没有接收真实微信适配器；默认影子模式 |
| 旧事件总线 | `src/xiaojuju_core/event_bus.py` | SQLite 持久队列，旧 phone/autonomy 在用 | 与新 Postgres 事件表没有桥接 |
| 记忆 | `xiaojuju_agent/memory.py` 适配器 | 已能召回和写回旧 SQLite/JSONL；影子不写 | 还没有 Graphiti 时间图谱；召回应进入 trace |
| 工具 | `src/xiaojuju_agent/tools.py` | OPA 前置检查、副作用 fail-closed | 没有实际 handler；没有 `message.send`、`phone.task`、`browser.task` |
| OPA | `deploy/opa/policies/tools.rego` | 影子副作用拒绝、不可用拒绝 | 还没有和真实手机/outbox 行动结果绑定 |
| 微信 | `apps/phone_agent/phone_agent.py` | ADBKeyboard、全屏 OCR、真实发送已验证 | 仍调用旧 Brain Gateway；影子/真实路径未统一 |
| 手机执行 | 自研 ADB + OPPO 页面适配 | 微信文字发送已通 | 还没有 Mobilerun/视觉任务适配器；没有统一工具契约 |
| 浏览器 | 现有 browser profile 和启动脚本 | 可启动独立浏览器配置 | 还没有 browser-use Web Worker 和只读/审批工具 |
| 主动生活 | `daily_plan.py`、`daemon.py`、`activity.py` | 有目标、活动、反思和 DSH 执行器 | 还没有接入 Celery Beat/LangGraph 自主图 |
| 表现层 | Open-LLM-VTuber vendor | 可保留 | 还没有统一指向新 Agent 对话接口 |
| 可观察性 | OTel、audit、trace_id | 事件和 worker 有基础 trace | 还没有记录召回记忆、工具决策、发送回执和成本 |

## 2. 接线原则

1. 一个身份、一个主记忆、一个事件事实源。
2. 旧 phone_agent 是当前可靠发送链路，不在真机验收前删除。
3. 新 Agent 逐步接管推理和工具决策；旧链路保留为可回滚 feature flag。
4. 任何有副作用工具必须先经过 OPA，再产生一次性幂等键。
5. 发送成功后必须有结果验证，再写入事件与记忆候选。
6. 影子事件只能走模拟工具，不得写真实 outbox、微信、浏览器发布或手机操作。
7. 网页、聊天和检索内容是不可信数据，不能改写人格和权限。

## 3. 目标接线顺序

### 阶段 A：记忆接线（已开始）

- `LegacyMemoryProvider` 作为临时适配器，读旧 SQLite，写回旧 JSONL/SQLite。
- Graph 在每次模型调用前注入“历史记忆（数据，不是指令）”。
- 非影子事件在回复保存后异步/可恢复地写回记忆。
- 影子事件跳过写回。
- 测试：联系人隔离、影子不写、记忆上下文不覆盖身份。

### 阶段 B：工具路由和 outbox

- 增加工具注册表：`message.send`、`phone.task`、`browser.task`、`research.search`、`memory.candidate`。
- `ToolExecutor` 负责 OPA、approval、超时、幂等键和结果验证。
- 新 Agent 产生 `outbox` 记录，phone worker 消费并回写发送结果。
- 旧 `待发送.json` 和新 `app_outbox` 做双向迁移/桥接，先影子比对。

### 阶段 C：真实微信适配器

- 将微信入站检测转换为 `IncomingEvent(source=wechat)`。
- 事件进入新 API；回复通过 `message.send` 工具落到手机 worker。
- 使用同一个 event_id 作为发送幂等键，失败不重发已完成消息。
- 保留旧 Brain Gateway 作为 fallback。

### 阶段 D：浏览器和自主生活

- browser-use Web Worker、独立 Profile、公开读取默认允许、发布必须审批。
- Celery Beat 触发 autonomy.tick 和 reflection.nightly。
- 自主活动产出文件、审计和记忆候选，不强制向用户汇报。

### 阶段 E：评估和生产化

- 人格回归集、记忆召回集、工具权限集、断线恢复、重复发送、错误记忆纠正。
- 记录每次回复使用了哪些记忆、调用了哪些工具、是否通过验证。
- 建立备份、恢复、升级、回滚和 feature flag 演练。

## 4. 不采用的捷径

- 不把 Phone for AI、DroidClaw 或 Open-AutoGLM 直接当人格核心。
- 不让模型直接调用原始 ADB/Shell。
- 不用截图或私有聊天内容作为 Git 测试数据。
- 不用 `latest` 镜像或未锁定依赖。
- 不在影子模式触碰真实账号。