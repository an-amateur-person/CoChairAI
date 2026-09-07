import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nicegui import ui

from app.api.router import public_router, router
from app.auth.oidc import router as auth_router
from app.config import get_settings
from app.db import init_database
from app.ui.home import register_home_page
from app.ui.meeting_detail import register_meeting_detail_page
from app.workflows.scheduler import create_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_database()
    if not get_settings().auth_enabled:
        logger.warning(
            "Entra sign-in is disabled. Every request runs as the configured development user "
            "and the API is unauthenticated. Set CCHAIR_AUTH_ENABLED=true before deploying."
        )
    scheduler = create_scheduler()
    scheduler.start()
    application.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(public_router)
app.include_router(router)
app.include_router(auth_router)
register_home_page()
register_meeting_detail_page()
ui.run_with(app, storage_secret=settings.ui_storage_secret)