# 自主生活运行手册

## 入口

```powershell
$env:DSH_HOME='D:\yige-personal-kb\.runtime\dsh-personal\home'
$env:DSH_TELEMETRY_DISABLED='1'
$env:DSH_TELEMETRY_MODE='DISABLED'
$env:DSH_PERMISSION_MODE='read-only'
$env:PYTHONUTF8='1'
D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe run_autonomy.py --once
```

手动强制重试（仅恢复用，绕过日常频率限制）：

```powershell
D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe run_autonomy.py --once --force
```

## 当前链路

```text
每日目标/兴趣
 -> Activity prompt（目标约束）
 -> DSH 只读公开研究
 -> 目标对齐检查
 -> 活动成果 Markdown
 -> 目标状态、活动日志、反思
 -> 下一轮兴趣
```

## 失败处理

- 空输出：不写成果，返回 `failed`。
- 目标不匹配：第一次重试，第二次仍不匹配则返回 `off_goal`。
- 旧失败缓存不会永久卡住目标：会创建带 `:retry:<epoch>` 的 bus event。
- `--force` 只用于人工恢复，不改变自动任务的频率规则。

## 验证

- 活动文件：`D:\yige-personal-kb\12_社交代理\小居居\自主生活\活动成果`
- 活动日志：`D:\yige-personal-kb\12_社交代理\小居居\自主生活\活动日志`
- 自主审计：`D:\yige-personal-kb\12_社交代理\小居居\行为日志\自主内核.jsonl`
- 已实际恢复：`研究：微信和抖音内容如何转化为收入`
- 已实际完成：`研究：视力防控门店如何合规获取客户`
## 心跳与健康（2026-10-27）

`XiaoJuJu-Autonomy` 每 15 分钟执行一次 `run_autonomy.py --once`，`XiaoJuJu-Proactive-Chat` 每小时执行一次。单次 Python 进程不会常驻，因此健康检查读取心跳文件：

- `D:\yige-personal-kb\.runtime\autonomy\last_run.json`
- `D:\yige-personal-kb\.runtime\proactive\last_run.json`

`scripts\health_check.py` 将 30 分钟内的 autonomy 心跳、2 小时内的 proactive 心跳视为健康；缺失或过期会触发任务重启和 owner 告警 outbox。

手动查看：

```powershell
Get-Content D:\yige-personal-kb\.runtime\autonomy\last_run.json
Get-Content D:\yige-personal-kb\.runtime\proactive\last_run.json
```