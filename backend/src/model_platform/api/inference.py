from typing import Annotated

from fastapi import APIRouter, Header, Request
from sqlalchemy import select

from ..database import utcnow
from ..errors import Problem, response
from ..job_models import Job, ServiceCall, ServiceKey
from ..job_schemas import CallInput, KeyInput
from ..permissions import workspace_access
from ..services.common import audit, commit, find_asset, serialize
from ..services.jobs import get_job
from ..services.service_calls import create_call, create_key, key_actor
from .deps import Actor, Db

router = APIRouter(tags=["内部推理与 API KEY"])
base = "/api/v1/workspaces/{workspace_id}"


@router.post(base + "/jobs/{job_id}/calls", status_code=202)
def browser_invoke(workspace_id: str, job_id: str, payload: CallInput, request: Request, actor: Actor, db: Db):
    return response(request, create_call(db, actor, get_job(db, actor, workspace_id, job_id), payload))


@router.get(base + "/calls/{call_id}")
def browser_call(workspace_id: str, call_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "services.invoke")
    call = db.get(ServiceCall, call_id)
    job = db.get(Job, call.job_id) if call else None
    if not job or job.workspace_id != workspace_id or call.created_by != actor.id:
        raise Problem(404, "NOT_FOUND", "调用不存在")
    return response(request, serialize(call))


@router.get(base + "/service-keys")
def keys(workspace_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "services.read")
    rows = db.scalars(select(ServiceKey).where(ServiceKey.workspace_id == workspace_id, ServiceKey.created_by == actor.id).order_by(ServiceKey.created_at.desc()).limit(100))
    return response(request, [serialize(row) for row in rows])


@router.post(base + "/service-keys", status_code=201)
def new_key(workspace_id: str, payload: KeyInput, request: Request, actor: Actor, db: Db):
    return response(request, create_key(db, actor, workspace_id, payload))


@router.post(base + "/service-keys/{key_id}/revoke")
def revoke_key(workspace_id: str, key_id: str, request: Request, actor: Actor, db: Db):
    workspace_access(db, actor, workspace_id, "services.write")
    key = find_asset(db, ServiceKey, workspace_id, key_id)
    if key.created_by != actor.id:
        raise Problem(404, "NOT_FOUND", "密钥不存在")
    key.revoked_at = utcnow(); audit(db, actor, "service_keys.revoke", key.id, workspace_id); commit(db)
    return response(request, serialize(key))


def api_key(authorization):
    return authorization[7:] if authorization and authorization.startswith("Bearer ") else ""


@router.post("/api/inference/v1/services/{job_id}/predict", status_code=202)
def external_invoke(job_id: str, payload: CallInput, request: Request, db: Db, authorization: Annotated[str | None, Header()] = None):
    actor, key = key_actor(db, api_key(authorization), job_id)
    return response(request, create_call(db, actor, db.get(Job, job_id), payload))


@router.get("/api/inference/v1/services/{job_id}/calls/{call_id}")
def external_result(job_id: str, call_id: str, request: Request, db: Db, authorization: Annotated[str | None, Header()] = None):
    actor, key = key_actor(db, api_key(authorization), job_id)
    call = db.get(ServiceCall, call_id)
    if not call or call.job_id != job_id or call.created_by != actor.id:
        raise Problem(404, "NOT_FOUND", "调用不存在")
    return response(request, serialize(call))
