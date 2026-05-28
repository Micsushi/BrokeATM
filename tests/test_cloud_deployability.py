from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.pool import NullPool

from app.core.config import Settings, normalize_database_url
from app.core.database import engine_options_for_backend

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_supabase_postgres_url_uses_psycopg_driver() -> None:
    assert (
        normalize_database_url("postgresql://user:pass@example.supabase.co/postgres")
        == "postgresql+psycopg://user:pass@example.supabase.co/postgres"
    )
    assert (
        normalize_database_url("postgres://user:pass@example.supabase.co/postgres")
        == "postgresql+psycopg://user:pass@example.supabase.co/postgres"
    )
    assert (
        normalize_database_url("postgresql+psycopg://user:pass@example.supabase.co/postgres")
        == "postgresql+psycopg://user:pass@example.supabase.co/postgres"
    )


def test_cloud_settings_do_not_create_local_storage_dirs(tmp_path: Path) -> None:
    cloud_data_dir = tmp_path / "cloud-data"
    settings = Settings(
        data_dir=cloud_data_dir,
        deployment_mode="cloud",
        _env_file=None,
    )

    settings.prepare_local_storage()

    assert not cloud_data_dir.exists()


def test_local_settings_create_local_storage_dirs(tmp_path: Path) -> None:
    local_data_dir = tmp_path / "local-data"
    settings = Settings(
        data_dir=local_data_dir,
        deployment_mode="local",
        _env_file=None,
    )

    settings.prepare_local_storage()

    assert local_data_dir.exists()
    assert (local_data_dir / "uploads").exists()


def test_supabase_postgres_engine_uses_null_pool() -> None:
    options = engine_options_for_backend("supabase_postgres")

    assert options["connect_args"] == {}
    assert options["poolclass"] is NullPool


def test_cloud_entrypoint_import_does_not_touch_db_or_local_storage(tmp_path: Path) -> None:
    cloud_data_dir = tmp_path / "cloud-data"
    env = os.environ.copy()
    env.update(
        {
            "ATM_DATA_DIR": str(cloud_data_dir),
            "ATM_DEPLOYMENT_MODE": "cloud",
            "ATM_AUTH_MODE": "supabase",
            "ATM_DATABASE_BACKEND": "supabase_postgres",
            "ATM_POSTGRES_URL": "postgresql://user:pass@localhost:5432/postgres",
            "ATM_SUPABASE_URL": "https://example.supabase.co",
            "ATM_SUPABASE_ANON_KEY": "anon-key",
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import app.main; "
                "from app.core.config import settings; "
                "from app.core.database import engine; "
                "print(settings.database_url); "
                "print(engine.dialect.driver); "
                "print(app.main.app.title)"
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "postgresql+psycopg://user:pass@localhost:5432/postgres" in result.stdout
    assert "psycopg" in result.stdout
    assert "BrokeATM" in result.stdout
    assert not cloud_data_dir.exists()
