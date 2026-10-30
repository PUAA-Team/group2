from types import SimpleNamespace

from sqlalchemy import select, update

from ..data_models import DataOperation
from ..database import new_id
from ..errors import Problem
from .common import audit, commit, serialize
from .data_samples import read_source, source
from .datasets import store_versions


def find_operation(db, workspace_id, operation_id):
    operation = db.scalar(select(DataOperation).where(DataOperation.id == operation_id,
        DataOperation.workspace_id == workspace_id))
    if operation is None:
        raise Problem(404, "NOT_FOUND", "数据操作不存在")
    return operation


def operation_view(operation):
    data = serialize(operation, exclude={"candidates"})
    data["candidates"] = [{key: value for key, value in candidate.items() if key != "storage_key"}
                          for candidate in operation.candidates]
    return data


def create_operation(db, actor, workspace_id, payload):
    dataset, version = source(db, workspace_id, payload.version_id)
    if payload.kind == "augment":
        allowed = {"image_classification": {"flip", "brightness", "noise"}, "text_classification": {"punctuation"}}
        if not payload.options.methods or set(payload.options.methods) - allowed.get(dataset.task_type, set()):
            raise Problem(422, "UNSUPPORTED_OPERATION", "请选择当前数据类型支持的增强方法")
        if version.provenance.get("partition") in {"validation", "test"}:
            raise Problem(409, "EVALUATION_PARTITION", "验证集和测试集不能进行训练增强")
    operation = DataOperation(id=new_id("dop"), workspace_id=workspace_id, version_id=version.id,
        name=payload.name, kind=payload.kind, options=payload.options.model_dump(), created_by=actor.id)
    db.add(operation)
    audit(db, actor, "data_operations.create", operation.id, workspace_id)
    commit(db)
    return operation_view(operation)


def cancel_operation(db, actor, operation):
    result = db.execute(update(DataOperation).where(DataOperation.id == operation.id,
        DataOperation.status.in_(["queued", "running", "review"]))
        .values(status="cancelled", revision=DataOperation.revision + 1).execution_options(synchronize_session=False))
    if result.rowcount != 1 and operation.status != "cancelled":
        raise Problem(409, "CONFLICT", "当前操作不能取消")
    audit(db, actor, "data_operations.cancel", operation.id, operation.workspace_id)
    commit(db)
    db.refresh(operation)
    return operation_view(operation)


def candidate_source(db, settings, operation, candidate_index):
    if operation.status not in {"review", "published"} or candidate_index < 0 or candidate_index >= len(operation.candidates):
        raise Problem(404, "NOT_FOUND", "候选结果不存在")
    dataset, _ = source(db, operation.workspace_id, operation.version_id)
    candidate = operation.candidates[candidate_index]
    return dataset, SimpleNamespace(**candidate)


def publish_operation(db, settings, actor, operation):
    db.execute(update(DataOperation).where(DataOperation.id == operation.id)
        .values(revision=DataOperation.revision + 1).execution_options(synchronize_session=False))
    db.refresh(operation)
    if operation.status == "published":
        return operation_view(operation)
    if operation.status != "review" or not operation.candidates:
        raise Problem(409, "CONFLICT", "处理结果就绪后才能发布")
    dataset, version = source(db, operation.workspace_id, operation.version_id)
    files = []
    for candidate in operation.candidates:
        _, content = read_source(settings, dataset, SimpleNamespace(**candidate))
        provenance = {**version.provenance, "operation": operation.kind, "operation_id": operation.id,
                      "seed": operation.options["seed"]}
        if operation.kind == "split":
            provenance["partition"] = candidate["partition"]
        files.append((candidate["filename"], content, provenance))

    def finalized(versions):
        operation.status, operation.output_version_ids = "published", [item.id for item in versions]
        audit(db, actor, "data_operations.publish", operation.id, operation.workspace_id)

    store_versions(db, settings, actor, dataset, files, parent=version, finalize=finalized)
    return operation_view(operation)
