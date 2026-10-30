import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from alembic.config import Config
from alembic.script import ScriptDirectory
from pathlib import Path

from .api import accounts, admin, administration, auth, console, datasets, models, resources, setup, worker, workspaces, jobs, executions, inference
from .config import Settings
from .database import make_engine, make_session_factory
from .errors import Problem, install_handlers, response
from .outputs import Envelope, ErrorEnvelope
from .web import attach_web
from .api import data_workflows


class RequestBoundary:
    """在 multipart 解析前限制请求总量，并统一来源和请求标识。"""

    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        headers = dict(scope["headers"])
        response_started = False

        async def tagged_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                message.setdefault("headers", []).extend([
                    (b"x-request-id", request_id.encode()), (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff")])
            await send(message)

        async def reject(status, code, message):
            output = JSONResponse(status_code=status, content={"error": {
                "code": code, "message": message, "details": []}, "request_id": request_id})
            await output(scope, receive, tagged_send)

        async def protected_call(receiver):
            try:
                await self.app(scope, receiver, tagged_send)
            except Exception as exc:
                logging.getLogger("model_platform").error(
                    "request_failed id=%s type=%s", request_id, type(exc).__name__)
                if response_started:
                    raise RuntimeError("响应发送中断，请按请求编号排查") from None
                await reject(500, "INTERNAL_ERROR", "服务处理失败")

        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            origin = headers.get(b"origin", b"").decode("latin1")
            if origin and origin not in self.settings.allowed_origins:
                return await reject(403, "FORBIDDEN", "请求来源未获允许")
            limit = self.settings.max_upload_bytes + 65536
            if scope["path"].startswith("/api/worker/v1/executions/") and scope["path"].endswith("/artifact"):
                limit = 64 * 1024 * 1024 + 65536
            chunks, size = [], 0
            while True:
                part = await receive()
                if part["type"] == "http.disconnect":
                    return
                size += len(part.get("body", b""))
                if size > limit:
                    return await reject(413, "FILE_TOO_LARGE", "请求超过大小限制")
                chunks.append(part.get("body", b""))
                if not part.get("more_body", False):
                    break
            body = b"".join(chunks)

            async def buffered_receive():
                nonlocal body
                if body is not None:
                    payload, body = body, None
                    return {"type": "http.request", "body": payload, "more_body": False}
                return await receive()

            return await protected_call(buffered_receive)
        return await protected_call(receive)


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    expected_schema = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))).get_current_head()
    app = FastAPI(title="模型训练平台控制平面", version="0.1.0", responses={
        "default": {"model": ErrorEnvelope, "description": "统一业务或服务错误"},
        422: {"model": ErrorEnvelope, "description": "输入校验失败"},
    })
    app.state.settings = settings
    app.state.engine = make_engine(settings.db_url)
    app.state.sessions = make_session_factory(app.state.engine)
    install_handlers(app)
    app.add_middleware(RequestBoundary, settings=settings)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                       allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
                       allow_headers=["Content-Type", "X-CSRF-Token", "If-Match"],
                       expose_headers=["X-Request-ID", "ETag"])
    for router in (setup.router, auth.router, admin.router, workspaces.router, models.router, datasets.router, resources.router, worker.router, jobs.router, executions.router, inference.router, console.router, administration.router, accounts.router):
        app.include_router(router)
    app.include_router(data_workflows.router)

    @app.get("/healthz", tags=["运行检查"], response_model=Envelope[dict[str, str]])
    def health(request: Request):
        return response(request, {"status": "alive"})

    @app.get("/readyz", tags=["运行检查"], response_model=Envelope[dict[str, str]])
    def ready(request: Request):
        if settings.db_url.startswith("sqlite:") and not app.state.engine.url.database == ":memory:":
            if not Path(app.state.engine.url.database).is_file():
                raise Problem(503, "NOT_READY", "请先执行数据库迁移")
        try:
            with app.state.engine.connect() as connection:
                version = connection.scalar(text("SELECT version_num FROM alembic_version"))
                if version != expected_schema:
                    raise Problem(503, "NOT_READY", "数据库版本尚未就绪")
        except SQLAlchemyError:
            raise Problem(503, "NOT_READY", "数据库尚未就绪") from None
        return response(request, {"status": "ready", "schema": version})

    attach_web(app)
    return app
