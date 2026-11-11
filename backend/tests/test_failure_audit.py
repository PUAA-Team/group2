from model_platform.models import AuditEvent
from sqlalchemy import select


def test_failed_write_audit_keeps_only_code_and_request_identifier(app, admin, workspace):
    marker = 'private-request-content-never-in-audit'
    response = admin.post(f'/api/v1/workspaces/{workspace}/datasets', json={'name': marker, 'task_type': 'invalid'})
    assert response.status_code == 422
    result = admin.get('/api/v1/admin/asset-catalog/audit?status=failure').json()['data']
    assert result and marker not in str(result)
    event = result[0]
    assert event['result'] == 'failure' and event['error_code'] == 'VALIDATION_ERROR'
    assert event['request_id'] == response.headers['x-request-id']
    assert event['action'] == 'datasets.create'
    assert admin.get(f'/api/v1/workspaces/{workspace}/audit').status_code == 200


def test_failed_revision_rolls_back_before_audit_write(app, admin, workspace):
    base = f'/api/v1/workspaces/{workspace}/datasets'
    item = admin.post(base, json={'name': '原始名称', 'task_type': 'text_classification'}).json()['data']
    response = admin.patch(base + '/' + item['id'], json={'name': '未生效名称'}, headers={'If-Match': '99'})
    assert response.status_code == 412
    assert admin.get(base + '/' + item['id']).json()['data']['name'] == '原始名称'
    records = admin.get('/api/v1/admin/asset-catalog/audit?status=failure').json()['data']
    assert records[0]['error_code'] == 'REVISION_MISMATCH'


def test_unauthenticated_failure_does_not_impersonate_user(app):
    from fastapi.testclient import TestClient
    with app.state.sessions() as db:
        before = len(db.scalars(select(AuditEvent)).all())
    with TestClient(app) as client:
        assert client.post('/api/v1/workspaces', json={'name': '匿名请求'}).status_code == 401
    with app.state.sessions() as db:
        assert len(db.scalars(select(AuditEvent)).all()) == before


def test_audit_write_failure_preserves_original_response_and_hides_details(app, admin, workspace, caplog):
    from sqlalchemy import event
    def reject(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().lower().startswith('insert into audit_events'):
            raise RuntimeError('private-audit-infrastructure-details')
    event.listen(app.state.engine, 'before_cursor_execute', reject)
    try:
        result = admin.post(f'/api/v1/workspaces/{workspace}/datasets', json={'name': '测试', 'task_type': 'invalid'})
        assert result.status_code == 422 and result.json()['error']['code'] == 'VALIDATION_ERROR'
        assert 'private-audit-' not in caplog.text and 'private-audit-' not in result.text
    finally:
        event.remove(app.state.engine, 'before_cursor_execute', reject)
