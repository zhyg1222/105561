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