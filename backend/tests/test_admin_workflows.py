from fastapi.testclient import TestClient

from conftest import create_user, login
from model_platform.assistant_models import AssistantRequest
from model_platform.data_models import DataOperation
from test_assistants import authorize, connection, preview
from test_jobs import prepare


def test_global_workflows_return_only_metadata_and_filter_space(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    conn = connection(admin); authorize(admin, base, conn)
    request = preview(admin, base, conn, job=payload)
    operation = admin.post(base + '/data-operations', json={'name': '元数据清洗', 'kind': 'clean',
        'version_id': payload['dataset_version_id'], 'options': {}}).json()['data']
    with app.state.sessions() as db:
        item = db.get(AssistantRequest, request['id'])
        item.messages = [{'content': 'hidden-model-message'}]
        item.preview = {'body': 'hidden-preview'}; item.result = {'body': 'hidden-result'}; item.usage = {'total_tokens': 0}
        db.get(DataOperation, operation['id']).candidates = [{'body': 'hidden-candidate'}]
        db.commit()
    for kind in ('operations', 'assistants'):
        response = admin.get('/api/v1/admin/workflow-catalog/' + kind)
        assert response.status_code == 200, response.text
        assert 'hidden-' not in response.text
        assert len(response.json()['data']) == 1
        assert not {'messages', 'preview', 'source', 'result', 'candidates', 'secret'}.intersection(response.json()['data'][0])
    result = admin.get('/api/v1/admin/workflow-catalog/assistants?q=智能参数').json()['data']
    assert len(result) == 1 and result[0]['reported_tokens'] == 0
    other = admin.post('/api/v1/workspaces', json={'name': '空空间'}).json()['data']['id']
    assert not admin.get('/api/v1/admin/workflow-catalog/operations?space=' + other).json()['data']
    assert not admin.get('/api/v1/admin/workflow-catalog/assistants?status=failed').json()['data']


def test_global_workflow_permissions_are_separate(app, admin):
    create_user(admin, account='restricted-admin', is_admin=True, deny_actions=['assistants.use'])
    with TestClient(app) as client:
        login(client, 'restricted-admin')
        assert client.get('/api/v1/admin/workflow-catalog/assistants').status_code == 403
        assert client.get('/api/v1/admin/workflow-catalog/operations').status_code == 200
    create_user(admin, account='plain-member')
    with TestClient(app) as client:
        login(client, 'plain-member')
        assert client.get('/api/v1/admin/workflow-catalog/operations').status_code == 403
