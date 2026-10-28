# 外部架构对标与当前实现审计

> 日期：2026-10-28  
> 方法：本机 `anysearch` 搜索/抽取 + GitHub API 元数据；星标数为本次查询时的公开数据，不把它们当成质量唯一指标。

## 结论先说

当前架构的**开源底座选得不差**：LangGraph、Postgres、Graphiti、OPA、Mobilerun/Open-AutoGLM、Open-LLM-VTuber、social-auto-upload 都是有维护者和真实使用者的项目。

但现在的实现不能吹成“生产级最高架构”：

- 编排、记忆、审批、发布适配：底座和方向正确。
- 手机控制：目前自研 ADB + OCR，是最弱的一层，应该接入 Mobilerun/Open-AutoGLM 一类视觉/可访问性 Agent。
- 记忆：Graphiti 方向正确，但当前 `HashEmbedder` 只是本地字符 n-gram 占位，不是真正的语义 embedding。
- 评测：当前 50+10 条自有场景能防回归，但还不是完整的外部基准/仿真框架。
- 可观察性：有 OTel 基础，但还没有把记忆召回、工具决策、发送回执、成本完整串成一条 trace。

## 外部项目证据

| 项目 | GitHub 星标 | 许可证 | 对本项目的意义 |
|---|---:|---|---|
| LangGraph | 44,014 | MIT | 官方提供 checkpointer（线程状态）和 store（跨线程数据），与我们的 LangGraph + Postgres checkpoint 方向一致 |
| Graphiti | 32,288 | Apache-2.0 | episode 是时间化知识图谱的摄入单元，支持 message/text/json 和批量摄入；适合长期事实、来源和时间关系 |
| Mem0 | 67,944 | Apache-2.0 | 成熟的内存层，强调个性化、跨会话和 temporal reasoning；是 Graphiti 的替代方案，不应同时再叠加一套 |
| Cognee | 32,829 | Apache-2.0 | 图记忆/记忆流水线，可把关系元数据、向量和图状态组合；作为架构参考 |
| Letta | 25,270 | Apache-2.0 | stateful agent + memory blocks，适合对照“独立人格和长期状态”的做法 |
| Mobilerun | 9,845 | MIT | 明确支持 Android/iOS、可访问性树 + 截图、自然语言任务、Python/CLI；应成为手机执行层候选 |
| Open-AutoGLM | 26,491 | Apache-2.0 | Android/HarmonyOS 手机 GUI Agent，ADB/HDC 驱动，支持模型/API；手机执行层的另一候选 |
| Open-LLM-VTuber | 14,424 | NOASSERTION | 后端已经有 ASR/TTS/Agent/WebSocket/Live2D 分层；适合做表现层，但许可证需要逐个版本确认 |
| social-auto-upload | 15,864 | MIT | 已有多平台 CLI/Skill、登录和发布流程；适合做发布适配器，不应重写所有 selector |
| Langfuse | 36,617 | NOASSERTION | Agent trace/评估/成本观测候选；接入前确认 self-host 许可 |

### 关键外部事实

- LangGraph 官方持久化文档明确区分：
  - `Checkpointer`：单线程状态快照，适合对话连续性、故障恢复、human-in-the-loop。
  - `Store`：跨线程的应用数据，适合偏好、事实和共享知识。
  - 我们当前用 Postgres checkpointer 保存 thread state，再以 Graphiti 作为跨线程时间图谱，这个分工有依据。
- Graphiti 官方文档说明：
  - episode 是单次摄入事件，节点通过 `MENTIONS` 关联；
  - 支持 `message`、`text`、`json` episode；
  - 大批量用 `add_episode_bulk`。
  - 因此我们采用“事件 → episode → 实体/关系/时间”的模型是合适的，自研的队列只是把异步失败恢复和投递可靠性补上。
- 事务 outbox + `FOR UPDATE SKIP LOCKED` 是成熟的 Postgres 至少一次投递模式。我们的 `app_memory_candidates` 把事件结果和记忆候选放在同一事务，符合该模式；副作用必须幂等，这正是现在用业务键避免重复 episode 的原因。
- Mobilerun 官方 README 明确把“可访问性树 + 截图”作为手机视觉理解路径；Open-AutoGLM 明确提供 Android ADB/HDC GUI 执行。当前只用坐标 OCR，能力范围和鲁棒性都低于这两个项目。

## 逐层评价

### 1. 编排层：优质复用

- LangGraph：MIT，44k stars，官方持久化语义清楚。
- 当前 `AsyncPostgresSaver` + thread id 是正确方向。
- 不足：工具调用、记忆召回、决策和发送回执没有统一 trace；需要在节点层补观测。

### 2. 记忆层：方向优质，当前实现需升级

- Graphiti：Apache-2.0，32k stars；适合时间化事实、来源和关系。
- 当前自研 durable queue 有标准 outbox 依据，不是凭空发明。
- 明显短板：`HashEmbedder` 只是 n-gram，语义召回质量有限。
- 建议：换成真实中文/多语 embedding（BGE-M3、BGE-small-zh 或等价本地模型），保留 hash fallback；Graphiti 的 LLM 抽取和 embedding 分开配置。

### 3. 手机层：当前最弱，不建议继续扩自研 OCR

- 现有 ADBKeyboard + OCR 已经真机发中文成功，可保留作为稳定 fallback。
- 但自研 OCR 对页面变化、按钮定位、复杂多步任务是脆弱的。
- 建议新增 `phone.task` 统一工具契约，后端优先接 Mobilerun 或 Open-AutoGLM；ADB 仅在简单微信发送、旧设备、离线场景保留。
- 不应把“坐标点击成功一次”当成通用手机执行能力。

### 4. 审批层：OPA 是正确底座，审批存储要补审计

- OPA 是业界的 policy-as-code 方案；我们的一次性、过期、事件绑定、参数匹配是合理的安全设计。
- 不足：还没有把每次工具决策、批准人、执行结果和回执完整写入统一审计查询。
- 建议：补 `app_tool_runs` 的实际写入、trace id、发送回执和失败原因。

### 5. 社交发布：复用策略正确，当前暂停

- `social-auto-upload` MIT、15.8k stars，已有 CLI 和 Agent Skill；把它作为适配器比自己维护 selector 更合理。
- 小红书按要求暂停；抖音/视频号等恢复时继续复用，不自行重写平台网页脚本。

### 6. VTuber：表现层可复用，资源策略要现实

- Open-LLM-VTuber 的 ASR/TTS/Agent/WebSocket/Live2D 分层适合表现层。
- 当前主机只有约 8GB 内存，不能把它作为核心常驻服务；现在改为按需启动是正确的工程选择。
- 真实麦克风、TTS、Live2D 互动仍需设备级验收。

### 7. 评测：自研场景有效，但不应封顶

- Google Agent EvalKit、AWS Agent-EvalKit、LangSmith/openevals 都提供多轮仿真和工具调用评估思路。
- 当前 50 单轮 + 10 多轮场景是业务回归集，不是完整生态基准。
- 建议保留自有场景，同时引入标准数据结构、固定随机性/重复运行、工具调用和失败恢复评估。

## 最终判断

- **组件选择：8/10**。LangGraph、Graphiti、Postgres、OPA、Mobilerun/Open-AutoGLM、social-auto-upload 都有明确来源。
- **当前接线：7/10**。记忆 outbox、微信 outbox、VTuber 接线已经真实跑通。
- **手机自主能力：5/10**。真实中文发送可用，但还不是通用视觉手机 Agent。
- **记忆语义质量：6/10**。结构好，embedding 仍是占位实现。
- **生产可观测/回滚：6/10**。备份、审批、单实例已有，trace 和统一回执仍缺。
- **总体：可运行的个人 Agent 原型，不是吹出来的生产级平台。**

## 下一步优先级

1. 接真实中文 embedding，替换 `HashEmbedder`。
2. 用 Mobilerun/Open-AutoGLM 做手机执行层，ADB 保留 fallback。
3. 补工具决策/发送回执/成本的统一 trace 和 `app_tool_runs`。
4. 把当前业务评测扩展到标准多轮工具评估和真实历史样本。
5. 社交平台仍按用户要求暂停小红书；恢复时继续用 `social-auto-upload`。

## 参考来源

- LangGraph: https://github.com/langchain-ai/langgraph
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/durable-execution
- Graphiti: https://github.com/getzep/graphiti
- Graphiti episodes: https://help.getzep.com/graphiti/core-concepts/adding-episodes
- Mem0: https://github.com/mem0ai/mem0
- Cognee: https://github.com/topoteretes/cognee
- Letta: https://github.com/letta-ai/letta
- Mobilerun: https://github.com/droidrun/mobilerun
- Open-AutoGLM: https://github.com/zai-org/Open-AutoGLM
- Open-LLM-VTuber backend: https://open-llm-vtuber.github.io/docs/user-guide/backend/structure/
- social-auto-upload: https://github.com/dreammis/social-auto-upload
- Langfuse: https://github.com/langfuse/langfuse