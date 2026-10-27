# 浏览器读取、动作和审批 Runbook

## 能力边界

- `browser.read`：无副作用，打开公开网页并返回渲染后的标题、URL、正文。
- `browser_action`：提出浏览器动作计划（navigate/click/type/press/wait）。
- 任何 `browser_action` 都是外部副作用，OPA 返回 `require_approval`。
- 影子事件永远拒绝副作用。
- 动作计划最多 20 步；navigate 只允许公开 http(s) URL。
- 不提供任意 JavaScript eval；不绕过 OPA。

## 审批 API

列出待审批：

```powershell
Invoke-RestMethod http://127.0.0.1:12402/v1/approvals
```

批准或拒绝：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:12402/v1/approvals/<approval_id>/approve
Invoke-RestMethod -Method Post http://127.0.0.1:12402/v1/approvals/<approval_id>/reject
```

审批只能消费一次，且必须匹配 `event_id`、工具名和参数。过期后自动失效。

## 当前实现

- `src/xiaojuju_agent/approvals.py`
- `src/xiaojuju_agent/browser.py`
- `scripts/browser_read.js`
- `scripts/browser_act.js`
- `src/xiaojuju_agent/tools.py`

真实浏览器验证：

```powershell
D:\yige-personal-kb\xiaojuju\.venv\Scripts\python.exe -c "from xiaojuju_agent.browser import default_browser_action; print(default_browser_action([{'action':'navigate','url':'https://example.com'},{'action':'wait','ms':10}]))"
```

当前没有自动发布社交内容；发布动作必须先创建待审批计划，由老大明确批准后才执行。