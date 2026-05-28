import logging
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import (
    accounts_router,
    budget_router,
    categories_router,
    dashboard_router,
    import_router,
    recurring_router,
    runtime_router,
    settings_router,
    transactions_router,
)
from app.core.config import settings
from app.core.database import (
    Base,
    SessionLocal,
    engine,
    ensure_budget_hidden_categories_schema,
    ensure_local_user_scope_columns,
)
from app.services.app_settings import ensure_app_settings
from app.services.recurring_service import process_due_rules
from app.services.starter_categories import seed_starter_categories

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

def _prewarm_ocr() -> None:
    try:
        from app.services.parsers.ocr_parser import _get_reader
        _get_reader()
    except Exception:
        pass


def _initialize_local_runtime() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_local_user_scope_columns()
    ensure_budget_hidden_categories_schema()
    threading.Thread(target=_prewarm_ocr, daemon=True).start()
    with SessionLocal() as _db:
        seed_starter_categories(_db)
        ensure_app_settings(_db)
        process_due_rules(_db)


if not settings.is_cloud_mode:
    _initialize_local_runtime()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.include_router(import_router.router)
app.include_router(transactions_router.router)
app.include_router(categories_router.router)
app.include_router(accounts_router.router)
app.include_router(dashboard_router.router)
app.include_router(recurring_router.router)
app.include_router(budget_router.router)
app.include_router(settings_router.router)
app.include_router(runtime_router.router)

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


_NO_CACHE = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _html(name: str) -> FileResponse:
    return FileResponse(str(TEMPLATES_DIR / name), headers=_NO_CACHE)


@app.get("/")
def index() -> FileResponse:
    return _html("dashboard.html")


@app.get("/login")
def login() -> Response:
    if settings.auth_mode == "none":
        return RedirectResponse(url="/")
    return _html("login.html")


@app.get("/import")
def import_page() -> FileResponse:
    return _html("index.html")


@app.get("/records")
def records() -> FileResponse:
    return _html("records.html")


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return _html("dashboard.html")


@app.get("/categories")
def categories_page() -> FileResponse:
    return _html("categories.html")


@app.get("/settings")
def settings_page() -> FileResponse:
    return _html("settings.html")


@app.get("/budget")
def budget_page() -> FileResponse:
    return _html("budget.html")


@app.get("/recurring")
def recurring_page() -> FileResponse:
    return _html("recurring.html")
