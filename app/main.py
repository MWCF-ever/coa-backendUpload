from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from .config import settings
from .database import engine, Base
from .api.v1 import compounds, templates, documents, health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events"""
    # Startup
    logger.info("Starting up COA Document Processor API...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://10.8.63.207:3000",
        "http://10.8.63.207:3000",  # 可选：允许非 https 版本
        "https://localhost:3000",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # 不限制 host（开发环境可用，生产环境请具体指定）
)



# Include routers
app.include_router(
    health.router,
    prefix=f"{settings.API_V1_PREFIX}/health",
    tags=["health"]
)

app.include_router(
    compounds.router,
    prefix=f"{settings.API_V1_PREFIX}/compounds",
    tags=["compounds"]
)

app.include_router(
    templates.router,
    prefix=f"{settings.API_V1_PREFIX}/templates",
    tags=["templates"]
)

app.include_router(
    documents.router,
    prefix=f"{settings.API_V1_PREFIX}/documents",
    tags=["documents"]
)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "COA Document Processor API",
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs"
    }

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "detail": "Resource not found",
        "status_code": 404
    }

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal error: {exc}")
    return {
        "detail": "Internal server error",
        "status_code": 500
    }