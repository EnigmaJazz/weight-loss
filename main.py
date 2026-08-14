"""FastAPI app factory, lifespan wiring, and static file serving."""

import asyncio
import os
import subprocess
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from constants import (
    DB_PATH,
    INDEX_HTML_PATH,
    STATIC_DIR,
    SW_PATH,
    VAPID_KEYS_PATH,
    get_logger,
)
from database import Database
from notifications import load_or_generate_vapid
from routes import router
from scheduler import scheduler_loop

logger = get_logger("main")

# Script srcs in index.html that need cache busting on deploy.
_JS_SCRIPTS = ("/static/format.js", "/static/auth.js", "/static/app.js")
# Stylesheet link hrefs that need the same treatment: without a version
# stamp, browsers keep the old CSS forever (ETag/Last-Modified are weak
# signals and there is no Cache-Control) and display fixes appear broken.
_CSS_HREFS = ("/static/style.css",)


def _cache_stamp() -> str:
    """Short git commit at boot, falling back to the index file mtime.
    Called once during app startup, never in the request path."""
    try:
        stamp = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        stamp = str(os.path.getmtime(INDEX_HTML_PATH)).replace(".", "")
    return stamp


def _stamped_index_html() -> str:
    """Read index.html and inject ?v=<stamp> into the script srcs so a deploy
    changes the URLs and browsers fetch the new bundle instead of the cached
    one. Called once at startup; the result is served from app.state."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as fh:
        html = fh.read()
    stamp = _cache_stamp()
    for src in _JS_SCRIPTS:
        html = html.replace(f'src="{src}"', f'src="{src}?v={stamp}"')
    for href in _CSS_HREFS:
        html = html.replace(f'href="{href}"', f'href="{href}?v={stamp}"')
    return html


def init_app_state(
    app: FastAPI, *, db_path: str, vapid_path: str
) -> None:
    """Open the DB, create schema, reconcile rewards, and load/generate VAPID
    keys."""
    db = Database(db_path)
    db.init_schema()
    db.reconcile_active_rewards()
    db.reconcile_all_weekly_awards()
    app.state.db = db
    app.state.db_path = db_path
    vapid, public_key = load_or_generate_vapid(vapid_path)
    app.state.vapid = vapid
    app.state.vapid_public_key = public_key
    app.state.scheduler_task = None
    # Precompute the cache-busted index once at startup: the route then
    # serves it with no subprocess or file I/O in the request path.
    app.state.index_html = _stamped_index_html()


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
    async def index() -> Response:
        return Response(
            app.state.index_html,
            media_type="text/html",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/sw.js")
    async def service_worker() -> FileResponse:
        # Serve the service worker from the web root so its scope covers /
        # (a SW at /static/ cannot claim the root scope; push registration
        # relies on it controlling the page).
        return FileResponse(
            SW_PATH, headers={"Cache-Control": "no-store"}
        )

    return app


app = create_app()
