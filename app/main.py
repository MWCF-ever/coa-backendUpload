from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
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
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # 不要因为数据库问题就停止应用启动
    
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

# 修复CORS配置 - 更宽松的设置用于诊断
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://beone-d.beigenecorp.net",
        "https://10.8.63.207:3000",
        "http://10.8.63.207:3000",
        "https://localhost:3000",
        "http://localhost:3000",
        # 添加Office应用可能的域名
        "https://office.live.com",
        "https://outlook.office.com",
        "https://outlook.office365.com",
        "https://teams.microsoft.com",
        # 允许本地和内网访问
        "http://localhost:*",
        "https://localhost:*",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Referer",
        "User-Agent",
    ],
    # 添加预检请求的缓存时间
    max_age=3600,
)

# 添加自定义CORS处理中间件，用于调试
@app.middleware("http")
async def cors_debug_middleware(request: Request, call_next):
    # 记录请求信息用于调试
    logger.info(f"🌐 收到请求: {request.method} {request.url}")
    logger.info(f"📡 Origin: {request.headers.get('origin', 'None')}")
    logger.info(f"🔑 User-Agent: {request.headers.get('user-agent', 'None')}")
    
    # 处理预检请求
    if request.method == "OPTIONS":
        response = JSONResponse({"status": "OK"})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "3600"
        logger.info("✅ 处理OPTIONS预检请求")
        return response
    
    # 处理正常请求
    try:
        response = await call_next(request)
        
        # 确保所有响应都包含CORS头
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        
        logger.info(f"✅ 请求处理完成: {response.status_code}")
        return response
        
    except Exception as e:
        logger.error(f"❌ 请求处理失败: {e}")
        # 即使发生错误也要返回CORS头
        response = JSONResponse(
            {"detail": "Internal server error"},
            status_code=500
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

# Add trusted host middleware - 更宽松的设置
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "beone-d.beigenecorp.net",
        "10.8.63.207",
        "*.beigenecorp.net",
        "*"  # 临时允许所有主机，用于调试
    ]
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

# Root endpoint - 添加更多诊断信息
@app.get("/")
async def root(request: Request):
    return {
        "message": "COA Document Processor API",
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
        "debug_info": {
            "host": request.client.host if request.client else "unknown",
            "headers": dict(request.headers),
            "url": str(request.url),
        }
    }

# 添加专门的连接测试端点
@app.get(f"{settings.API_V1_PREFIX}/test-connection")
async def test_connection(request: Request):
    """专门用于前端连接测试的端点"""
    return {
        "status": "connected",
        "message": "API连接正常",
        "timestamp": "2025-07-29T12:00:00Z",
        "api_version": settings.APP_VERSION,
        "client_info": {
            "ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "origin": request.headers.get("origin", "unknown"),
        }
    }

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "detail": "Resource not found",
        "status_code": 404
    }

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal error on {request.url}: {exc}")
    
    response = JSONResponse({
        "detail": "Internal server error",
        "status_code": 500
    }, status_code=500)
    
    # 确保500响应也包含CORS头
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response
