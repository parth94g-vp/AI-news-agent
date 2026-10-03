import pytest

from app.config.settings import ConfigError, Settings


def test_from_env_defaults_and_overrides():
    s = Settings.from_env({"GROQ_API_KEY": "g", "LOOKBACK_HOURS": "12"})
    assert s.groq_model == "llama-3.3-70b-versatile" and s.lookback_hours == 12
    with pytest.raises(ConfigError):
        s.require_news_api()


def test_bad_number_raises():
    with pytest.raises(ConfigError):
        Settings.from_env({"LOOKBACK_HOURS": "abc"})
