"""失败写操作只记录安全元数据，不保存正文或异常详情。"""
import logging
import re

from .database import new_id
from .models import AuditEvent, Workspace

ACTIONS = {'create_dataset': 'datasets.create', 'upload_version': 'dataset_versions.create',
    'patch_dataset': 'datasets.update', 'create_model': 'models.create', 'create_version': 'model_versions.create',
    'new_job': 'jobs.create', 'submit': 'jobs.submit', 'edit_job': 'jobs.update',
    'update_policy': 'resources.device_policy.update', 'update_budget': 'groups.budget.update',
    'archive_dataset': 'datasets.archive', 'archive_model': 'models.archive',
    'execution_reconcile': 'resources.execution.reconcile'}


def record_failure(request, code):
    actor = getattr(request.state, 'actor_id', None)
    if not actor or request.method not in {'POST', 'PATCH', 'DELETE'} or not request.url.path.startswith('/api/v1/'):
        return
    try:
        # 请求作用域的依赖可能尚未关闭，先释放失败事务持有的写锁。
        source = getattr(request.state, 'db', None)
        if source is not None:
            source.rollback()
        route = request.scope.get('route')
        action = ACTIONS.get(getattr(route, 'name', ''), 'requests.failure')
        ids = {key: value for key, value in request.path_params.items() if isinstance(value, str) and re.fullmatch(r'[a-z]{2,4}_[a-f0-9]{32}', value)}
        target = next((value for key, value in ids.items() if key != 'workspace_id'), ids.get('workspace_id', 'new'))
        code = code if re.fullmatch(r'[A-Z0-9_]{1,64}', code) else 'REQUEST_FAILED'
        with request.app.state.sessions() as db:
            space = ids.get('workspace_id')
            if space and not db.get(Workspace, space):
                space = None
            db.add(AuditEvent(id=new_id('evt'), actor_id=actor, workspace_id=space,
                action=action, target_id=target, result='failure', error_code=code, request_id=request.state.request_id))
            db.commit()
    except Exception as error:
        logging.getLogger('model_platform').warning('failure_audit_unavailable type=%s', type(error).__name__)
