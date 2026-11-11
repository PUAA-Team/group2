from sqlalchemy import select, update

from ..database import new_id
from ..errors import Problem
from ..models import ModelAsset, ModelVersion
from ..template_models import TrainingParameterTemplate
from .assets import check_trainer
from .asset_lifecycle import ensure_active
from .common import audit, commit, find_asset, revision_update, serialize

COMMON = ('epochs', 'batch_size', 'learning_rate', 'validation_ratio', 'seed')


def config_values(config, task_type):
    keys = COMMON + (('max_length', 'lora_rank') if task_type == 'llm_sft' else ())
    values = config.model_dump(mode='json')
    return {key: values[key] for key in keys}


def create_template(db, actor, workspace_id, payload):
    check_trainer(payload.task_type, payload.trainer_id)
    item = TrainingParameterTemplate(id=new_id('tpt'), workspace_id=workspace_id, name=payload.name,
        task_type=payload.task_type, trainer_id=payload.trainer_id,
        config=config_values(payload.config, payload.task_type), created_by=actor.id)
    db.add(item)
    audit(db, actor, 'parameter_templates.create', item.id, workspace_id)
    commit(db)
    return serialize(item)


def change_template(db, actor, item, payload, expected):
    values = payload.model_dump()
    if 'config' in values:
        values['config'] = config_values(payload.config, item.task_type)
    revision_update(db, item, values, expected)
    audit(db, actor, 'parameter_templates.archive' if 'archived' in values else 'parameter_templates.update', item.id, item.workspace_id)
    commit(db)
    return serialize(item)


def resolve_template(db, actor, item, model_version_id, expected):
    # 与编辑竞争时锁定并刷新，返回的配置对应实际检查的revision。
    db.execute(update(TrainingParameterTemplate).where(TrainingParameterTemplate.id == item.id)
        .values(revision=TrainingParameterTemplate.revision).execution_options(synchronize_session=False))
    db.refresh(item)
    if item.revision != expected:
        raise Problem(412, 'REVISION_MISMATCH', '模板已更新，请重新选择')
    if item.archived:
        raise Problem(409, 'TEMPLATE_ARCHIVED', '参数模板已归档')
    version = db.get(ModelVersion, model_version_id)
    model = db.get(ModelAsset, version.model_id) if version else None
    if not model or model.workspace_id != item.workspace_id:
        raise Problem(422, 'INVALID_MODEL', '请选择本空间模型版本')
    ensure_active(model)
    if model.task_type != item.task_type or model.trainer_id != item.trainer_id:
        raise Problem(422, 'INCOMPATIBLE_TEMPLATE', '模板与当前模型的任务或训练器不兼容')
    result = {'template_id': item.id, 'revision': item.revision, 'config': dict(item.config)}
    audit(db, actor, 'parameter_templates.apply', item.id, item.workspace_id)
    commit(db)
    return result
