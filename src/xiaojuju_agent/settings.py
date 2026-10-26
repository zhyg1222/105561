from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="XJJ_", extra="ignore")

    database_url: str
    valkey_url: str
    opa_url: str
    environment: Literal["dev", "test", "prod"] = "dev"
    shadow_mode: bool = True
    deepseek_api_key: SecretStr | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
