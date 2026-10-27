from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="XJJ_", extra="ignore")

    database_url: str = "postgresql://xiaojuju:xjj-dev-postgres@127.0.0.1:5432/xiaojuju"
    valkey_url: str = "redis://:xjj-dev-valkey@127.0.0.1:6379/0"
    opa_url: str = "http://127.0.0.1:8181"
    environment: Literal["dev", "test", "prod"] = "dev"
    shadow_mode: bool = True
    db_open_timeout_seconds: float = 45.0
    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    graphiti_enabled: bool = False
    neo4j_uri: str = "neo4j://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr | None = None
    otel_exporter_otlp_endpoint: str | None = None
    identity_dir: Path = Path("D:/yige-personal-kb/12_\u793e\u4ea4\u4ee3\u7406/\u5c0f\u5c45\u5c45")
    social_publish_enabled: bool = False
    social_publish_home: Path = Path("D:/yige-personal-kb/.runtime/social-auto-upload")
    social_publish_media_root: Path = Path("D:/yige-personal-kb/12_\u793e\u4ea4\u4ee3\u7406/\u5c0f\u5c45\u5c45/\u7d20\u6750")
    social_publish_receipts_dir: Path = Path("D:/yige-personal-kb/.runtime/social-publish/receipts")
    social_publish_timeout_seconds: float = 900.0
    social_identity_label: str = "\u3010AI\u667a\u80fd\u4f53\u00b7\u5c0f\u5c45\u5c45\u3011"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
