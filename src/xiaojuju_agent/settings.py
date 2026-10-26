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
    deepseek_api_key: SecretStr | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
