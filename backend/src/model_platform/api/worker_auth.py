from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from ..compute_models import ComputeNode
from ..errors import Problem
from ..security import digest
from .deps import Db

bearer = HTTPBearer(auto_error=False, scheme_name="WorkerCredential")


def worker_identity(db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)]):
    node = db.scalar(select(ComputeNode).where(ComputeNode.credential_digest == digest(credentials.credentials))) if credentials else None
    if not node or node.revoked:
        raise Problem(401, "INVALID_WORKER", "Worker 凭据无效")
    return node


Worker = Annotated[ComputeNode, Depends(worker_identity)]
