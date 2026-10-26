# XiaoJuJu

小居居的自主智能体代码仓库。

## 当前范围

- 公开身份与凭证字段安全
- 状态、长期记忆、目标队列和每日计划
- 权限、审计与自主活动执行
- 后续开源组件接线：Open-LLM-VTuber、Live2D、TTS、平台适配器

## 不进入仓库

- 私人聊天与关系记忆
- 账号密码、验证码、Cookie、Token
- 运行缓存、日志、截图和模型文件
- 第三方项目源码本体；后续优先使用 Git Submodule 或独立安装目录

## 测试

```powershell
$env:PYTHONPATH = "D:\yige-personal-kb\xiaojuju\src"
$env:TMP = "D:\yige-personal-kb\.runtime\tmp"
$env:TEMP = $env:TMP
D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe -m unittest discover -s D:\yige-personal-kb\xiaojuju\tests -v
```

## 设计资料

- `docs/2026-10-26-自主互联网智能体与直播设计.md`
- `docs/2026-10-26-自主内核与每日生活实施计划.md`
## 自主内核运行

```powershell
# 查看状态
D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe D:\yige-personal-kb\xiaojuju\run_autonomy.py --status

# 单次 dry-run
D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe D:\yige-personal-kb\xiaojuju\run_autonomy.py --once --dry-run

# 暂停/恢复
D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe D:\yige-personal-kb\xiaojuju\run_autonomy.py --pause
D:\yige-personal-kb\.runtime\wechat-operator\.venv\Scripts\python.exe D:\yige-personal-kb\xiaojuju\run_autonomy.py --resume
```

Windows 计划任务：`XiaoJuJu-Autonomy`，每 15 分钟执行一次 `--once`。安全限制为每日最多 4 次活动、间隔至少 120 分钟、00:00—07:30 静默。
