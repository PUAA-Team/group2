from collections import Counter

from sqlalchemy import select, update

from ..data_models import AnnotationBatch, AnnotationResult
from ..database import new_id, utcnow
from ..errors import Problem
from ..models import DatasetVersion, Membership, User, Workspace
from .common import audit, commit, serialize
from .data_samples import encode_rows, read_source, source
from .datasets import store_versions
from .asset_lifecycle import ensure_active


def find_batch(db, workspace_id, batch_id):
    batch = db.scalar(select(AnnotationBatch).where(AnnotationBatch.id == batch_id,
        AnnotationBatch.workspace_id == workspace_id))
    if batch is None:
        raise Problem(404, "NOT_FOUND", "标注批次不存在")
    return batch


def reviewer(db, actor, batch):
    space = db.get(Workspace, batch.workspace_id)
    return actor.is_admin or actor.id in {batch.created_by, space.owner_id}


def lock_batch(db, batch, *, publishing=False):
    # 所有结果写入和发布先通过版本号条件更新竞争同一父行，防止并发改写丢失。
    result = db.execute(
        update(AnnotationBatch)
        .where(AnnotationBatch.id == batch.id, AnnotationBatch.revision == batch.revision)
        .values(revision=AnnotationBatch.revision + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise Problem(409, "CONFLICT", "批次状态已更新，请刷新重试")
    db.refresh(batch)
    if batch.status != "open" and not (publishing and batch.output_version_id):
        raise Problem(409, "CONFLICT", "批次已发布，无法继续修改")


def batch_view(db, batch):
    data = serialize(batch)
    states = Counter(db.scalars(select(AnnotationResult.state).where(AnnotationResult.batch_id == batch.id)).all())
    data["counts"] = {"total": len(batch.sample_indices), **states}
    data["counts"]["pending"] = len(batch.sample_indices) - sum(states.values())
    data.pop("sample_indices")
    return data


def create_batch(db, settings, actor, workspace_id, payload):
    dataset, version = source(db, workspace_id, payload.version_id)
    ensure_active(dataset)
    if payload.assigned_to:
        member = db.get(Membership, (workspace_id, payload.assigned_to))
        user = db.get(User, payload.assigned_to)
        if not member or member.role == "viewer" or not user or not user.active:
            raise Problem(422, "VALIDATION_ERROR", "请分配给当前空间的有效编辑成员")
    if dataset.task_type != "llm_sft" and not payload.labels:
        raise Problem(422, "VALIDATION_ERROR", "分类标注需要标签集合")
    read_source(settings, dataset, version)
    batch = AnnotationBatch(id=new_id("ann"), workspace_id=workspace_id, version_id=version.id,
        name=payload.name, labels=payload.labels, assigned_to=payload.assigned_to,
        sample_indices=list(range(min(payload.limit, version.sample_count))), created_by=actor.id)
    db.add(batch)
    audit(db, actor, "annotations.create", batch.id, workspace_id)
    commit(db)
    return batch_view(db, batch)


def batch_detail(db, settings, actor, batch, page, page_size):
    dataset, version = source(db, batch.workspace_id, batch.version_id)
    rows, _ = read_source(settings, dataset, version)
    indices = batch.sample_indices[(page - 1) * page_size:page * page_size]
    results = {item.sample_index: serialize(item) for item in db.scalars(select(AnnotationResult).where(
        AnnotationResult.batch_id == batch.id, AnnotationResult.sample_index.in_(indices))).all()}
    return {**batch_view(db, batch), "dataset": {"id": dataset.id, "name": dataset.name, "task_type": dataset.task_type},
        "source_version": {"id": version.id, "number": version.number, "provenance": version.provenance},
        "can_review": reviewer(db, actor, batch),
        "can_edit": not batch.assigned_to or batch.assigned_to == actor.id or reviewer(db, actor, batch),
        "samples": [{"index": index, "source": rows[index], "result": results.get(index)} for index in indices],
        "pagination": {"page": page, "page_size": page_size, "total": len(batch.sample_indices)}}


def save_result(db, actor, batch, index, payload):
    lock_batch(db, batch)
    if batch.assigned_to and batch.assigned_to != actor.id and not reviewer(db, actor, batch):
        raise Problem(403, "FORBIDDEN", "此批次已分配给其他成员")
    if index not in batch.sample_indices:
        raise Problem(404, "NOT_FOUND", "样本不属于此标注批次")
    dataset, _ = source(db, batch.workspace_id, batch.version_id)
    ensure_active(dataset)
    if dataset.task_type != "llm_sft" and payload.value not in batch.labels:
        raise Problem(422, "VALIDATION_ERROR", "标注值不在标签集合中")
    if payload.edits and dataset.task_type != "llm_sft":
        raise Problem(422, "VALIDATION_ERROR", "只有指令标注可以修改输入与指令")
    result = db.scalar(select(AnnotationResult).where(AnnotationResult.batch_id == batch.id,
        AnnotationResult.sample_index == index))
    if (result.revision if result else 0) != payload.revision:
        raise Problem(412, "REVISION_MISMATCH", "标注已更新，请重新读取")
    if result is None:
        result = AnnotationResult(id=new_id("anr"), batch_id=batch.id, sample_index=index,
            value=payload.value, state="draft", edited_by=actor.id)
        db.add(result)
    else:
        result.revision += 1
    result.value, result.state = payload.value, "submitted" if payload.submit else "draft"
    result.edited_by, result.reviewed_by = actor.id, None
    result.edits = dict(payload.edits)
    result.origin = origin_with_edits(result.origin, payload.edits, actor.id)
    audit(db, actor, "annotations.submit" if payload.submit else "annotations.save", batch.id, batch.workspace_id)
    commit(db)
    return serialize(result)


def origin_with_edits(origin, edits, actor_id):
    """记录人工修订过的字段及来源，保留此前的智能采纳来源。"""
    data = {key: value for key, value in (origin or {}).items() if key != "edits"}
    if edits:
        data["edits"] = {"fields": sorted(edits), "actor_id": actor_id, "at": utcnow().isoformat()}
    return data


def apply_candidates(db, actor, batch, candidates, revisions, origin):
    """把智能候选写入标注草稿；沿用人工提交、复核和发布流程。"""
    lock_batch(db, batch)
    if batch.assigned_to and batch.assigned_to != actor.id and not reviewer(db, actor, batch):
        raise Problem(403, "FORBIDDEN", "此批次已分配给其他成员")
    for candidate in candidates:
        if candidate["index"] not in batch.sample_indices:
            raise Problem(404, "NOT_FOUND", "样本不属于此标注批次")
    dataset, _ = source(db, batch.workspace_id, batch.version_id)
    ensure_active(dataset)
    if dataset.task_type != "llm_sft" and any(candidate["value"] not in batch.labels for candidate in candidates):
        raise Problem(422, "VALIDATION_ERROR", "标注值不在标签集合中")
    for candidate in candidates:
        index = candidate["index"]
        result = db.scalar(select(AnnotationResult).where(AnnotationResult.batch_id == batch.id,
            AnnotationResult.sample_index == index))
        if result is not None and result.state == "approved":
            raise Problem(409, "ALREADY_REVIEWED", "已审核样本不能被智能候选覆盖")
        # 采纳时固定样本revision，预览之后被人改过就要求重新核对。
        if (result.revision if result else 0) != revisions.get(str(index), 0):
            raise Problem(409, "STALE_SAMPLE", "样本已更新，请重新生成预览")
        if result is None:
            result = AnnotationResult(id=new_id("anr"), batch_id=batch.id, sample_index=index,
                value=candidate["value"], state="draft", edited_by=actor.id)
            db.add(result)
        else:
            result.revision += 1
            result.value = candidate["value"]
        result.state, result.edited_by, result.reviewed_by = "draft", actor.id, None
        result.origin = {**origin, **({"edits": (result.origin or {})["edits"]}
            if (result.origin or {}).get("edits") else {}),
            "reason": candidate.get("reason", ""), "applied_at": utcnow().isoformat()}
    audit(db, actor, "assistants.annotation_apply", batch.id, batch.workspace_id)
    # 由调用方将候选、采纳记录和请求状态一次提交。
    db.flush()
    return batch_view(db, batch)


def review_results(db, actor, batch, payload):
    if not reviewer(db, actor, batch):
        raise Problem(403, "FORBIDDEN", "此操作需要批次创建人或空间所有者复核")
    previous_revision = batch.revision
    lock_batch(db, batch)
    if previous_revision != payload.revision or batch.revision != payload.revision + 1:
        raise Problem(412, "REVISION_MISMATCH", "批次已更新，请重新读取")
    indices = set(payload.indices)
    results = db.scalars(select(AnnotationResult).where(AnnotationResult.batch_id == batch.id,
        AnnotationResult.sample_index.in_(indices))).all()
    if len(results) != len(indices) or any(result.state != "submitted" for result in results):
        raise Problem(409, "CONFLICT", "只能审核待审核的标注")
    for result in results:
        result.state, result.reviewed_by = payload.decision, actor.id
        result.revision += 1
    audit(db, actor, "annotations.review", batch.id, batch.workspace_id)
    commit(db)
    return batch_view(db, batch)


def publish_batch(db, settings, actor, batch):
    if not reviewer(db, actor, batch):
        raise Problem(403, "FORBIDDEN", "此操作需要批次创建人或空间所有者复核")
    if batch.output_version_id:
        return serialize(db.get(DatasetVersion, batch.output_version_id))
    lock_batch(db, batch, publishing=True)
    if batch.output_version_id:
        return serialize(db.get(DatasetVersion, batch.output_version_id))
    results = db.scalars(select(AnnotationResult).where(AnnotationResult.batch_id == batch.id)).all()
    if len(results) != len(batch.sample_indices) or any(result.state != "approved" for result in results):
        raise Problem(409, "CONFLICT", "目标样本全部审核通过后才能发布")
    dataset, version = source(db, batch.workspace_id, batch.version_id)
    rows, content = read_source(settings, dataset, version)
    field = "output" if dataset.task_type == "llm_sft" else "label"
    for result in results:
        rows[result.sample_index][field] = result.value
        if dataset.task_type == "llm_sft":
            # 指令标注的输入与指令修订随输出一起发布到新版本。
            for key, value in (result.edits or {}).items():
                rows[result.sample_index][key] = value
    filename, output = encode_rows(dataset.task_type, rows, content)
    provenance = {**version.provenance, "operation": "annotation", "batch_id": batch.id, "reviewed_samples": len(results)}

    def finalized(versions):
        batch.status, batch.output_version_id = "published", versions[0].id
        audit(db, actor, "annotations.publish", batch.id, batch.workspace_id)

    return serialize(store_versions(db, settings, actor, dataset, [(filename, output, provenance)],
        parent=version, finalize=finalized)[0])
