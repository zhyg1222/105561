# 小居居目标交接（自动续跑更新）

> 更新时间：2026-10-27 22:21  
> 状态：active，预算 100,000,000 token，未完成。

## 本轮新增

- `85ae051`：多轮评估、健康监控、PostgreSQL/Neo4j 备份恢复演练。
- 多轮评估新增 `evals/multiturn_scenarios.jsonl`，覆盖跨轮记忆、项目上下文、纠正偏好、AI 身份、审批、安全边界和回滚。
- 多轮实测：`8/8` 通过。
- 单轮 50 场景最近一次：`49/50`；唯一失败是评分词表误把自然的“好的内容”判为禁止词，定向复测已通过。
- 评估器对 429/5xx 增加指数退避重试，避免把模型服务瞬时 503 记成人格失败。
- 健康监控任务：`XiaoJuJu-Health-Monitor`，每 5 分钟运行 `scripts/health_check.py --repair --notify`。
- 健康检查当前 `ok=true`：API、Postgres、Neo4j、Memory worker、Phone agent、ADB 全部正常；WSL 子进程在健康检查进程中被系统拒绝时标记为跳过，服务端口由其他检查覆盖。
- 备份恢复演练：PostgreSQL 生产/恢复计数一致（`514|230|0|3`）；Neo4j 导出 236 episodes / 442 edges，临时集合恢复 236 并清理；临时数据库无残留。
- 清理了 3 条测试审批和 224 个 `conversation:eval:` 测试 episode。

## 当前唯一外部阻塞

小红书、抖音、视频号都还没有有效登录 cookie。二维码登录需要用户手机扫码；在此之前不能做真实公开发布验收。

登录恢复命令：

```powershell
D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe scripts\start_social_login.py xiaohongshu --account xiaojuju --wait-seconds 25
```

扫码后先检查：

```powershell
Invoke-RestMethod "http://127.0.0.1:12402/v1/social/session?platform=xiaohongshu&account=xiaojuju"
```

只有 `valid=true` 才进入批准和发布测试。发布仍需一次性审批，不能把 `submitted` 当成 `published`。

---
# 小居居目标交接（最新）

> 更新时间：2026-10-27  
> 目标状态：active，预算 100,000,000 token，未完成，不要标记 complete。

## 最新提交

- `8a19203`：Graphiti 持久化写入队列、独立 worker、迁移、真实 Neo4j 验收。
- `12afe95`：社交发布审批层、AI 身份标注、`social-auto-upload` 适配、页面回执验证。

## 当前已完成

- 事件结果与 `app_memory_candidates` 同一 PostgreSQL 事务提交。
- `XiaoJuJu-Memory-Worker` 独立消费 Graphiti，支持 `FOR UPDATE SKIP LOCKED`、租约、指数退避、失败状态和业务键幂等。
- 真实验收：`queue-smoke-20261027-1` 最终 `done`；重复回放后 Neo4j 同名 episode 仍为 1。
- 记忆召回已修复：Graphiti 结果不再丢弃旧 SQLite/JSONL 结果，二者合并去重。
- 全量测试：151 passed；OPA：5/5 passed。
- 社交发布：`social.publish` 必须经 OPA 一次性批准；影子事件拒绝；媒体限制在配置目录；正文自动加 `【AI智能体·小居居】`。
- 已接入 `dreammis/social-auto-upload`（MIT，约 15.8k stars）到 `D:\yige-personal-kb\.runtime\social-auto-upload`，使用系统 Chrome，避免重复维护平台 selector。
- 新增 `scripts/bootstrap_social_upload.py`、`scripts/start_social_login.py`、`scripts/verify_social_post.py`。

## 当前运行状态

- Agent API：`http://127.0.0.1:12402`，`/readyz` ready。
- Memory worker：登录任务 `XiaoJuJu-Memory-Worker`，当前有 Python 进程在运行。
- OPA 已重启并加载 `social.publish` 规则。
- 小红书登录流程当前可能已过期；需要重新启动扫码。
- 平台 cookie 还没有有效登录态：`xiaohongshu`、`douyin`、`tencent` 的 `check` 均未完成真实登录。

## 真实发布下一步

1. 打开最新小红书二维码：`D:\yige-personal-kb\.runtime\social-auto-upload\cookies\xiaohongshu_xiaojuju_xhs_login_qrcode_*.png`
2. 用小红书 APP 扫码；成功后检查 `GET /v1/social/session?platform=xiaohongshu&account=xiaojuju`。
3. 准备一条明确 AI 身份的草稿，使用 `/v1/social/publish` 创建 pending approval。
4. 用户明确批准后再次提交同一 payload，检查回执和页面截图。
5. 再依次完成抖音、视频号登录。

## 风险

- 平台 selector 会随网页版本变化；回执未页面验证时只能标记 `submitted`，不能宣称 `published`。
- 外部 `social-auto-upload` 运行时不在 Git 仓库；升级后需重新执行 bootstrap 兼容补丁。
- 不提交 cookie、二维码、聊天正文、API key。
- `vendor/open-llm-vtuber` 的既有 submodule 提示不要提交。

---
# 小居居总目标交接（HANDOFF）

> 生成时间：2026-10-27  
> 目标线程：独立人格、长期记忆、自主生活、自然社交，可操作网络和手机，但明确标注 AI 身份。

## 当前目标

构建并验收一个具备稳定人格、长期记忆、自主生活、自然社交表达、可自主上网和操作手机/微信的智能体。它应当在体验上接近真人，但不冒充真人；所有对外社交身份都要标注 AI。预算：100,000,000 token。

## 已完成

- Plan 1 Agent 平台已合并并推送：Postgres、Valkey、Neo4j、OPA、Celery、LangGraph，四个 Compose 服务 healthy。
- OPPO A96 / Android 12 真机 ADB 链路已打通。
- ColorOS 开发者选项 `禁止权限监控` 已打开。
- ADBKeyboard 已安装并启用；首次安装需要保留 OPPO 系统确认页并点击继续安装。
- 微信发送链路已验证：
  - `xjj-test` 真实发送成功；
  - `你好，我是小居居。` 真实中文发送成功；
  - 发送后输入框清空，百度输入法恢复；
  - 发送函数返回 True 且有截图证据。
- `apps/phone_agent/phone_agent.py` 已改为全屏 OCR 定位发送按钮，不再固定使用 0.68–0.80 裁剪区。
- 新增 `src/xiaojuju_core/phone_ui.py` 和 `tests/test_phone_ui.py`，覆盖 OCR 坐标、漏字容错、当前输入法解析。
- 人格与主动消息提示已补充：追问时先兑现具体内容，不编造当前状态，不用“啥啥/发呆”模板；主动消息禁止只卖关子。
- 主动 outbox 发送成功后开始写回聊天历史；连续未回复消息改为聚合识别。
- 已配置 `XiaoJuJu-Phone-Agent` 登录后延迟 20 秒启动。

## 已验证证据

- `uv run --extra dev pytest -q` 曾在平台阶段得到 `106 passed`。
- 手机发送真机截图：
  - `D:\yige-personal-kb\.runtime\phone-agent\screen.png`（中文发送）
  - `D:\yige-personal-kb\.runtime\phone-agent\after-user-sent.png`（用户追问上下文）
- 运行日志：`D:\yige-personal-kb\.runtime\phone-agent\phone-agent.log`
- 运行手册：`D:\yige-personal-kb\xiaojuju\docs\runbooks\wechat-oppo-a96.md`

## 当前未完成 / 风险

- 电话智能体后台进程可能因桌面休眠、任务重启或 Brain Gateway 掉线而停止；需要持续监控和自动重启。
- 最近一次真机追踪发现：
  - 主动消息原先没有写入 state history，已经补了 outbox 写回逻辑但还没有完成最终全链路验收；
  - 连续未回复消息原先只取最后一条，已改为聚合逻辑，但需在真实微信截图上确认稳定；
  - 用户发送 `?` 这类单字符消息时 OCR 可能漏检，需要视觉兜底。
- `uv.lock` 被本机镜像环境重写，属于不应提交的无关变更；最终提交前必须恢复。
- `vendor/open-llm-vtuber` 有原有 submodule 状态提示，不要误提交。
- 当前 phone_agent 代码改动尚未提交，需完成回归、真实收发和风险检查后再提交。
- Brain Gateway 与 Phone Agent 是两个独立进程；登录启动、健康检查、重启策略必须补齐，不能只保证某一次手工启动成功。

## 开源调研结论

严格名为“给她一部手机”的 GitHub 仓库没有找到，最可能是中文传播标题。相关项目：

- `lllq-123/phone-for-ai`：中文名“给 AI 一台手机”，MIT，Android 14+，伴侣 APK + 自托管服务器 + MCP + 网页控制台；只提供手机控制，不含人格/记忆。
- `unitedbyai/droidclaw`：约 1.6k stars，TypeScript/Bun，ADB + 感知→判断→动作循环，适合旧安卓；无明确许可证元数据。
- `zai-org/Open-AutoGLM`：约 26k stars，Apache-2.0，Android 7+，视觉 GUI Agent；适合任务型自动化，但模型 heavier。
- `andycufari/movicom`：MIT，Node.js，控件树菜单化，token 省，但微信实测控件树基本为空，不适合作为微信主链路。

选择原则：保留小居居现有 memory/persona/brain，借鉴 DroidClaw 的循环、Open-AutoGLM 的视觉执行、Phone for AI 的 MCP/伴侣结构；不把手机控制项目当成人格框架。

## 下一步

1. 固化架构接线：Brain Gateway、Phone Agent、Proactive、EventBus、MemoryStore、Outbox 的启动与健康监控必须闭环。
2. 用真实微信完成“新消息 → 上下文 → 自然回复 → 结果验证 → 历史写回”端到端验收。
3. 增加浏览器/网页工具和社交媒体适配器，所有外部操作经过权限、幂等和审计。
4. 建立场景评估集：记忆连续性、追问兑现、主动消息质量、重复发送、断线恢复、AI 身份标注。
5. 通过后再评估是否引入 DroidClaw/Open-AutoGLM 作为独立视觉执行器。

## 相关文件

- `D:\yige-personal-kb\xiaojuju\apps\phone_agent\phone_agent.py`
- `D:\yige-personal-kb\xiaojuju\src\xiaojuju_core\phone_ui.py`
- `D:\yige-personal-kb\xiaojuju\src\xiaojuju_core\brain.py`
- `D:\yige-personal-kb\xiaojuju\src\xiaojuju_core\proactive.py`
- `D:\yige-personal-kb\xiaojuju\src\xiaojuju_core\outbox.py`
- `D:\yige-personal-kb\xiaojuju\prompts\live_persona.md`
- `D:\yige-personal-kb\xiaojuju\docs\runbooks\wechat-oppo-a96.md`
- `D:\yige-personal-kb\xiaojuju\docs\superpowers\plans\2026-10-26-01-agent-platform-foundation.md`
## 2026-10-27 本轮新增接线

- `XiaoJuJu-Agent-API` 已注册为登录后启动任务，端口 `127.0.0.1:12402`；启动脚本设置 `XJJ_SHADOW_MODE=false`。
- 私有配置 `runtime.agent_gateway_url` 已指向 `http://127.0.0.1:12402`，phone_agent 会优先走新 Agent，失败才回退旧 12400。
- 中文联系人 header 已做 URL 编码/API 解码，避免 `UnicodeEncodeError`。
- `src/xiaojuju_agent/memory.py`：新 Agent 可读旧 SQLite 记忆并幂等写回；影子事件不写。
- `src/xiaojuju_agent/outbox.py`：Postgres outbox 支持 enqueue、claim、retry、sent、failed、stale recovery。
- `scripts/run_agent_phone_worker.py`：新 outbox 到手机发送的 worker，复用 phone_agent 并共享实例锁。
- `src/xiaojuju_agent/style.py`：统一清理 Markdown、标题、列表和过长输出。
- `phone_agent` 已支持新 Agent 历史上下文、连续未回复消息、主动消息历史写回；聊天内容裁剪现在按键盘/输入框动态避让。
- 全仓测试本轮通过：`141 passed`。
- 尚未完成：新 outbox worker 的真实发送验收；浏览器 worker；Celery Beat 自主生活/夜间反思；50+ 人格与记忆评估集。

## 当前真机注意

- 微信自动化单轮仍包含多次 OCR，响应可能较慢；需要继续压缩 OCR 区域和缓存截图。
- ADBKeyboard 与百度输入法切换后必须恢复原输入法。
- 手机后台任务和 Agent API 任务都需要健康监控与自动重启。
## 工具回路与最新提交

- 最新 main：`e3b1a6e fix: make autonomous activity goal-aligned and retryable`；此前为 `1fa36db fix: bind browser approvals to event ids`。
- `web_search` 已接入 LangGraph：模型可发起工具调用，`WebSearchTool` 经 OPA 只读检查，结果回到同一 checkpoint。
- 真实 DeepSeek + 公共搜索已验证，返回内容能作为最终回复依据。
- 失败后残留的 dangling tool_call 会自动补 `ToolMessage`，修复顺序是先修复旧工具结果，再追加新用户消息。
- API 生产任务 `XiaoJuJu-Agent-API` 和手机任务 `XiaoJuJu-Phone-Agent` 已重启；API `/healthz`、`/readyz` 通过。
- 当前仍缺：browser-use Web Worker、Mobilerun/视觉手机 Worker、Graphiti 时间图谱、Celery Beat 自主生活/夜间反思、社交媒体外部发布审批、50+ 回归评估集。
## 互联网工具验收

- `web_search` 和 `web_fetch` 均已接入 LangGraph 工具回路。
- `web_fetch` 拒绝 localhost、私网 IP、`.local` 和 `.internal`，公开网页读取由 OPA 允许，写入/登录/发布仍无工具。
- 真实 API 已验证：搜索 Open-AutoGLM 后能回答；读取官方 README 后能用一句话总结项目。
- OPA 版本测试：4/4 passed；OPA 容器已重启加载 `web.fetch` 新策略。
- 生产 API 任务 `XiaoJuJu-Agent-API` 已重启，端口 `127.0.0.1:12402`，health/ready 均通过。
## 自动评估与运行稳定性

- 新增 `src/xiaojuju_agent/evaluation.py`、`scripts/run_persona_eval.py` 和 50 条固定场景：`evals/persona_scenarios.jsonl`。
- 评估会使用 `eval-{run_id}-{scenario_id}` 隔离每次会话，保存 JSONL 明细和 JSON 汇总。
- 最近完整 50 条：49/50（最后一个失败是评分词表把“这个不行/硬边界”判成缺少边界词，定向修正后该场景 1/1）。
- `Database.open` 改为可配置的 `db_open_timeout_seconds=45`，适配 Windows + WSL2 冷启动。
- WSL 必须由 `XiaoJuJu-Agent-Stack`/`sleep infinity` 保活；否则 Docker 容器和端口会反复重建。
- 运行手册：`docs/runbooks/persona-evaluation.md`。
## 浏览器与审批

- `browser_read` 已接入真实 Chrome/Puppeteer 渲染读取，不是简单 HTTP 抓取；已验证 example.com。
- `browser_action` 支持 navigate/click/type/press/wait 计划，但所有动作必须经过 OPA 审批。
- `app_approvals` 已有一键创建待审批、批准、拒绝、过期和一次性消费；审批必须匹配 event_id、工具和参数。
- API 端点：`GET /v1/approvals`、`POST /v1/approvals/{id}/approve`、`POST /v1/approvals/{id}/reject`。
- 运行手册：`docs/runbooks/browser-and-approvals.md`。
- 当前仍不自动发布社交内容；发布必须先明确批准。
## 浏览器动作与审批验收（2026-10-27）

- `browser_read` 已真实打开 example.com 并读取渲染后的标题/正文。
- `browser_action` 会生成 pending 审批，不会在没有批准时执行；真实 API 返回了 approval_id。
- 审批已真实批准、消费并验证状态从 `approved` 变为 `consumed`；审批记录已正确绑定 event_id。
- API：`GET /v1/approvals`、`POST /v1/approvals/{id}/approve`、`POST /v1/approvals/{id}/reject`。
- WSL 现在必须先启动保活；`XiaoJuJu-Agent-Stack` 会启动 WSL/Docker 并保持 `sleep infinity`，否则 Docker 容器会反复重建、端口丢失。
- 当前最新测试：`138 passed`；OPA 4/4。
- 仍未实现：社交媒体平台的自动发布、直播自主运营、Graphiti/Neo4j 长期图谱、Celery Beat 自主生活完整接线。
## 自主生活恢复

- 自主活动 prompt 已强制特定目标围绕目标关键词，不再随意改做章鱼/猫等无关主题。
- 空输出和偏离目标会重试；连续偏离返回 `off_goal`，不写假成果。
- 失败缓存不会永久锁住目标：`daemon.tick` 会创建 `autonomy:<id>:retry:<epoch>`。
- 新增 `run_autonomy.py --force` 作为人工恢复开关。
- 真实验收：微信/抖音收入目标从 failed 恢复为 done；视力防控门店合规获客目标完成并生成 Markdown 成果。
- 最新自主活动日志已写入 `自主生活\活动日志\2026-10-27.jsonl`。
## Graphiti 长期记忆接线

- 新增 `src/xiaojuju_agent/graphiti_memory.py`，Graphiti 0.31.2 + Neo4j 5.26 已实际验证。
- 旧 SQLite/JSONL 同步写，Graphiti 图谱 episode 后台异步写，失败自动回退。
- 召回 8 秒超时；联系人 group_id 用 `contact_<hash>` 隔离。
- 真实 Neo4j 测试：写入后抽取 2 个实体、1 条关系，查询能召回图谱事实。
- 运行手册：`docs/runbooks/graphiti-memory.md`。
- 当前 `HashEmbedder` 是字符 n-gram 临时嵌入；后续应接专用中文 embedding 模型提升语义召回。
## Graphiti 生产验收（2026-10-27 20:35）

- 生产 API 已启用 Graphiti，并修正 `XJJ_DEEPSEEK_API_KEY` 从现有 `DEEPSEEK_API_KEY` 继承，避免图谱写回静默 fallback。
- 同一联系人实际写入后，Neo4j 查询到 **4 个节点、7 条关系**。
- 图谱事实示例：`老大告诉小居居，自己喜欢直接、简短的回答，也不喜欢被催。`
- 聊天回复仍使用后台写回，不等待 DeepSeek 图谱抽取。
- 最新测试：`144 passed`；Graphiti 真实 add/search 已验证。