import ipaddress

from fastapi import APIRouter, Request
from sqlalchemy import select

from ..errors import Problem, response
from ..models import User
from ..outputs import Envelope, SetupState, UserOut
from ..schemas import SetupInput
from ..services.common import serialize
from ..services.identity import initialize_admin
from .deps import Db

router = APIRouter(prefix="/api/v1/setup", tags=["首次设置"])


def local_setup_allowed(request):
    try:
        loopback = request.client and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        loopback = False
    return bool(request.app.state.settings.allow_browser_setup and loopback
                and request.url.hostname in {"localhost", "127.0.0.1", "::1"})


@router.get("", response_model=Envelope[SetupState])
def setup_state(request: Request, db: Db):
    initialized = db.scalar(select(User.id).where(User.is_admin.is_(True)).limit(1)) is not None
    return response(request, {"initialized": initialized, "enabled": local_setup_allowed(request) and not initialized})


@router.post("", status_code=201, response_model=Envelope[UserOut])
def setup(payload: SetupInput, request: Request, db: Db):
    if not local_setup_allowed(request):
        raise Problem(403, "FORBIDDEN", "网页初始化未开放，请联系部署管理员")
    user = initialize_admin(db, payload.to_user())
    return response(request, serialize(user))
