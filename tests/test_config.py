import pytest

from auto_toss.config import Config, ConfigError


def test_config_reads_required_credentials_without_printing_values(monkeypatch):
    monkeypatch.setenv("API_KEY", "client-id")
    monkeypatch.setenv("SECRET_KEY", "client-secret")

    config = Config.from_env()

    assert config.client_id == "client-id"
    assert config.client_secret == "client-secret"
    assert "client-secret" not in repr(config)


def test_config_requires_credentials(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ConfigError, match="API_KEY"):
        Config.from_env()


def test_live_trading_requires_exact_true(monkeypatch):
    monkeypatch.setenv("API_KEY", "client-id")
    monkeypatch.setenv("SECRET_KEY", "client-secret")
    monkeypatch.setenv("TOSS_LIVE_TRADING", "true")

    assert Config.from_env().live_trading_enabled is True
