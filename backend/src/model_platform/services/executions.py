from datetime import timedelta
import hashlib
import json

from sqlalchemy import select, update

from ..compute_models import ComputeDevice
from ..database import new_id, utcnow
from ..errors import Problem
from ..job_models import Execution, ExecutionEvent, Job, ServiceCall
from ..models import DatasetVersion, ModelVersion, User
from .artifact_files import validate_artifact
from .common import audit, commit
from .file_storage import delete_object, resolve_key, write_atomic
from .jobs import source_job
from .call_lifecycle import finish_call


def owned_execution(db, node, execution_id, *, lock=False):
    if lock:
        db.execute(update(Execution).where(Execution.id == execution_id, Execution.node_id == node.id).values(event_seq=Execution.event_seq).execution_options(synchronize_session=False))
    execution = db.scalar(select(Execution).where(Execution.id == execution_id, Execution.node_id == node.id).execution_options(populate_existing=True))
    if not execution:
        raise Problem(404, "NOT_FOUND", "执行不存在")
    return execution, db.get(Job, execution.job_id)


def add_event(db, node, execution_id, payload):
    execution, job = owned_execution(db, node, execution_id, lock=True)
    existing = db.scalar(select(ExecutionEvent).where(ExecutionEvent.execution_id == execution.id, ExecutionEvent.seq == payload.seq))
    if existing:
        if existing.type != payload.type or existing.payload != payload.payload:
            raise Problem(409, "EVENT_CONFLICT", "相同序号的事件内容不同")
        return {"next_seq": execution.event_seq + 1}
    if execution.finished_at or payload.seq != execution.event_seq + 1:
        raise Problem(409, "EVENT_SEQUENCE", "事件序号不连续")
    if job.status not in {"preparing", "running", "ready", "stopping"}:
        raise Problem(409, "INVALID_STATE", "任务当前状态不允许上报事件")
    if payload.type == "metric":
        values = payload.payload
        if not values or any(not isinstance(value, (float, int)) or isinstance(value, bool) for value in values.values()):
            raise Problem(422, "INVALID_METRIC", "指标必须是数值")
    if payload.type == "ready" and job.kind != "service":
        raise Problem(409, "INVALID_STATE", "该任务不是在线服务")
    if payload.type == "started" and job.status == "preparing":
        job.status = "running"
        job.revision += 1
    elif payload.type == "ready" and job.status in {"preparing", "running"}:
        job.status = "ready"
        job.revision += 1
    db.add(ExecutionEvent(id=f"{execution.id}:{payload.seq}", execution_id=execution.id, seq=payload.seq, type=payload.type, payload=payload.payload))
    execution.event_seq = payload.seq
    execution.status = job.status
    execution.lease_until = utcnow() + timedelta(seconds=30)
    commit(db)
    return {"next_seq": execution.event_seq + 1}


def control(db, node, execution_id):
    execution, job = owned_execution(db, node, execution_id, lock=True)
    execution.lease_until = utcnow() + timedelta(seconds=30)
    pending = []
    if job.kind == "service" and job.status == "ready":
        pending = [{"id": call.id, "input": call.input} for call in db.scalars(select(ServiceCall).where(ServiceCall.job_id == job.id, ServiceCall.status == "pending").order_by(ServiceCall.created_at).limit(16))]
    commit(db)
    return {"stop": job.status == "stopping", "finished": execution.finished_at is not None, "calls": pending}


def input_path(db, settings, node, execution_id, model=False):
    execution, job = owned_execution(db, node, execution_id)
    if execution.finished_at:
        raise Problem(409, "EXECUTION_FINISHED", "执行已结束")
    if model:
        version = db.get(ModelVersion, job.model_version_id)
        if version and version.source_ref.startswith("upload://") and version.storage_key and version.sha256:
            key, sha = version.storage_key, version.sha256
        else:
            parent = source_job(db, job.workspace_id, version)
            if not parent:
                raise Problem(404, "NOT_FOUND", "该模型无需下载平台产物")
            key, sha = parent.artifact_key, parent.artifact_sha256
    else:
        data = db.get(DatasetVersion, job.dataset_version_id)
        if not data:
            raise Problem(404, "NOT_FOUND", "该执行没有数据输入")
        key, sha = data.storage_key, data.sha256
    path = resolve_key(settings, key)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise Problem(409, "FILE_NOT_READY", "输入文件缺失或校验失败")
    return path, sha


def store_artifact(db, settings, node, execution_id, content):
    execution, job = owned_execution(db, node, execution_id, lock=True)
    if job.kind != "train" or execution.finished_at:
        raise Problem(409, "INVALID_STATE", "当前执行不能上传产物")
    sha = validate_artifact(content, job.snapshot["trainer_id"])
    if job.artifact_sha256:
        if job.artifact_sha256 != sha:
            raise Problem(409, "ARTIFACT_CONFLICT", "该执行已上传不同的产物")
        return {"sha256": sha}
    key = f"{job.workspace_id}/artifacts/{execution.id}.zip"
    from .budgets import charge_objects
    actor = db.get(User, job.created_by)
    charge_objects(db, actor, [{'id': 'artifact:' + job.id, 'workspace_id': job.workspace_id,
        'kind': 'artifact', 'object_id': job.id, 'storage_key': key, 'size_bytes': len(content)}])
    try:
        path, _, _ = write_atomic(settings, key, content)
        job.artifact_key, job.artifact_sha256, job.artifact_bytes = key, sha, len(content)
        commit(db)
    except Exception:
        db.rollback()
        delete_object(settings, key)
        raise
    return {"sha256": sha}


def finish(db, node, execution_id, payload, settings=None):
    execution, job = owned_execution(db, node, execution_id, lock=True)
    fingerprint = hashlib.sha256(json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    if execution.finished_at:
        if execution.finish_digest != fingerprint:
            raise Problem(409, "FINISH_CONFLICT", "完成结果与已确认记录不同")
        return {"accepted": True, "status": job.status}
    if job.status not in {"preparing", "running", "ready", "stopping"}:
        raise Problem(409, "INVALID_STATE", "任务当前状态不允许结案")
    if "error_samples" in payload.result:
        from .evaluation_errors import validate_errors
        validate_errors(db, settings, job, payload.result)
    status = "stopped" if job.status == "stopping" else payload.status
    if status == "succeeded" and job.kind == "train" and not job.artifact_sha256:
        raise Problem(409, "ARTIFACT_REQUIRED", "成功训练需要先回传模型产物")
    if status == "succeeded" and job.kind == "service":
        status = "stopped"
    if status == "succeeded" and job.kind == "train":
        version = db.get(ModelVersion, job.model_version_id)
        output = ModelVersion(id=new_id("mvr"), model_id=version.model_id, version=f"run-{job.id[-12:]}",
                              source_ref=f"artifact://{job.id}", status="available", created_by=job.created_by)
        db.add(output); db.flush(); job.output_model_version_id = output.id
    job.status, job.result, job.error = status, payload.result, payload.error
    job.revision += 1
    execution.status, execution.finished_at, execution.finish_digest = status, utcnow(), fingerprint
    db.execute(update(ComputeDevice).where(ComputeDevice.id == execution.device_id, ComputeDevice.reserved_execution_id == execution.id).values(reserved_execution_id=None))
    if job.kind == "service":
        for call in db.scalars(select(ServiceCall).where(ServiceCall.job_id == job.id, ServiceCall.status == "pending")):
            finish_call(call, "failed", {"error": "服务已结束"})
    commit(db)
    return {"accepted": True, "status": job.status}
