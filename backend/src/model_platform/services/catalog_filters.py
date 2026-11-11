from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select

from ..models import AuditEvent, User

BUSINESS_ZONE = timezone(timedelta(hours=8))


def creation_actor(model, kind):
    if kind in {'datasets', 'models'}:
        return select(AuditEvent.actor_id).where(AuditEvent.target_id == model.id,
            AuditEvent.action == kind + '.create').order_by(AuditEvent.created_at, AuditEvent.id).limit(1).scalar_subquery()
    return model.actor_id if kind == 'audit' else model.created_by


def filter_catalog(query, model, kind, filters=None):
    filters = filters or {}
    if filters.get('creator'):
        names = select(User.id).where(func.lower(User.display_name).contains(filters['creator'].lower(), autoescape=True))
        query = query.where(creation_actor(model, kind).in_(names))
    if filters.get('created_from'):
        start = datetime.combine(filters['created_from'], time.min, BUSINESS_ZONE).astimezone(timezone.utc)
        query = query.where(model.created_at >= start)
    if filters.get('created_to'):
        end = datetime.combine(filters['created_to'], time.max, BUSINESS_ZONE).astimezone(timezone.utc)
        query = query.where(model.created_at <= end)
    if kind == 'audit' and filters.get('action'):
        query = query.where(AuditEvent.action == filters['action'])
    return query
