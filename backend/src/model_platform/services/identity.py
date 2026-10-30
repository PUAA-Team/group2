from sqlalchemy import select, text, update

from ..database import new_id
from ..errors import Problem
from ..models import User
from ..permissions import effective_policy
from ..security import csrf_token, hash_password
from .common import audit, commit, serialize


def initialize_admin(db, payload):
    # 首次初始化也需串行，避免两个浏览器同时建立平台所有者。
    if db.bind.dialect.name == "sqlite":
        db.execute(update(User).values(revision=User.revision).execution_options(synchronize_session=False))
    else:
        db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    if db.scalar(select(User.id).where(User.is_admin.is_(True))) is not None:
        raise Problem(409, "CONFLICT", "管理员已设置，请登录")
    user = User(id=new_id("usr"), password_hash=hash_password(payload.password),
                **payload.model_dump(exclude={"password"}))
    db.add(user)
    db.flush()
    audit(db, user, "system.bootstrap", user.id)
    commit(db)
    return user


def session_data(db, user, raw):
    actions, quota = effective_policy(db, user)
    return {"user": serialize(user), "csrf_token": csrf_token(raw),
            "access": {"actions": sorted(actions), "quota": quota}}
