import logging
import sys
import traceback
from pathlib import Path

# 保证无论从哪启动，都能正确加载 backend 下的模块
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# 在加载 FastAPI 前放宽 multipart 默认限制，避免 4MB+ 上传触发 Part exceeded maximum size
try:
    from starlette.formparsers import MultiPartParser
    MultiPartParser.max_part_size = 20 * 1024 * 1024  # 20MB
except Exception:
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import documents

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="票据识别服务", version="0.1.0")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """未捕获异常时记录完整堆栈并返回 500 详情，便于排查。"""
    tb = traceback.format_exc()
    logger.error("unhandled exception: %s\n%s", exc, tb)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}", "traceback": tb.split("\n")},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """调试：记录每条请求的方法与路径。"""
    logger.info(">>> %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("<<< %s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.middleware("http")
async def options_200(request: Request, call_next):
    """统一对 OPTIONS 返回 200，避免 CORS 预检 405。"""
    if request.method == "OPTIONS":
        from starlette.responses import Response
        return Response(status_code=200)
    return await call_next(request)


app.include_router(documents.router, prefix="/api/doc", tags=["documents"])


@app.on_event("startup")
def startup():
    for r in app.routes:
        if hasattr(r, "methods") and hasattr(r, "path"):
            logger.info("route: %s %s", r.methods, r.path)


@app.get("/")
def root():
    return {"message": "票据识别服务", "docs": "/docs"}
