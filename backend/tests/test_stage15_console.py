import csv
from datetime import datetime, timedelta, timezone
import io
import pytest

from sqlalchemy import select

from model_platform.database import utcnow
from model_platform.job_models import Job, ServiceCall, ServiceKey
from model_platform.models import AuditEvent, ModelAsset, ModelVersion, User
from model_platform.services import reports
from model_platform.services.service_calls import create_call, key_actor
from model_platform.job_schemas import CallInput
from model_platform.errors import Problem
from test_jobs import node_client, prepare, submit
from test_result_views import fixtures


def data(result, expected=200):
    assert result.status_code == expected, result.text
    return result.json()['data']


def test_project_archive_blocks_create_submit_and_claim_then_restores(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    project = data(admin.post(base + '/projects', json={'name': '团队项目', 'description': '文本实验'}), 201)
    pp = base + '/projects/' + project['id']
    assert data(admin.get(pp))['description'] == '文本实验'
    assert admin.patch(pp, json={'name': '改名'}).status_code == 428
    updated = data(admin.patch(pp, json={'name': '新项目名'}, headers={'If-Match': '1'}))
    assert updated['description'] == '文本实验'
    assert admin.patch(pp, json={'name': '旧更新'}, headers={'If-Match': '1'}).status_code == 412
    payload['project_id'] = project['id']
    queued = submit(admin, base, payload)
    draft = data(admin.post(base + '/jobs', json=payload), 201)
    data(admin.post(pp + '/archive', json={'archived': True}, headers={'If-Match': '2'}))
    assert not data(admin.get(base + '/projects?status=active'))
    assert len(data(admin.get(base + '/project-catalog?status=archived'))) == 1
    assert admin.post(base + '/jobs', json=payload).status_code == 409
    assert admin.post(base + '/jobs/' + draft['id'] + '/submit', headers={'If-Match': '1'}).status_code == 409
    assert '项目已归档' in data(admin.get(base + '/jobs/' + queued['id']))['queue_reason']
    with node_client(app, admin, workspace) as worker:
        assert data(worker.post('/api/worker/v1/claim', json={})) is None
        data(admin.post(pp + '/archive', json={'archived': False}, headers={'If-Match': '3'}))
        assert data(worker.post('/api/worker/v1/claim', json={}))['job_id'] == queued['id']
    assert data(admin.get(pp))['job_count'] == 2
    other = data(admin.post('/api/v1/workspaces', json={'name': '其他'}), 201)
    assert admin.get(f"/api/v1/workspaces/{other['id']}/projects/{project['id']}").status_code == 404


def test_asset_catalog_filters_use_latest_version(app, admin, workspace):
    base, _ = prepare(app, admin, workspace)
    item = data(admin.get(base + '/dataset-catalog'))[0]
    assert len(data(admin.get(base + '/dataset-catalog?version_status=available'))) == 1
    data(admin.post(base + '/datasets/' + item['id'] + '/versions', files={'file': ('new.csv', b'text,label\na,\n')}), 201)
    assert not data(admin.get(base + '/dataset-catalog?version_status=available'))
    assert len(data(admin.get(base + '/dataset-catalog?version_status=needs_annotation'))) == 1
    empty = data(admin.post(base + '/datasets', json={'name': '空数据', 'task_type': 'text_classification'}), 201)
    assert data(admin.get(base + '/dataset-catalog?version_status=unversioned'))[0]['id'] == empty['id']
    current = data(admin.get(base + '/datasets/' + item['id']))
    data(admin.post(base + '/datasets/' + item['id'] + '/archive', json={'archived': True, 'revision': current['revision']}))
    assert data(admin.get(base + '/dataset-catalog?status=archived'))[0]['id'] == item['id']
    assert all(not row['archived'] for row in data(admin.get(base + '/dataset-catalog?status=active')))


def test_key_usage_only_counts_attributed_predictions_and_not_polling(app, admin, workspace):
    base, _, service = fixtures(app, admin, workspace)
    a = data(admin.post(base + '/service-keys', json={'name': '应用A', 'job_id': service}), 201)
    b = data(admin.post(base + '/service-keys', json={'name': '应用B', 'job_id': service}), 201)
    api = f'/api/inference/v1/services/{service}'
    call = data(admin.post(api + '/predict', headers={'Authorization': 'Bearer ' + a['key']}, json={'text': '合成'}), 202)
    data(admin.get(api + '/calls/' + call['id'], headers={'Authorization': 'Bearer ' + a['key']}))
    data(admin.post(base + '/jobs/' + service + '/calls', json={'text': '网页调用'}), 202)
    rows = data(admin.get(base + '/service-keys?status=active&job_id=' + service))
    one = next(row for row in rows if row['id'] == a['id']); two = next(row for row in rows if row['id'] == b['id'])
    assert one['recorded_calls'] == 1 and one['last_called_at']
    assert two['recorded_calls'] == 0 and two['last_called_at'] is None
    assert a['key'] not in str(rows) and 'token_digest' not in str(rows)
    with app.state.sessions() as db:
        assert db.get(ServiceCall, call['id']).service_key_id == a['id']


def test_key_expiry_revision_bounds_revocation_and_rotation(app, admin, workspace):
    base, _, service = fixtures(app, admin, workspace)
    key = data(admin.post(base + '/service-keys', json={'name': '期限', 'job_id': service}), 201)
    path = base + '/service-keys/' + key['id']
    future = (utcnow() + timedelta(days=40)).isoformat()
    assert admin.patch(path, json={'expires_at': future}).status_code == 428
    changed = data(admin.patch(path, json={'expires_at': future}, headers={'If-Match': '1'}))
    assert changed['revision'] == 2
    assert admin.patch(path, json={'expires_at': future}, headers={'If-Match': '1'}).status_code == 412
    for invalid in [(utcnow() - timedelta(days=1)).isoformat(), (utcnow() + timedelta(days=366)).isoformat(), '2027-01-01T00:00:00']:
        assert admin.patch(path, json={'expires_at': invalid}, headers={'If-Match': '2'}).status_code == 422
    rotated = data(admin.post(path + '/rotate'))
    assert datetime.fromisoformat(rotated['expires_at']) == datetime.fromisoformat(future)
    assert admin.patch(path, json={'expires_at': future}, headers={'If-Match': '3'}).status_code == 409
    revoked = data(admin.post(base + '/service-keys/' + rotated['id'] + '/revoke'))
    assert revoked['revision'] == 2
    assert data(admin.get(base + '/service-keys?status=revoked'))
    assert admin.post(f'/api/inference/v1/services/{service}/predict', json={'text': 'x'}, headers={'Authorization': 'Bearer ' + rotated['key']}).status_code == 401


def test_key_is_rechecked_after_cached_authentication(app, admin, workspace):
    base, _, service = fixtures(app, admin, workspace)
    key = data(admin.post(base + '/service-keys', json={'name': '锁内复核', 'job_id': service}), 201)
    with app.state.sessions() as first:
        actor, cached = key_actor(first, key['key'], service)
        with app.state.sessions() as second:
            changed = second.get(ServiceKey, key['id']); changed.revoked_at = utcnow(); changed.revision += 1; second.commit()
        with pytest.raises(Problem) as error:
            create_call(first, actor, first.get(Job, service), CallInput(text='合成'), cached)
        assert error.value.code == 'INVALID_API_KEY'
        first.rollback()


def test_audit_filters_dates_and_safe_export_match(app, admin, workspace, monkeypatch):
    with app.state.sessions() as db:
        actor = db.scalar(select(User).where(User.account == 'owner')); actor.display_name = '=1+1'
        event = db.scalar(select(AuditEvent).where(AuditEvent.target_id == workspace, AuditEvent.action == 'workspaces.create'))
        event.created_at = datetime(2026, 10, 31, 16, tzinfo=timezone.utc); db.commit()
    params = {'space': workspace, 'action': 'workspaces.create', 'creator': '=1+1', 'created_from': '2026-11-01', 'created_to': '2026-11-01'}
    rows = data(admin.get('/api/v1/admin/asset-catalog/audit', params=params)); assert len(rows) == 1
    assert not data(admin.get('/api/v1/admin/asset-catalog/audit', params={**params, 'created_to': '2026-10-31', 'created_from': '2026-10-31'}))
    assert admin.get('/api/v1/admin/asset-catalog/audit', params={**params, 'created_from': '2026-11-02'}).status_code == 422
    result = admin.get('/api/v1/admin/audit-export', params=params)
    assert result.status_code == 200 and result.content.startswith(b'\xef\xbb\xbf')
    records = list(csv.reader(io.StringIO(result.content.decode('utf-8-sig'))))
    assert len(records) == len(rows) + 1 and records[1][2] == "'=1+1"
    assert 'token_digest' not in result.text and 'password_hash' not in result.text
    # 导出改走分页流式：即使每页只取 1 条也不再 422，仍完整导出全部命中行
    monkeypatch.setattr(reports, 'AUDIT_EXPORT_PAGE_SIZE', 1)
    result = admin.get('/api/v1/admin/audit-export', params=params)
    assert result.status_code == 200 and result.content.startswith(b'\xef\xbb\xbf')
    records = list(csv.reader(io.StringIO(result.content.decode('utf-8-sig'))))
    assert len(records) == len(rows) + 1 and records[1][2] == "'=1+1"


def test_evaluation_report_metrics_unknown_values_and_exports(app, admin, workspace):
    base, jobs, _ = fixtures(app, admin, workspace)
    with app.state.sessions() as db:
        job = db.get(Job, jobs[0]); job.result = {**job.result, 'labels': ['=first', 'second'],
            'confusion_matrix': [[1, 1], [0, 0]], 'private_sample': 'must-not-export'}; db.commit()
    path = base + '/jobs/' + jobs[0]
    summary = data(admin.get(path + '/evaluation-summary'))
    assert datetime.fromisoformat(summary['created_at']).tzinfo is not None
    assert summary['metrics']['accuracy'] == 0
    first, second = summary['per_class']
    assert first['precision'] == 1 and first['recall'] == 0.5 and first['f1'] == 2 / 3
    assert second['precision'] == 0 and second['recall'] is None and second['support'] == 0
    exported = admin.get(path + '/evaluation-report?format=json'); assert exported.status_code == 200
    assert exported.json()['per_class'] == summary['per_class'] and 'private_sample' not in exported.text
    csv_report = admin.get(path + '/evaluation-report?format=csv')
    assert csv_report.status_code == 200 and "'=first" in csv_report.content.decode('utf-8-sig')
    assert reports.classification_metrics(['a', 'b'], [[0, 0], [0, 0]])[0]['f1'] is None
    assert reports.classification_metrics(['a', 'b'], [[True, 0], [0, 1]]) is None
    other = data(admin.post('/api/v1/workspaces', json={'name': '他空间'}), 201)
    assert admin.get(f"/api/v1/workspaces/{other['id']}/jobs/{jobs[0]}/evaluation-report").status_code == 404
