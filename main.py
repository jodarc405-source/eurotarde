import json
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from config import get_settings
from database import init_db
from services.scheduler import start_scheduler, stop_scheduler

# Import routers
from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.draws import router as draws_router
from routes.payments import router as payments_router
from routes.admin import router as admin_router
from routes.api import router as api_router

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Eurotarde",
    description="Gestão de Sorteios do Euromilhões",
    version="1.0.0",
)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.***REDACTED***,
    max_age=settings.SESSION_MAX_AGE,
    same_site="lax",
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")
templates.env.filters["fromjson"] = lambda v: json.loads(v) if isinstance(v, str) else v
app.state.templates = templates


# Include routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(draws_router)
app.include_router(payments_router)
app.include_router(admin_router)
app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Eurotarde application...")
    init_db()
    start_scheduler()
    logger.info("Eurotarde is ready!")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Eurotarde...")
    stop_scheduler()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
