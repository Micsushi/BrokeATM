from pathlib import Path

from pydantic_settings import BaseSettings

_DEFAULT_DATA_DIR = Path.home() / ".brokeatm"


class Settings(BaseSettings):
    app_name: str = "BrokeATM"
    app_version: str = "0.1.0"
    data_dir: Path = _DEFAULT_DATA_DIR
    debug: bool = False

    model_config = {"env_prefix": "ATM_", "env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'brokeatm.db'}"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
