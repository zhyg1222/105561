import re


def clean_chat_reply(text: str, max_chars: int = 160) -> str:
    value = re.sub(r"\x1b\[[0-9;]*m", "", str(text or ""))
    value = re.sub(r"^\s*(?:#{1,6}|[-*+]|\d+[.)])\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return ""
    parts = re.split(r"(?<=[。！？!?])", value)
    value = "".join(parts[:2]).strip()
    if len(value) > max_chars:
        value = value[:max_chars].rstrip()
    return value
