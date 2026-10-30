from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse

from ..errors import Problem, response
from ..job_schemas import CallResult, ClaimInput, EventInput, FinishInput
from ..services import executions, service_calls
from ..services.artifact_files import MAX_ARTIFACT
from ..services.scheduler import claim
from .deps import Db
from .worker_auth import Worker

router = APIRouter(prefix="/api/worker/v1", tags=["Worker 执行"])


@router.post("/claim")
def get_assignment(payload: ClaimInput, request: Request, node: Worker, db: Db):
    return response(request, claim(db, node, request.app.state.settings, payload.known_executions))


@router.post("/executions/{execution_id}/events")
def events(execution_id: str, payload: EventInput, request: Request, node: Worker, db: Db):
    return response(request, executions.add_event(db, node, execution_id, payload))


@router.get("/executions/{execution_id}/control")
def control(execution_id: str, request: Request, node: Worker, db: Db):
    return response(request, executions.control(db, node, execution_id))


def download(request, db, node, execution_id, model):
    path, sha = executions.input_path(db, request.app.state.settings, node, execution_id, model)
    return FileResponse(path, media_type="application/octet-stream", headers={"X-Content-SHA256": sha})


@router.get("/executions/{execution_id}/input")
def input_file(execution_id: str, request: Request, node: Worker, db: Db):
    return download(request, db, node, execution_id, False)


@router.get("/executions/{execution_id}/model")
def model_file(execution_id: str, request: Request, node: Worker, db: Db):
    return download(request, db, node, execution_id, True)


@router.post("/executions/{execution_id}/artifact")
async def artifact(execution_id: str, request: Request, node: Worker, db: Db, file: Annotated[UploadFile, File()]):
    content = await file.read(MAX_ARTIFACT + 1)
    if len(content) > MAX_ARTIFACT:
        raise Problem(413, "FILE_TOO_LARGE", "模型产物超过 64 MiB")
    return response(request, executions.store_artifact(db, request.app.state.settings, node, execution_id, content))


@router.post("/executions/{execution_id}/finish")
def finish(execution_id: str, payload: FinishInput, request: Request, node: Worker, db: Db):
    return response(request, executions.finish(db, node, execution_id, payload))


@router.post("/executions/{execution_id}/calls/{call_id}")
def call_result(execution_id: str, call_id: str, payload: CallResult, request: Request, node: Worker, db: Db):
    return response(request, service_calls.complete_call(db, node, execution_id, call_id, payload))
