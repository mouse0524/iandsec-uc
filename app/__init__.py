from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise import Tortoise

from app.core.exceptions import SettingNotFound
from app.core.init_app import (
    init_data,
    make_middlewares,
    register_exceptions,
    register_routers,
)
from app.services.database_backup_service import database_backup_scheduler
from app.services.inactive_user_service import inactive_user_auto_disable_scheduler
from app.services.skill_know.evolution_scheduler import skill_know_evolution_scheduler

try:
    from app.settings.config import settings
except ImportError:
    raise SettingNotFound("Can not import settings")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_data()
    inactive_user_auto_disable_scheduler.start()
    database_backup_scheduler.start()
    skill_know_evolution_scheduler.start()
    try:
        yield
    finally:
        await inactive_user_auto_disable_scheduler.stop()
        await database_backup_scheduler.stop()
        await skill_know_evolution_scheduler.stop()
        await Tortoise.close_connections()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.VERSION,
        openapi_url="/openapi.json" if settings.OPENAPI_ENABLED else None,
        docs_url="/docs" if settings.OPENAPI_ENABLED else None,
        redoc_url="/redoc" if settings.OPENAPI_ENABLED else None,
        middleware=make_middlewares(),
        lifespan=lifespan,
    )
    register_exceptions(app)
    register_routers(app, prefix="/api")
    return app


app = create_app()
