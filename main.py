import json
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
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

from services.flash_service import flash

@pass_context
def get_flashed_messages(context, with_categories=False):
    request = context["request"]
    messages = request.session.get("flashed", [])
    request.session["flashed"] = []
    if with_categories:
        return [(m.get("category", "info"), m.get("message", "")) if isinstance(m, dict) else ("info", m) for m in messages]
    return [m.get("message", m) if isinstance(m, dict) else m for m in messages]

templates.env.globals["get_flashed_messages"] = get_flashed_messages
templates.env.globals["flash"] = flash
templates.env.filters["fromjson"] = lambda v: json.loads(v) if isinstance(v, str) else v
app.state.templates = templates


# Exception handler: redirect unauthenticated (401) requests to login.
# Used by the require_auth dependency on protected routes (e.g. /sorteios/my-keys).
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/auth/login", status_code=302)
    if exc.status_code == 403:
        # Forbidden — usually a non-admin hitting an admin-only action.
        # Flash a message and send them back to the society-key page.
        if "flashed" not in request.session:
            request.session["flashed"] = []
        request.session["flashed"].append(
            {"message": exc.detail or "Não tens permissão para esta ação.", "category": "warning"}
        )
        return RedirectResponse(url="/sorteios/my-keys", status_code=302)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


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
    # NOTE: defensive startup. A failure in init_db / start_scheduler must NOT
    # crash uvicorn — otherwise Render marks the deploy as failed and keeps
    # serving the previous (stale) build. Log and continue instead.
    try:
        init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.error(f"init_db failed (continuing anyway): {e}")
    try:
        start_scheduler()
        logger.info("Scheduler started.")
    except Exception as e:
        logger.error(f"start_scheduler failed (continuing anyway): {e}")
    logger.info("Eurotarde is ready!")


@app.get("/health", tags=["system"])
async def health_check():
    """Lightweight health/diagnostics endpoint (no auth).

    Returns draw/prize counts so we can verify the DB was populated
    after a deploy without needing an admin login.
    """
    from database import SessionLocal, engine
    from models.draw import Draw
    from models.draw_prize import DrawPrize
    from models.key import Key
    db = SessionLocal()
    try:
        draws = db.query(Draw).count()
        with_prizes = db.query(DrawPrize).count()
        society = db.query(Key).filter(Key.is_society == True).count()
        return {
            "status": "ok",
            "draws": draws,
            "draws_with_prizes": with_prizes,
            "society_keys": society,
        }
    except Exception as e:
        # Surface the real error instead of a generic 500 so we can debug
        # environment-specific failures (e.g. driver/SSL issues on Render).
        import traceback
        logger.error(f"/health failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "db_url": str(engine.url).split("@")[-1],
            "traceback": traceback.format_exc().splitlines()[-5:],
        }
    finally:
        db.close()


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Eurotarde...")
    stop_scheduler()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
