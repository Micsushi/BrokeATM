from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_DEFAULT_DATA_DIR = Path.home() / ".brokeatm"


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    return database_url


class Settings(BaseSettings):
    app_name: str = "BrokeATM"
    app_version: str = "0.1.0"
    data_dir: Path = _DEFAULT_DATA_DIR
    debug: bool = False
    deployment_mode: Literal["local", "cloud"] = "local"
    auth_mode: Literal["none", "supabase", "mock"] = "none"
    database_backend: Literal["sqlite", "supabase_postgres"] = "sqlite"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_key: str | None = None
    supabase_jwt_secret: str | None = None
    site_url: str | None = None
    postgres_url: str | None = None

    model_config = {"env_prefix": "ATM_", "env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def database_url(self) -> str:
        if self.database_backend == "supabase_postgres":
            if not self.postgres_url:
                raise ValueError("ATM_POSTGRES_URL is required for supabase_postgres mode.")
            return normalize_database_url(self.postgres_url)
        return f"sqlite:///{self.data_dir / 'brokeatm.db'}"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def is_cloud_mode(self) -> bool:
        return self.deployment_mode == "cloud"

    @property
    def csv_only_imports(self) -> bool:
        return self.is_cloud_mode

    def prepare_local_storage(self) -> None:
        if self.is_cloud_mode:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.prepare_local_storage()
