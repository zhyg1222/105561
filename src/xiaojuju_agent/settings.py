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

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
