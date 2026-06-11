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
from routes.semanas import router as semanas_router

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
    https_only=False,
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

from jinja2 import pass_context

@pass_context
def get_flashed_messages(context, with_categories=False):
    request = context["request"]
    messages = request.session.get("flashed", [])
    request.session["flashed"] = []
    if with_categories:
        return [(m.get("category", "info"), m.get("message", "")) if isinstance(m, dict) else ("info", m) for m in messages]
    return [m.get("message", m) if isinstance(m, dict) else m for m in messages]

@pass_context
def flash(context, message, category="info"):
    if "flashed" not in context["request"].session:
        context["request"].session["flashed"] = []
    context["request"].session["flashed"].append({"message": message, "category": category})

templates.env.globals["get_flashed_messages"] = get_flashed_messages
templates.env.globals["flash"] = flash
templates.env.filters["fromjson"] = lambda v: json.loads(v) if isinstance(v, str) else v
app.state.templates = templates


# Include routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(draws_router)
app.include_router(payments_router)
app.include_router(admin_router)
app.include_router(api_router)
app.include_router(semanas_router)


# Middleware: no-cache for HTML pages
@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in ("/", "/sorteios", "/pagamentos", "/admin/prizes"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Middleware: track page views
@app.middleware("http")
async def track_page_views(request: Request, call_next):
    response = await call_next(request)

    # Only count HTML page requests (ignore static files, API, favicon)
    path = request.url.path
    if path.startswith("/static") or path.startswith("/api") or path == "/favicon.ico":
        return response
    if not request.headers.get("accept", "").startswith("text/html") and "text/html" not in request.headers.get("accept", ""):
        # Still count even without accept header (some requests)
        pass

    try:
        from database import SessionLocal
        from models.page_view import PageView
        db = SessionLocal()
        try:
            user_id = request.session.get("user_id")
            user_agent = request.headers.get("user-agent", "")[:500]
            page_view = PageView(
                path=path,
                method=request.method,
                status_code=response.status_code,
                ip_address=request.client.host if request.client else None,
                user_agent=user_agent,
                user_id=user_id,
            )
            db.add(page_view)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # Never break the request for analytics

    return response


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
