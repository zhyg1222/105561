from pathlib import Path
from .storage import read_json

SECRET_KEYS = {"password","passwd","token","cookie","secret","api_key","verification_code"}

def assert_no_secret_fields(data: object) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower() in SECRET_KEYS:
                raise ValueError(f"secret field not allowed: {key}")
            assert_no_secret_fields(value)
    elif isinstance(data, list):
        for item in data:
            assert_no_secret_fields(item)

def load_public_identity(path: Path | None = None) -> dict:
    p = Path(path) if path else Path(r"D:\yige-personal-kb\12_社交代理\小居居\身份\账号清单.json")
    data = read_json(p, {"version": 1, "display_name": "小居居", "accounts": []})
    assert_no_secret_fields(data)
    return data