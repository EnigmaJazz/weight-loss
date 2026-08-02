"""FastAPI app factory, lifespan wiring, and static file serving."""

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from constants import DB_PATH, INDEX_HTML_PATH, STATIC_DIR, VAPID_KEYS_PATH, get_logger
from database import Database
from notifications import load_or_generate_vapid
from routes import router
from scheduler import scheduler_loop

logger = get_logger("main")


def init_app_state(
    app: FastAPI, *, db_path: str, vapid_path: str
) -> None:
    """Open the DB, create schema, and load/generate VAPID keys."""
    db = Database(db_path)
    db.init_schema()
    app.state.db = db
    app.state.db_path = db_path
    vapid, public_key = load_or_generate_vapid(vapid_path)
    app.state.vapid = vapid
    app.state.vapid_public_key = public_key
    app.state.scheduler_task = None


def create_app(
    *,
    db_path: str = DB_PATH,
    vapid_path: str = VAPID_KEYS_PATH,
    static_dir: str = STATIC_DIR,
    start_scheduler: bool = True,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_app_state(app, db_path=db_path, vapid_path=vapid_path)
        scheduler_task: Optional[asyncio.Task] = None
        if start_scheduler:
            scheduler_task = asyncio.create_task(scheduler_loop(app.state))
            app.state.scheduler_task = scheduler_task
            logger.info("scheduler started")
        yield
        if scheduler_task is not None:
            scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler_task
            logger.info("scheduler stopped")
        app.state.db.close()

    app = FastAPI(title="Weight Loss Tracker", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(router)

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(INDEX_HTML_PATH)

    return app


app = create_app()
