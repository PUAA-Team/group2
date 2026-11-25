from sqlalchemy import delete, func, select, update

from ..administration_models import Invitation, WorkspaceInvite, WorkspaceJoinRequest
from ..assistant_models import AssistantRequest, WorkspaceAIPolicy
from ..compute_models import ComputeNode, Enrollment
from ..data_models import AnnotationBatch, DataOperation
from ..errors import Problem
from ..governance_models import StoredObject
from ..job_models import Job, Project, ServiceKey
from ..models import AuditEvent, Dataset, DatasetVersion, Membership, ModelAsset, ModelVersion, Workspace
from ..permissions import workspace_access
from ..template_models import TrainingParameterTemplate
from .common import audit, commit, find_asset
from .file_storage import delete_object


def delete_project(db, actor, workspace_id, project_id):
    workspace_access(db, actor, workspace_id, "training.write")
    project = find_asset(db, Project, workspace_id, project_id)
    if not project.archived:
        raise Problem(409, "ARCHIVE_REQUIRED", "请先归档项目后再删除")
    job_count = db.scalar(select(func.count()).select_from(Job).where(Job.project_id == project.id))
    if job_count:
        raise Problem(409, "PROJECT_IN_USE", "该项目仍有关联任务记录，无法删除")
    db.delete(project)
    audit(db, actor, "projects.delete", project_id, workspace_id)
    commit(db)
    return {"deleted": True, "id": project_id}


def delete_model(db, settings, actor, workspace_id, model_id):
    workspace_access(db, actor, workspace_id, "models.write")
    model = find_asset(db, ModelAsset, workspace_id, model_id)
    if not model.archived:
        raise Problem(409, "ARCHIVE_REQUIRED", "请先归档模型后再删除")
    versions = list(db.scalars(select(ModelVersion).where(ModelVersion.model_id == model.id)))
    version_ids = [item.id for item in versions]
    if version_ids:
        used = db.scalar(select(func.count()).select_from(Job).where(
            (Job.model_version_id.in_(version_ids)) | (Job.output_model_version_id.in_(version_ids))
        ))
        if used:
            raise Problem(409, "ASSET_IN_USE", "该模型版本已被任务记录引用，无法删除")
        db.execute(delete(StoredObject).where(StoredObject.workspace_id == workspace_id, StoredObject.object_id.in_(version_ids)))
        db.execute(delete(ModelVersion).where(ModelVersion.model_id == model.id))
    db.delete(model)
    audit(db, actor, "models.delete", model_id, workspace_id)
    commit(db)
    for item in versions:
        delete_object(settings, item.storage_key)
    return {"deleted": True, "id": model_id}


def delete_dataset(db, settings, actor, workspace_id, dataset_id):
    workspace_access(db, actor, workspace_id, "datasets.write")
    dataset = find_asset(db, Dataset, workspace_id, dataset_id)
    if not dataset.archived:
        raise Problem(409, "ARCHIVE_REQUIRED", "请先归档数据集后再删除")
    versions = list(db.scalars(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)))
    version_ids = [item.id for item in versions]
    if version_ids:
        used_jobs = db.scalar(select(func.count()).select_from(Job).where(Job.dataset_version_id.in_(version_ids)))
        used_ann = db.scalar(select(func.count()).select_from(AnnotationBatch).where(
            (AnnotationBatch.version_id.in_(version_ids)) | (AnnotationBatch.output_version_id.in_(version_ids))
        ))
        used_ops = db.scalar(select(func.count()).select_from(DataOperation).where(
            DataOperation.version_id.in_(version_ids)
        ))
        if used_jobs or used_ann or used_ops:
            raise Problem(409, "ASSET_IN_USE", "该数据集版本已被任务或数据处理记录引用，无法删除")
        db.execute(delete(StoredObject).where(StoredObject.workspace_id == workspace_id, StoredObject.object_id.in_(version_ids)))
        db.execute(delete(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id))
    db.delete(dataset)
    audit(db, actor, "datasets.delete", dataset_id, workspace_id)
    commit(db)
    for item in versions:
        delete_object(settings, item.storage_key)
    return {"deleted": True, "id": dataset_id}


def delete_workspace(db, actor, workspace_id, confirm_name, expected):
    workspace = workspace_access(db, actor, workspace_id, "members.manage")
    if workspace.revision != expected:
        raise Problem(412, "REVISION_MISMATCH", "工作空间已更新，请重新读取")
    if workspace.name != confirm_name.strip():
        raise Problem(422, "CONFIRMATION_MISMATCH", "确认的工作空间名称不匹配")

    checks = [
        ("计算节点", ComputeNode, ComputeNode.workspace_id == workspace_id),
        ("训练与服务任务", Job, Job.workspace_id == workspace_id),
        ("训练项目", Project, Project.workspace_id == workspace_id),
        ("模型资产", ModelAsset, ModelAsset.workspace_id == workspace_id),
        ("数据集", Dataset, Dataset.workspace_id == workspace_id),
        ("服务密钥", ServiceKey, ServiceKey.workspace_id == workspace_id),
        ("标注批次", AnnotationBatch, AnnotationBatch.workspace_id == workspace_id),
        ("数据处理任务", DataOperation, DataOperation.workspace_id == workspace_id),
        ("智能辅助请求", AssistantRequest, AssistantRequest.workspace_id == workspace_id),
    ]
    blockers = []
    for label, model, cond in checks:
        count = db.scalar(select(func.count()).select_from(model).where(cond))
        if count:
            blockers.append(f"{label}({count})")
    if blockers:
        raise Problem(409, "WORKSPACE_NOT_EMPTY", "工作空间仍有未清空内容：" + "、".join(blockers))

    # 清理空间附属记录并保留审计事件（脱敏置空 workspace_id）
    db.execute(update(AuditEvent).where(AuditEvent.workspace_id == workspace_id).values(workspace_id=None))
    db.execute(delete(StoredObject).where(StoredObject.workspace_id == workspace_id))
    db.execute(delete(Enrollment).where(Enrollment.workspace_id == workspace_id))
    db.execute(delete(TrainingParameterTemplate).where(TrainingParameterTemplate.workspace_id == workspace_id))
    db.execute(delete(WorkspaceJoinRequest).where(WorkspaceJoinRequest.workspace_id == workspace_id))
    db.execute(delete(WorkspaceInvite).where(WorkspaceInvite.workspace_id == workspace_id))
    db.execute(delete(Invitation).where(Invitation.workspace_id == workspace_id))
    db.execute(delete(WorkspaceAIPolicy).where(WorkspaceAIPolicy.id == workspace_id))
    db.execute(delete(Membership).where(Membership.workspace_id == workspace_id))
    db.delete(workspace)
    audit(db, actor, "workspaces.delete", workspace_id)
    commit(db)
    return {"deleted": True, "id": workspace_id}
