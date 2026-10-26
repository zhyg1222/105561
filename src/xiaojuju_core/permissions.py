ALLOW = {"web_search", "web_fetch", "read_local", "write_workspace", "research", "reflect"}
ASK = {"send_message", "publish_public", "contact_stranger", "download_file", "login"}
DENY = {"read_password", "read_cookie", "read_token", "bypass_captcha", "bulk_message", "harass", "spend_money"}

def check_permission(action: str, source: str = "self") -> tuple[str, str]:
    if action in DENY:
        return "deny", "action is forbidden"
    if action in ALLOW:
        return "allow", "safe local or public-read action"
    if action in ASK:
        return "ask", "external or sensitive action requires confirmation"
    return "ask", "unknown action"