from fastapi import APIRouter, Request, Response
from typing import Literal
from sqlalchemy import delete, func, select, update

from ..database import new_id
from ..errors import Problem, response
from ..models import SessionToken, User, UserGroup
from ..outputs import Envelope, GroupOut, PageEnvelope, UserOut
from ..permissions import require_admin
from ..schemas import GroupCreate, GroupPatch, UserCreate, UserPatch
from ..security import hash_password
from ..services.common import audit, commit, page_data, revision_update, search_query, serialize
from .deps import Actor, Db, Expected, Page, PageSize, Search

router = APIRouter(prefix="/api/v1/admin", tags=["用户与用户组"])


def check_group(db, group_id):
    if group_id and not db.get(UserGroup, group_id):
        raise Problem(422, "VALIDATION_ERROR", "用户组不存在")


@router.get("/users", response_model=PageEnvelope[UserOut])
def list_users(request: Request, actor: Actor, db: Db, page: Page = 1, page_size: PageSize = 20, q: Search = "", group_id: str | None = None,
               user_status: Literal["active", "disabled"] | None = None):
    require_admin(db, actor, "users.manage")
    query = select(User)
    if group_id:
        query = query.where(User.group_id == group_id)
    if user_status:
        query = query.where(User.active.is_(user_status == "active"))
    items, pagination = page_data(db, search_query(query, q, User.account, User.display_name), page, page_size)
    return response(request, items, pagination=pagination)


@router.post("/users", status_code=201, response_model=Envelope[UserOut])
def create_user(payload: UserCreate, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "users.manage")
    check_group(db, payload.group_id)
    values = payload.model_dump(exclude={"password"})
    user = User(id=new_id("usr"), password_hash=hash_password(payload.password), **values)
    db.add(user)
    audit(db, actor, "users.create", user.id)
    commit(db)
    return response(request, serialize(user))


@router.patch("/users/{user_id}", response_model=Envelope[UserOut])
def patch_user(user_id: str, payload: UserPatch, request: Request, output: Response,
               actor: Actor, db: Db, expected: Expected):
    require_admin(db, actor, "users.manage")
    user = db.get(User, user_id)
    if user is None:
        raise Problem(404, "NOT_FOUND", "用户不存在")
    values = payload.model_dump(exclude_unset=True)
    if "group_id" in values:
        check_group(db, values["group_id"])
    if user.active and user.is_admin and (values.get("active") is False or values.get("is_admin") is False):
        # SQLite 用写锁，PostgreSQL 按固定顺序锁住管理员行，保护跨账号约束。
        admins = (User.active.is_(True), User.is_admin.is_(True))
        if db.bind.dialect.name == "sqlite":
            db.execute(update(User).where(*admins).values(revision=User.revision)
                       .execution_options(synchronize_session=False))
        else:
            db.scalars(select(User).where(*admins).order_by(User.id).with_for_update()).all()
        count = db.scalar(select(func.count()).select_from(User).where(User.active.is_(True), User.is_admin.is_(True)))
        if count <= 1:
            raise Problem(409, "CONFLICT", "至少需要保留一个启用的管理员")
    revision_update(db, user, values, expected)
    if values.get("active") is False:
        db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    audit(db, actor, "users.update", user.id)
    commit(db)
    output.headers["ETag"] = f'"{user.revision}"'
    return response(request, serialize(user))


@router.get("/groups", response_model=PageEnvelope[GroupOut])
def list_groups(request: Request, actor: Actor, db: Db, page: Page = 1, page_size: PageSize = 20, q: Search = ""):
    require_admin(db, actor, "groups.manage")
    items, pagination = page_data(db, search_query(select(UserGroup), q, UserGroup.name), page, page_size)
    return response(request, items, pagination=pagination)


@router.post("/groups", status_code=201, response_model=Envelope[GroupOut])
def create_group(payload: GroupCreate, request: Request, actor: Actor, db: Db):
    require_admin(db, actor, "groups.manage")
    group = UserGroup(id=new_id("grp"), **payload.model_dump())
    db.add(group)
    audit(db, actor, "groups.create", group.id)
    commit(db)
    return response(request, serialize(group))


@router.patch("/groups/{group_id}", response_model=Envelope[GroupOut])
def patch_group(group_id: str, payload: GroupPatch, request: Request, output: Response,
                actor: Actor, db: Db, expected: Expected):
    require_admin(db, actor, "groups.manage")
    group = db.get(UserGroup, group_id)
    if group is None:
        raise Problem(404, "NOT_FOUND", "用户组不存在")
    revision_update(db, group, payload.model_dump(exclude_unset=True), expected)
    audit(db, actor, "groups.update", group.id)
    commit(db)
    output.headers["ETag"] = f'"{group.revision}"'
    return response(request, serialize(group))
