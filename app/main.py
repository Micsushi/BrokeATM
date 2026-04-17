import logging
import threading
from pathlib import Path

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    accounts_router,
    budget_router,
    categories_router,
    dashboard_router,
    import_router,
    recurring_router,
    settings_router,
    transactions_router,
)
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.services.app_settings import ensure_app_settings
from app.services.starter_categories import seed_starter_categories

Base.metadata.create_all(bind=engine)


def _prewarm_ocr() -> None:
    try:
        from app.services.parsers.ocr_parser import _get_reader
        _get_reader()
    except Exception:
        pass


threading.Thread(target=_prewarm_ocr, daemon=True).start()

with SessionLocal() as _db:
    seed_starter_categories(_db)
    ensure_app_settings(_db)

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

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(TEMPLATES_DIR / "dashboard.html"))


@app.get("/import")
def import_page() -> FileResponse:
    return FileResponse(str(TEMPLATES_DIR / "index.html"))


@app.get("/records")
def records() -> FileResponse:
    return FileResponse(str(TEMPLATES_DIR / "records.html"))


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(str(TEMPLATES_DIR / "dashboard.html"))


@app.get("/categories")
def categories_page() -> FileResponse:
    return FileResponse(str(TEMPLATES_DIR / "categories.html"))


@app.get("/settings")
def settings_page() -> FileResponse:
    return FileResponse(str(TEMPLATES_DIR / "settings.html"))


@app.get("/budget")
def budget_page() -> FileResponse:
    return FileResponse(str(TEMPLATES_DIR / "budget.html"))
