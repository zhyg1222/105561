import copy, json
from pathlib import Path
from .storage import read_json

DEFAULT_CONFIG = Path(r"D:\yige-personal-kb\xiaojuju\config\xiaojuju.default.json")
PRIVATE_CONFIG = Path(r"D:\yige-personal-kb\12_社交代理\小居居\配置\私有.json")

def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result

def _valid_time(value: str) -> bool:
    try:
        hour, minute = str(value).split(":", 1)
        return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59
    except Exception:
        return False

def validate_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    identity = config.get("identity", {})
    if identity.get("ai_label") != "AI智能体":
        raise ValueError("identity.ai_label must be AI智能体")
    browser = config.get("browser", {})
    if browser.get("private_network") is not False:
        raise ValueError("browser.private_network must be false")
    if browser.get("public_http") is not True:
        raise ValueError("browser.public_http must be true")
    social = config.get("social", {})
    if social.get("unknown_contacts") != "do_not_reply":
        raise ValueError("unknown contacts must not be auto-replied")
    autonomy = config.get("autonomy", {})
    limit = int(autonomy.get("activity_limit_per_day", 4))
    if not 1 <= limit <= 12:
        raise ValueError("activity_limit_per_day must be 1..12")
    if int(autonomy.get("activity_gap_minutes", 120)) < 30:
        raise ValueError("activity_gap_minutes must be at least 30")
    quiet = autonomy.get("quiet_hours", [])
    if not isinstance(quiet, list) or len(quiet) != 2 or not all(_valid_time(x) for x in quiet):
        raise ValueError("quiet_hours must contain two HH:MM values")
    publishing = config.get("publishing", {})
    if publishing.get("ai_label_required") is not True:
        raise ValueError("publishing.ai_label_required must be true")
    if publishing.get("require_human_review_for_sensitive") is not True:
        raise ValueError("sensitive publishing must require human review")
    constitution = config.get("constitution", {})
    if constitution.get("immutable") is not True or not str(constitution.get("file", "")).strip():
        raise ValueError("immutable personality constitution is required")
    character = config.get("character", {})
    if not str(character.get("file", "")).strip():
        raise ValueError("character file is required")
    habits = config.get("habits", {})
    if habits.get("force_daily_report") is not False:
        raise ValueError("habits must not force daily reports")
    if habits.get("casual_chat_allowed") is not True:
        raise ValueError("casual chat must be allowed")
    goals = config.get("goals", {})
    if goals.get("money_research_enabled"):
        brief = goals.get("daily_brief", {})
        if brief.get("enabled"):
            if brief.get("channel") != "wechat":
                raise ValueError("daily brief channel must be wechat")
            if not _valid_time(brief.get("time", "")):
                raise ValueError("daily brief time must be HH:MM")
            if not str(brief.get("contact", "")).strip():
                raise ValueError("daily brief contact is required")
            if not 1 <= int(brief.get("max_items", 3)) <= 5:
                raise ValueError("daily brief max_items must be 1..5")
        forbidden = set(goals.get("forbidden_actions", []))
        if "autonomous_trading" not in forbidden or "autonomous_spending" not in forbidden:
            raise ValueError("money research must forbid autonomous trading and spending")
    return config

def load_config(default_path: Path | None = None, private_path: Path | None = None) -> dict:
    base = read_json(Path(default_path) if default_path else DEFAULT_CONFIG, None)
    if not isinstance(base, dict):
        raise ValueError("default config missing or invalid")
    private = read_json(Path(private_path) if private_path else PRIVATE_CONFIG, {})
    if not isinstance(private, dict):
        raise ValueError("private config must be an object")
    return validate_config(deep_merge(base, private))