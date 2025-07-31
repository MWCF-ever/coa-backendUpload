# app/main.py - Updated with Authentication
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from .config import settings
from .database import engine, Base
from .api.v1 import compounds, templates, documents, health
from .auth.middleware import AuthLoggingMiddleware, require_authentication, optional_authentication, User

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
    logger.info("Starting up COA Document Processor API with SSO Authentication...")
    
    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # 不要因为数据库问题就停止应用启动
    
    # 验证认证配置
    logger.info("Authentication configuration:")
    logger.info(f"  - Tenant ID: 7dbc552d-50d7-4396-aeb9-04d0d393261b")
    logger.info(f"  - Client ID: 244a9262-04ff-4f5b-8958-2eeb0cedb928")
    logger.info(f"  - Debug mode: {settings.DEBUG}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME + " (SSO Enabled)",
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
    description="COA Document Processor API with Azure AD SSO Authentication"
)

# Add authentication logging middleware
app.add_middleware(AuthLoggingMiddleware)

# CORS中间件配置 - 更新以支持认证头
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://beone-d.beigenecorp.net",
        "https://10.8.63.207:3000",
        "http://10.8.63.207:3000",
        "https://localhost:3000",
        "http://localhost:3000",
        # Office应用可能的域名
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
        "Authorization",  # 重要：允许Authorization头
        "X-Requested-With",
        "Origin",
        "Referer",
        "User-Agent",
        "X-API-Key",
    ],
    max_age=3600,
)

# 增强的CORS处理中间件
@app.middleware("http")
async def enhanced_cors_middleware(request: Request, call_next):
    # 记录请求信息用于调试
    logger.info(f"🌐 收到请求: {request.method} {request.url}")
    logger.info(f"📡 Origin: {request.headers.get('origin', 'None')}")
    
    # 检查认证头
    auth_header = request.headers.get("authorization")
    if auth_header:
        logger.info(f"🔐 Request includes Authorization header")
    else:
        logger.info(f"⚠️  Request without Authorization header")
    
    # 处理预检请求
    if request.method == "OPTIONS":
        response = JSONResponse({"status": "OK"})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "3600"
        logger.info("✅ 处理OPTIONS预检请求")
        return response
    
    # 处理正常请求
    try:
        response = await call_next(request)
        
        # 确保所有响应都包含CORS头
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
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
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

# Add trusted host middleware
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

# 健康检查路由 - 不需要认证
app.include_router(
    health.router,
    prefix=f"{settings.API_V1_PREFIX}/health",
    tags=["health"]
)

# 需要认证的路由
app.include_router(
    compounds.router,
    prefix=f"{settings.API_V1_PREFIX}/compounds",
    tags=["compounds"],
    dependencies=[Depends(require_authentication)]  # 添加认证依赖
)

app.include_router(
    templates.router,
    prefix=f"{settings.API_V1_PREFIX}/templates",
    tags=["templates"],
    dependencies=[Depends(require_authentication)]  # 添加认证依赖
)

app.include_router(
    documents.router,
    prefix=f"{settings.API_V1_PREFIX}/documents",
    tags=["documents"],
    dependencies=[Depends(require_authentication)]  # 添加认证依赖
)

# Root endpoint - 添加认证信息
@app.get("/")
async def root(request: Request, user: User = Depends(optional_authentication)):
    return {
        "message": "COA Document Processor API (SSO Enabled)",
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
        "authentication": {
            "enabled": True,
            "type": "Azure AD SSO",
            "tenant_id": "7dbc552d-50d7-4396-aeb9-04d0d393261b",
            "client_id": "244a9262-04ff-4f5b-8958-2eeb0cedb928"
        },
        "user_info": {
            "authenticated": user is not None,
            "name": user.name if user else None,
            "email": user.email if user else None,
            "roles": user.roles if user else []
        } if user else {"authenticated": False},
        "debug_info": {
            "host": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "origin": request.headers.get("origin", "unknown"),
            "has_auth_header": bool(request.headers.get("authorization")),
        }
    }

# 专门的连接测试端点 - 需要认证
@app.get(f"{settings.API_V1_PREFIX}/test-connection")
async def test_connection_authenticated(
    request: Request, 
    user: User = Depends(require_authentication)
):
    """需要认证的连接测试端点"""
    return {
        "status": "connected",
        "message": "API连接正常 (已认证)",
        "timestamp": "2025-07-29T12:00:00Z",
        "api_version": settings.APP_VERSION,
        "user_info": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "roles": user.roles,
            "tenant_id": user.tenant_id
        },
        "client_info": {
            "ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "origin": request.headers.get("origin", "unknown"),
        }
    }

# 用户信息端点
@app.get(f"{settings.API_V1_PREFIX}/user/me")
async def get_current_user_info(user: User = Depends(require_authentication)):
    """获取当前用户信息"""
    return {
        "success": True,
        "data": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "roles": user.roles,
            "groups": user.groups,
            "tenant_id": user.tenant_id,
            "app_id": user.app_id
        }
    }

# 认证状态检查端点
@app.get(f"{settings.API_V1_PREFIX}/auth/status")
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
            }
        }
    else:
        return {
            "authenticated": False,
            "message": "No valid authentication token provided"
        }

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        {
            "detail": "Resource not found",
            "status_code": 404
        },
        status_code=404,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        }
    )

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    logger.warning(f"Unauthorized access attempt: {request.url}")
    return JSONResponse(
        {
            "detail": "Authentication required",
            "status_code": 401,
            "auth_info": {
                "type": "Bearer",
                "description": "Please provide a valid Azure AD access token"
            }
        },
        status_code=401,
        headers={
            "WWW-Authenticate": "Bearer",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        }
    )

@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    logger.warning(f"Forbidden access attempt: {request.url}")
    return JSONResponse(
        {
            "detail": "Access forbidden",
            "status_code": 403
        },
        status_code=403,
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
        "status_code": 500
    }, status_code=500)
    
    # 确保500响应也包含CORS头
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    
    return response
