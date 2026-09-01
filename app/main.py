from contextlib import asynccontextmanager

from fastapi import FastAPI
from nicegui import ui

from app.api.router import router
from app.config import get_settings
from app.db import init_database
from app.ui.home import register_home_page
from app.workflows.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_database()
    scheduler = create_scheduler()
    scheduler.start()
    application.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)
register_home_page()
ui.run_with(app, storage_secret=settings.ui_storage_secret)