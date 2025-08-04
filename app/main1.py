# app/main.py - 紧急CORS修复，超级宽松配置

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from .config import settings
from .database import engine, Base
from .api.v1 import compounds, templates, documents, health
from .auth.middleware import require_authentication, optional_authentication, User

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events"""
    logger.info("Starting up COA Document Processor API...")
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    yield
    logger.info("Shutting down...")

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    root_path="/api/aimta",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 🔥 紧急修复：最宽松的CORS配置
@app.middleware("http")
async def emergency_cors_middleware(request: Request, call_next):
    """紧急CORS修复中间件 - 允许所有请求"""
    
    origin = request.headers.get("origin")
    
    # 处理OPTIONS预检请求
    if request.method == "OPTIONS":
        response = JSONResponse({"status": "ok"})
        
        # 超级宽松的CORS头
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "86400"
        response.headers["Vary"] = "Origin"
        
        logger.info(f"🚀 CORS预检通过: {origin}")
        
        return response
    
    # 处理实际请求
    try:
        response = await call_next(request)
        
        # 为所有响应添加CORS头
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Vary"] = "Origin"
        
        logger.info(f"✅ CORS响应头已添加: {origin}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ 请求处理错误: {e}")
        
        # 即使出错也要添加CORS头
        error_response = JSONResponse(
            {"error": "Internal server error", "detail": str(e)},
            status_code=500
        )
        
        error_response.headers["Access-Control-Allow-Origin"] = origin or "*"
        error_response.headers["Access-Control-Allow-Credentials"] = "true"
        error_response.headers["Access-Control-Allow-Methods"] = "*"
        error_response.headers["Access-Control-Allow-Headers"] = "*"
        error_response.headers["Vary"] = "Origin"
        
        return error_response

# 🔥 添加标准CORS中间件作为备用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 临时允许所有源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)

# 🔥 CORS测试端点
@app.get("/cors-test")
async def cors_test():
    """CORS测试端点"""
    return {
        "message": "CORS test successful from backend",
        "timestamp": "2025-08-04T20:00:00Z",
        "cors_working": True,
        "service": settings.APP_NAME,
        "debug": "Emergency CORS fix applied"
    }

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": "2025-08-04T20:00:00Z",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "root_path": "/api/aimta",
        "cors_emergency_fix": True
    }

# 认证状态检查端点
@app.get("/auth/status")
async def check_auth_status(user: User = Depends(optional_authentication)):
    """检查认证状态"""
    if user:
        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "roles": user.roles
            },
            "cors_working": True
        }
    else:
        return {
            "authenticated": False,
            "message": "No valid authentication token provided",
            "debug_mode": settings.DEBUG,
            "cors_working": True
        }

# DEBUG模式的可选认证依赖
async def debug_optional_auth():
    """调试用的可选认证"""
    try:
        user = await optional_authentication()
        if user:
            logger.info(f"✅ 认证用户访问: {user.email}")
            return user
        else:
            if settings.DEBUG:
                logger.info("⚠️ DEBUG模式：使用虚拟用户")
                class DebugUser:
                    def __init__(self):
                        self.id = "debug-user-id"
                        self.name = "Debug User"
                        self.email = "debug@beigene.com"
                        self.roles = ["user"]
                return DebugUser()
            return None
    except Exception as e:
        logger.error(f"❌ 认证过程出错: {e}")
        if settings.DEBUG:
            class DebugUser:
                def __init__(self):
                    self.id = "debug-user-id"
                    self.name = "Debug User"
                    self.email = "debug@beigene.com"
                    self.roles = ["user"]
            return DebugUser()
        return None

# 选择认证策略
auth_dependency = debug_optional_auth if settings.DEBUG else require_authentication

# 业务路由
app.include_router(
    compounds.router,
    prefix="/compounds",
    tags=["compounds"],
    dependencies=[Depends(auth_dependency)]
)

app.include_router(
    templates.router,
    prefix="/templates",
    tags=["templates"],
    dependencies=[Depends(auth_dependency)]
)

app.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(auth_dependency)]
)

# Root endpoint
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "COA Document Processor API",
        "version": settings.APP_VERSION,
        "root_path": "/api/aimta",
        "endpoints": {
            "health": "/api/aimta/health",
            "cors_test": "/api/aimta/cors-test",
            "auth_status": "/api/aimta/auth/status",
            "compounds": "/api/aimta/compounds",
            "templates": "/api/aimta/templates",
            "documents": "/api/aimta/documents",
            "docs": "/api/aimta/docs"
        },
        "debug_mode": settings.DEBUG,
        "cors_emergency_fix": True
    }

# Exception handlers with CORS support
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    origin = request.headers.get("origin", "*")
    
    response = JSONResponse(
        {
            "detail": "Resource not found",
            "status_code": 404,
            "path": str(request.url.path),
            "method": request.method,
            "available_endpoints": [
                "/api/aimta/health",
                "/api/aimta/cors-test",
                "/api/aimta/auth/status",
                "/api/aimta/compounds",
                "/api/aimta/templates",
                "/api/aimta/documents"
            ]
        },
        status_code=404
    )
    
    # 添加CORS头
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal error on {request.url}: {exc}")
    origin = request.headers.get("origin", "*")
    
    response = JSONResponse({
        "detail": "Internal server error",
        "status_code": 500,
        "debug_mode": settings.DEBUG,
        "error": str(exc) if settings.DEBUG else "Internal server error"
    }, status_code=500)
    
    # 添加CORS头
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

# 启动时日志
logger.info("🚀 COA API服务启动 (紧急CORS修复版)")
logger.info(f"📍 Root path: /api/aimta")
logger.info(f"🔧 Debug mode: {settings.DEBUG}")
logger.info("🌐 紧急CORS修复已启用 - 允许所有源访问")
