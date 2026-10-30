from fastapi import APIRouter, Request, Query
import hashlib
from fastapi.responses import FileResponse

from ..compute_schemas import HeartbeatInput, InventoryReport, RegisterInput
from ..compute_outputs import HeartbeatReceipt, WorkerReceipt
from ..errors import Problem, response
from ..outputs import Envelope
from ..services.common import commit
from ..services.compute import heartbeat, inventory_update, register_node
from ..services.worker_bundle import build_bundle
from .deps import Db
from .worker_auth import Worker

router = APIRouter(prefix="/api/worker/v1", tags=["Worker 协议"])


@router.get("/bundle", include_in_schema=False)
def bundle(request: Request, sha256: str | None = Query(default=None, pattern=r"^[a-f0-9]{64}$")):
    settings = request.app.state.settings
    if sha256:
        path = settings.runtime_dir / "bundles" / f"worker-{sha256}.pyz"
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise Problem(404, "BUNDLE_NOT_FOUND", "指定 Worker 版本暂不可用，请重新生成命令")
        sha = sha256
    else:
        path, sha = build_bundle(settings)
    return FileResponse(path, filename="model-platform-worker.pyz", media_type="application/zip", headers={"X-Content-SHA256": sha})


@router.post("/register", response_model=Envelope[WorkerReceipt])
def register(payload: RegisterInput, request: Request, db: Db):
    return response(request, register_node(db, request.app.state.settings, payload))


@router.post("/heartbeat", response_model=Envelope[HeartbeatReceipt])
def beat(payload: HeartbeatInput, request: Request, node: Worker, db: Db):
    return response(request, heartbeat(db, node, payload, request.app.state.settings))


@router.post("/inventory")
def inventory(payload: InventoryReport, request: Request, node: Worker, db: Db):
    if payload.request_id != "startup" and node.probe_request_id != payload.request_id:
        raise Problem(409, "STALE_PROBE", "探测请求已更新")
    inventory_update(db, node, payload.inventory)
    if payload.request_id != "startup":
        node.probe_request_id = None
    commit(db)
    return response(request, {"accepted": True})
