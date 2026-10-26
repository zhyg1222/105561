from xiaojuju_agent.settings import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("XJJ_DATABASE_URL", "postgresql://xjj:test@127.0.0.1:5432/xjj")
    monkeypatch.setenv("XJJ_VALKEY_URL", "valkey://127.0.0.1:6379/0")
    monkeypatch.setenv("XJJ_OPA_URL", "http://127.0.0.1:8181")
    monkeypatch.setenv("XJJ_ENVIRONMENT", "test")
    monkeypatch.setenv("XJJ_SHADOW_MODE", "true")
    settings = Settings.from_env()
    assert settings.environment == "test"
    assert settings.shadow_mode is True
    assert settings.database_url.startswith("postgresql://")
