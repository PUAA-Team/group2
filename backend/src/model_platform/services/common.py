from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from ..database import aware, new_id
from ..errors import Problem
from ..models import AuditEvent


def serialize(obj, *, exclude=()):
    blocked = {"password_hash", "token_digest", "credential_digest", "code_digest", "storage_key"} | set(exclude)
    result = {}
    for column in obj.__table__.columns:
        if column.name in blocked:
            continue
        value = getattr(obj, column.name)
        result[column.name] = aware(value).isoformat() if isinstance(value, datetime) else value
    return result


def audit(db, user, action, target_id, workspace_id=None):
    db.add(AuditEvent(id=new_id("evt"), actor_id=user.id, action=action,
                      target_id=target_id, workspace_id=workspace_id))


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Problem(409, "CONFLICT", "名称、版本或关联对象存在冲突") from None


def page_data(db, query, page, page_size):
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    model = query.column_descriptions[0]["entity"]
    if hasattr(model, "created_at"):
        query = query.order_by(model.created_at, model.id)
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return [serialize(item) for item in items], {"page": page, "page_size": page_size, "total": total}


def search_query(query, q, *columns):
    term = q.strip().lower()
    if term:
        return query.where(or_(*(func.lower(column).contains(term, autoescape=True) for column in columns)))
    return query


def revision_update(db, obj, values, expected):
    if any(value is None for key, value in values.items() if key != "group_id"):
        raise Problem(422, "VALIDATION_ERROR", "字段不能设置为空")
    model = type(obj)
    result = db.execute(update(model).where(model.id == obj.id, model.revision == expected)
                        .values(**values, revision=expected + 1).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise Problem(412, "REVISION_MISMATCH", "对象已更新，请重新读取")
    db.expire(obj)
    return obj


def find_asset(db, model, workspace_id, asset_id):
    obj = db.scalar(select(model).where(model.id == asset_id, model.workspace_id == workspace_id))
    if obj is None:
        raise Problem(404, "NOT_FOUND", "资产不存在")
    return obj
