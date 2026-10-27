# 社交媒体发布 Runbook

## 目标

把小居居的公开内容发布接入现有 Agent 审批链，同时满足：

- 公开内容明确标注 AI 身份。
- 发布前必须经过一次性人工批准。
- 发布动作和回执可审计、可回滚。
- 发布后打开平台管理页核对标题/正文，不能只看进程退出码。
- 不自动触碰支付、密码和验证码。

## 部署注意

OPA 当前不会自动发现挂载目录中新增的策略内容。修改 `deploy/opa/policies/tools.rego` 后必须重启 OPA：

```powershell
wsl -d UbuntuAgent -u root -- bash -lc "docker restart xiaojuju-agent-opa-1"
```