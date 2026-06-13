from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    base_url: str = "https://openapi.tossinvest.com"
    live_trading_enabled: bool = False

    @classmethod
    def from_env(cls, *, dotenv_path: str | Path | None = None) -> "Config":
        load_dotenv(dotenv_path=dotenv_path or Path.cwd() / ".env")

        client_id = os.getenv("API_KEY")
        client_secret = os.getenv("SECRET_KEY")
        missing = [name for name, value in (("API_KEY", client_id), ("SECRET_KEY", client_secret)) if not value]
        if missing:
            raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            base_url=os.getenv("TOSS_BASE_URL", cls.base_url),
            live_trading_enabled=os.getenv("TOSS_LIVE_TRADING") == "true",
        )
