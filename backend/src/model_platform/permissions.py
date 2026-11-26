from sqlalchemy import select

from .errors import Problem
from .models import Membership, UserGroup, Workspace

ACTIONS = frozenset({
    "users.manage", "groups.manage", "workspaces.create", "members.manage",
    "models.read", "models.write", "datasets.read", "datasets.write", "audit.read",
    "resources.read", "resources.manage",
    "training.read", "training.write", "services.read", "services.write", "services.invoke",
    "settings.manage", "assistants.use",
})
QUOTAS = ("gpu_count", "concurrent_jobs", "storage_gib")
WRITE_SUFFIXES = (".write", ".manage", ".invoke", ".use")
ANNOTATOR_ACTIONS = frozenset({"datasets.read", "datasets.write", "assistants.use"})


def is_workspace_admin(user, workspace, member=None):
    if user.is_admin:
        return True
    if workspace is None:
        return False
    return workspace.owner_id == user.id or (member is not None and member.role == "admin")


def effective_policy(db, user):
    group = db.get(UserGroup, user.group_id) if user.group_id else None
    allowed = set(user.allow_actions) | (set(group.allow_actions) if group else set())
    denied = set(user.deny_actions) | (set(group.deny_actions) if group else set())
    if user.is_admin:
        allowed |= ACTIONS
    limits = group.quota if group else {}
    quota = {key: min(limits.get(key, 0), user.quota.get(key, limits.get(key, 0))) for key in QUOTAS}
    return allowed - denied, quota


def workspace_effective_quota(db, user, workspace_id):
    _, base_quota = effective_policy(db, user)
    if user.is_admin:
        return base_quota
    member = db.get(Membership, (workspace_id, user.id))
    sub = (member.quota if member else None) or {}
    return {
        key: min(base_quota[key], int(sub[key])) if sub.get(key) is not None else base_quota[key]
        for key in QUOTAS
    }


def require_action(db, user, action):
    allowed, _ = effective_policy(db, user)
    if action not in allowed:
        raise Problem(403, "FORBIDDEN", "无权执行此操作")


def require_admin(db, user, action):
    if not user.is_admin:
        raise Problem(403, "FORBIDDEN", "此操作需要管理员权限")
    require_action(db, user, action)


def require_workspace_admin(db, user, workspace_id):
    workspace = db.get(Workspace, workspace_id)
    member = db.get(Membership, (workspace_id, user.id))
    if workspace is None or (not user.is_admin and member is None):
        raise Problem(404, "NOT_FOUND", "工作空间不存在")
    if not is_workspace_admin(user, workspace, member):
        raise Problem(403, "FORBIDDEN", "此操作需要工作空间管理员权限")
    group = db.get(UserGroup, user.group_id) if user.group_id else None
    denied = set(user.deny_actions) | (set(group.deny_actions) if group else set())
    if "members.manage" in denied:
        raise Problem(403, "FORBIDDEN", "无权执行此操作")
    return workspace, member


def workspace_access(db, user, workspace_id, action):
    workspace = db.get(Workspace, workspace_id)
    member = db.get(Membership, (workspace_id, user.id))
    if workspace is None or (not user.is_admin and member is None):
        raise Problem(404, "NOT_FOUND", "工作空间不存在")
    if action == "members.manage":
        if not is_workspace_admin(user, workspace, member):
            raise Problem(403, "FORBIDDEN", "此操作需要工作空间管理员权限")
        group = db.get(UserGroup, user.group_id) if user.group_id else None
        denied = set(user.deny_actions) | (set(group.deny_actions) if group else set())
        if "members.manage" in denied:
            raise Problem(403, "FORBIDDEN", "无权执行此操作")
        return workspace
    require_action(db, user, action)
    if not user.is_admin and member.role == "viewer" and action.endswith(WRITE_SUFFIXES):
        raise Problem(403, "FORBIDDEN", "当前成员角色只允许读取")
    if not user.is_admin and member.role == "annotator" and action not in ANNOTATOR_ACTIONS:
        raise Problem(403, "FORBIDDEN", "标注员角色仅允许访问数据标注与预览")
    return workspace


def visible_workspaces(db, user):
    query = select(Workspace)
    if not user.is_admin:
        query = query.join(Membership).where(Membership.user_id == user.id)
    return query
