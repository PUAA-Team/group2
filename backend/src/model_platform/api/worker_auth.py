from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from ..compute_models import ComputeNode
from ..database import aware, utcnow
from ..errors import Problem
from ..security import digest
from .deps import Db

bearer = HTTPBearer(auto_error=False, scheme_name="WorkerCredential")


def worker_identity(db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)]):
    node = db.scalar(select(ComputeNode).where(ComputeNode.credential_digest == digest(credentials.credentials))) if credentials else None
    if not node or node.revoked:
        raise Problem(401, "INVALID_WORKER", "Worker 凭据无效")
    # 凭据过期与被轮换一样直接 401；旧数据 credential_expires_at 为空时视为未过期。
    if node.credential_expires_at and aware(node.credential_expires_at) <= utcnow():
        raise Problem(401, "WORKER_CREDENTIAL_EXPIRED", "Worker 凭据已过期，请轮换凭据")
    return node


Worker = Annotated[ComputeNode, Depends(worker_identity)]
