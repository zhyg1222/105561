# 备份恢复演练 Runbook

## 目标

验证 PostgreSQL 持久化事件/记忆队列可以完整恢复，同时验证 Graphiti/Neo4j 的 episode 可以逻辑导出、导入临时集合并删除，不触碰生产数据。

## 执行

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\backup_restore_drill.ps1
```

脚本会：

1. 在 `D:\yige-personal-kb\.runtime\backups\drill-<时间>` 下保存 PostgreSQL custom dump。
2. 创建名称受正则约束的 `xiaojuju_restore_<时间>` 临时数据库。
3. 用 `pg_restore --no-owner --no-privileges` 恢复并比较生产/恢复后的关键表行数。
4. 导出一个 Neo4j episode 逻辑快照，再导入 `restore_<时间>` 临时集合并核对数量，自动清理。
5. 最后删除临时数据库，不删除生产数据库。

## 最近一次实测（2026-10-27）

- PostgreSQL 行数：生产 `514|230|0|3`，恢复库 `514|230|0|3`
- PostgreSQL dump：`1,764,225` bytes
- Neo4j：导出 `236` 个 episode、`442` 条关系；临时集合恢复 `236` 个 episode
- 临时数据库已删除，`pg_database` 中没有残留 `xiaojuju_restore_%`

## 边界

- PostgreSQL 使用 custom dump 全量恢复。
- Neo4j 当前演练是 episode 逻辑导入/导出，不是企业版在线物理备份；后续可增加 `neo4j-admin` 离线 dump 窗口。
- 不对生产库执行 `dropdb`、`down -v` 或清空命名卷。
- 恢复脚本创建的临时数据库必须匹配 `xiaojuju_restore_[0-9]{8}_[0-9]{6}`。