# app/main.py - 修复路由前缀问题

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
    # 🔥 关键修复：设置正确的root_path
    root_path="/api/aimta",
    docs_url="/docs",  # 相对于root_path，实际是 /api/aimta/docs
    redoc_url="/redoc"  # 相对于root_path，实际是 /api/aimta/redoc
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://beone-d.beigenecorp.net",
        "https://*.beigenecorp.net",
        "https://office.live.com",
        "https://*.office.live.com",
        "https://outlook.office.com",
        "https://*.outlook.office.com",
        "https://sharepoint.com",
        "https://*.sharepoint.com",
        "https://officeapps.live.com",
        "https://*.officeapps.live.com",
        "https://localhost:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=[
        "Accept", "Accept-Language", "Content-Language", "Content-Type",
        "Authorization", "X-Requested-With", "Origin", "Referer", "User-Agent", "X-API-Key",
    ],
    max_age=3600,
)

# 🔥 修复：健康检查路由 - 直接在根级别，不需要认证
@app.get("/health")
async def health_check():
    """健康检查端点 - /api/aimta/health"""
    return {
        "status": "healthy",
        "timestamp": "2025-08-03T13:15:00Z",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "root_path": "/api/aimta"
    }

# 🔥 修复：认证状态检查端点 - 直接在根级别，不需要强制认证
@app.get("/auth/status")
async def check_auth_status(user: User = Depends(optional_authentication)):
    """检查认证状态 - /api/aimta/auth/status"""
    if user:
        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "roles": user.roles
            }
        }
    else:
        return {
            "authenticated": False,
            "message": "No valid authentication token provided",
            "debug_mode": settings.DEBUG
        }

# 用户信息端点 - 需要认证
@app.get("/user/me")
async def get_current_user_info(user: User = Depends(require_authentication)):
    """获取当前用户信息 - /api/aimta/user/me"""
    return {
        "success": True,
        "data": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "roles": user.roles,
            "groups": getattr(user, 'groups', []),
            "tenant_id": getattr(user, 'tenant_id', None),
            "app_id": getattr(user, 'app_id', None)
        }
    }

# 🔥 DEBUG模式的可选认证依赖
async def debug_optional_auth():
    """调试用的可选认证"""
    try:
        user = await optional_authentication()
        if user:
            logger.info(f"✅ 认证用户访问: {user.email}")
            return user
        else:
            logger.info("⚠️ 匿名用户访问（调试模式）")
            if settings.DEBUG:
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

# 🔥 修复：业务路由 - 不需要额外的前缀，因为已经设置了root_path
app.include_router(
    compounds.router,
    prefix="/compounds",  # 实际路径：/api/aimta/compounds
    tags=["compounds"],
    dependencies=[Depends(auth_dependency)]
)

app.include_router(
    templates.router,
    prefix="/templates",  # 实际路径：/api/aimta/templates
    tags=["templates"],
    dependencies=[Depends(auth_dependency)]
)

app.include_router(
    documents.router,
    prefix="/documents",  # 实际路径：/api/aimta/documents
    tags=["documents"],
    dependencies=[Depends(auth_dependency)]
)

# Root endpoint
@app.get("/")
async def root():
    """根路径 - /api/aimta/"""
    return {
        "message": "COA Document Processor API",
        "version": settings.APP_VERSION,
        "root_path": "/api/aimta",
        "health": "/api/aimta/health",
        "auth_status": "/api/aimta/auth/status",
        "docs": "/api/aimta/docs",
        "debug_mode": settings.DEBUG
    }

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        {
            "detail": "Resource not found",
            "status_code": 404,
            "path": str(request.url.path),
            "root_path": "/api/aimta",
            "requested_url": str(request.url)
        },
        status_code=404,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal error on {request.url}: {exc}")
    
    response = JSONResponse({
        "detail": "Internal server error",
        "status_code": 500,
        "debug_mode": settings.DEBUG,
        "error": str(exc) if settings.DEBUG else "Internal server error"
    }, status_code=500)
    
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    
    return response
