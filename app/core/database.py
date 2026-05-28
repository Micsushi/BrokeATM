from collections.abc import Generator, Iterable

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings


def engine_options_for_backend(database_backend: str) -> dict[str, object]:
    options: dict[str, object] = {
        "connect_args": {"check_same_thread": False} if database_backend == "sqlite" else {},
    }
    if database_backend == "supabase_postgres":
        options["poolclass"] = NullPool
    return options


engine = create_engine(
    settings.database_url,
    **engine_options_for_backend(settings.database_backend),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_USER_SCOPE_TABLES = (
    "accounts",
    "categories",
    "transactions",
    "budget_rules",
    "budget_hidden_categories",
    "recurring_rules",
    "import_batches",
    "app_settings",
)


def ensure_local_user_scope_columns(table_names: Iterable[str] = _USER_SCOPE_TABLES) -> None:
    if settings.database_backend != "sqlite":
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name in table_names:
            if table_name not in existing_tables:
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "user_id" in columns:
                continue
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN user_id VARCHAR(36)"))
            connection.execute(
                text(f"CREATE INDEX ix_{table_name}_user_id ON {table_name} (user_id)")
            )


def ensure_budget_hidden_categories_schema() -> None:
    """Upgrade budget_hidden_categories from category_key PK to surrogate id PK.

    Old schema used category_key as the sole PK, which prevents two users from hiding
    the same category in cloud mode. This recreates the table with a surrogate id PK
    and a composite unique constraint on (user_id, category_key).
    """
    if settings.database_backend != "sqlite":
        return

    inspector = inspect(engine)
    if "budget_hidden_categories" not in set(inspector.get_table_names()):
        return
    columns = {col["name"] for col in inspector.get_columns("budget_hidden_categories")}
    if "id" in columns:
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE budget_hidden_categories_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR(36),
                category_key VARCHAR(64) NOT NULL,
                category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                created_at DATETIME,
                UNIQUE(user_id, category_key)
            )
        """))
        conn.execute(text("""
            INSERT INTO budget_hidden_categories_new
                (user_id, category_key, category_id, created_at)
            SELECT user_id, category_key, category_id, created_at
            FROM budget_hidden_categories
        """))
        conn.execute(text("DROP TABLE budget_hidden_categories"))
        conn.execute(text(
            "ALTER TABLE budget_hidden_categories_new RENAME TO budget_hidden_categories"
        ))
        conn.execute(text(
            "CREATE INDEX ix_budget_hidden_categories_user_id "
            "ON budget_hidden_categories(user_id)"
        ))
