from typing import Literal

from fastapi import APIRouter, Request
from sqlalchemy import select

from ..administration_models import ModelConnection
from ..administration_schemas import ConnectionInput, PlatformConfig
from ..errors import response
from ..permissions import effective_policy, require_admin
from ..services.administration_queries import global_catalog, statistics
from ..services.common import page_data
from ..services.model_connections import connection_view, save_connection, test_connection
from ..services.platform_settings import config_view, platform_config, save_config
from .deps import Actor, Db, Expected, Page, PageSize, Search

router = APIRouter(prefix="/api/v1", tags=["平台管理"])


@router.get("/platform-info")
def public_branding(request: Request, db: Db):
    config = platform_config(db)
    return response(request, {"platform_name": config.platform_name, "invitations_enabled": config.invitations_enabled})


@router.get("/admin/settings")
def settings(request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "settings.manage")
    return response(request, config_view(db))


@router.patch("/admin/settings")
def update_settings(payload: PlatformConfig, request: Request, actor: Actor, db: Db, expected: Expected):
    require_admin(db, actor, "settings.manage")
    return response(request, save_config(db, actor, payload, expected))


@router.get("/admin/model-connections")
def connections(request: Request, actor: Actor, db: Db, page: Page = 1, page_size: PageSize = 20):
    require_admin(db, actor, "settings.manage")
    rows, pagination = page_data(db, select(ModelConnection), page, page_size)
    return response(request, [connection_view(db.get(ModelConnection, row["id"])) for row in rows], pagination=pagination)


@router.post("/admin/model-connections", status_code=201)
def new_connection(payload: ConnectionInput, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "settings.manage")
    return response(request, save_connection(db, request.app.state.settings, actor, payload))


@router.patch("/admin/model-connections/{connection_id}")
def edit_connection(connection_id: str, payload: ConnectionInput, request: Request, actor: Actor, db: Db, expected: Expected):
    require_admin(db, actor, "settings.manage")
    return response(request, save_connection(db, request.app.state.settings, actor, payload, connection_id, expected))


@router.post("/admin/model-connections/{connection_id}/test")
async def check_connection(connection_id: str, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "settings.manage")
    return response(request, await test_connection(db, request.app.state.settings, actor, connection_id))


@router.get("/admin/statistics")
def global_statistics(request: Request, actor: Actor, db: Db, space: Search = ""):
    require_admin(db, actor, "audit.read")
    return response(request, statistics(db, actor, space or None))


@router.get("/admin/asset-catalog/{kind}")
def management_catalog(kind: Literal["datasets", "models", "jobs", "audit"], request: Request, actor: Actor, db: Db,
                       page: Page = 1, page_size: PageSize = 20, q: Search = "", space: Search = "", status: Search = "",
                       job_kind: Literal["train", "evaluate", "service"] | None = None):
    actions, _ = effective_policy(db, actor)
    permission = {"datasets": "datasets.read", "models": "models.read", "audit": "audit.read", "jobs": "services.read" if job_kind == "service" or "training.read" not in actions else "training.read"}[kind]
    if kind == "jobs" and job_kind in {"train", "evaluate"}:
        permission = "training.read"
    require_admin(db, actor, permission)
    allowed_kinds = (["train", "evaluate"] if "training.read" in actions else []) + (["service"] if "services.read" in actions else [])
    rows, pagination = global_catalog(db, kind, q, space, status, job_kind, page, page_size, allowed_kinds)
    return response(request, rows, pagination=pagination)
