import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.database import init_db
from api.routes import auth, session, memory, voice, vision
from api.routes.browser import router as browser_router, get_browser_agent

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("aira.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AIRA backend starting up...")
    await init_db()
    logger.info("Database tables verified / created.")

    # Browser is NOT pre-warmed on startup.
    # It will launch automatically the first time AIRA needs it (on-demand).
    logger.info("Browser agent ready (will launch on first use).")

    yield

    # Shutdown — stop browser only if it was actually started during this session
    try:
        agent = get_browser_agent()
        if agent.is_running:
            await agent.stop()
            logger.info("Browser agent stopped.")
    except Exception:
        pass

    logger.info("AIRA backend shutting down...")


app = FastAPI(
    title="AIRA — AI Real-time Agent API",
    description=(
        "Backend API for AIRA, a next-generation multimodal AI agent. "
        "Supports voice streaming, vision understanding, persistent memory, "
        "goal planning, and computer-use automation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str) -> JSONResponse:
    return JSONResponse(
        content={"detail": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


app.include_router(auth.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(vision.router, prefix="/api/v1")
app.include_router(browser_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "version": "1.0.0",
    }


@app.get("/", tags=["Root"])
async def root() -> dict:
    return {
        "message": "Welcome to the AIRA API. Visit /docs for the full API reference.",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )