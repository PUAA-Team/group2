"""隔离元数据夹具验证评估、调用记录和密钥边界，不代表真实训练。"""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from conftest import create_user, login
from model_platform.database import new_id, utcnow
from model_platform.errors import Problem
from model_platform.job_models import Job, ServiceCall, ServiceKey
from model_platform.job_schemas import JobInput
from model_platform.models import DatasetVersion, User
from model_platform.services import service_calls
from model_platform.services.evaluation_errors import validate_errors
from model_platform.services.call_lifecycle import finish_call
from test_jobs import prepare


def fixtures(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    with app.state.sessions() as db:
        actor = db.scalar(select(User).where(User.account == 'owner'))
        version = db.get(DatasetVersion, payload['dataset_version_id'])
        config = JobInput(**payload).config.model_dump()
        jobs = []
        for index in range(2):
            job = Job(id=new_id('job'), workspace_id=workspace, created_by=actor.id,
                name=f'协议评估{index}', kind='evaluate', status='succeeded', config=config,
                model_version_id=payload['model_version_id'], dataset_version_id=version.id,
                snapshot={'task_type': 'text_classification', 'dataset_sha256': version.sha256},
                result={'accuracy': index / 2, 'macro_f1': 0, 'samples': 16})
            db.add(job); jobs.append(job.id)
        service = Job(id=new_id('job'), workspace_id=workspace, created_by=actor.id,
            name='协议服务', kind='service', status='ready', model_version_id=payload['model_version_id'],
            config=config, snapshot={'task_type': 'text_classification'})
        db.add(service); db.commit()
        return base, jobs, service.id


def test_compare_fixed_data_missing_metrics_and_zero(app, admin, workspace):
    base, jobs, _ = fixtures(app, admin, workspace)
    result = admin.get(base + '/evaluation-comparison', params=[('ids', value) for value in jobs])
    assert result.status_code == 200, result.text
    items = result.json()['data']['items']
    assert items[0]['metrics']['accuracy'] == 0
    assert 'loss' not in items[0]['metrics']
    assert admin.get(base + '/evaluation-comparison', params=[('ids', jobs[0])] * 2).status_code == 422
    assert admin.get(base + '/evaluation-comparison', params={'ids': jobs[0]}).status_code == 422
    with app.state.sessions() as db:
        job = db.get(Job, jobs[1]); job.config = {**job.config, 'seed': 99}; db.commit()
    assert admin.get(base + '/evaluation-comparison', params=[('ids', value) for value in jobs]).status_code == 409


def test_comparison_rejects_other_workspace_and_nonmember(app, admin, workspace):
    base, jobs, _ = fixtures(app, admin, workspace)
    other = admin.post('/api/v1/workspaces', json={'name': '另一空间'}).json()['data']['id']
    assert admin.get(f'/api/v1/workspaces/{other}/evaluation-comparison', params=[('ids', value) for value in jobs]).status_code == 404
    create_user(admin)
    with TestClient(app) as member:
        login(member, 'member')
        assert member.get(base + '/evaluation-comparison', params=[('ids', value) for value in jobs]).status_code == 404


def test_call_history_never_exposes_payload_and_statistics_keep_unknown(app, admin, workspace):
    base, _, service_id = fixtures(app, admin, workspace)
    with app.state.sessions() as db:
        service = db.get(Job, service_id)
        legacy = ServiceCall(id=new_id('cal'), job_id=service_id, created_by=service.created_by,
            status='succeeded', input={'text': 'private-input'}, result={'text': 'private-output'})
        timed = ServiceCall(id=new_id('cal'), job_id=service_id, created_by=service.created_by,
            created_at=utcnow() - timedelta(seconds=1), status='pending', input={'text': 'other'})
        db.add_all([legacy, timed]); db.flush(); finish_call(timed, 'failed', {'error': 'private-error'}); db.commit()
    path = base + '/jobs/' + service_id
    result = admin.get(path + '/call-history?page_size=1')
    assert result.json()['pagination']['total'] == 2
    assert 'private-' not in result.text and '"input"' not in result.text and '"result"' not in result.text
    counts = admin.get(path + '/call-statistics').json()['data']
    assert counts['total'] == 2 and counts['failed'] == 1 and counts['measured_calls'] == 1
    assert counts['mean_ms'] >= 1000
    assert admin.get(path + '/call-history?status=failed').json()['pagination']['total'] == 1


def test_rotation_revokes_old_value_without_extending_expiry(app, admin, workspace):
    base, _, service_id = fixtures(app, admin, workspace)
    old = admin.post(base + '/service-keys', json={'name': '轮换', 'job_id': service_id, 'days': 2}).json()['data']
    result = admin.post(base + '/service-keys/' + old['id'] + '/rotate')
    assert result.status_code == 200, result.text
    new = result.json()['data']
    assert new['key'] != old['key'] and new['expires_at'] == old['expires_at']
    assert new['key'] not in admin.get(base + '/service-keys').text
    assert admin.post(base + '/service-keys/' + old['id'] + '/rotate').status_code == 409
    with app.state.sessions() as db:
        with pytest.raises(Problem): service_calls.key_actor(db, old['key'], service_id)
        assert service_calls.key_actor(db, new['key'], service_id)[0]


def test_failed_rotation_keeps_original_key(app, admin, workspace, monkeypatch):
    base, _, service_id = fixtures(app, admin, workspace)
    old = admin.post(base + '/service-keys', json={'name': '事务', 'job_id': service_id}).json()['data']
    def fail(*args, **kwargs): raise RuntimeError('模拟新密钥创建失败')
    monkeypatch.setattr(service_calls, 'create_key', fail)
    with app.state.sessions() as db:
        actor = db.scalar(select(User).where(User.account == 'owner'))
        with pytest.raises(RuntimeError): service_calls.rotate_key(db, actor, workspace, old['id'])
        db.rollback()
    with app.state.sessions() as db:
        assert db.get(ServiceKey, old['id']).revoked_at is None


def test_error_samples_are_bound_to_actual_source(app, admin, workspace):
    base, jobs, _ = fixtures(app, admin, workspace)
    with app.state.sessions() as db:
        job = db.get(Job, jobs[0])
        result = {**job.result, 'labels': ['正向', '负向'], 'error_sample_count': 1,
            'error_samples': [{'index': 0, 'actual': '正向', 'predicted': '负向'}]}
        validate_errors(db, app.state.settings, job, result)
        job.result = result; db.commit()
        invalid = {**result, 'error_samples': [{'index': 0, 'actual': '负向', 'predicted': '正向'}]}
        with pytest.raises(Problem): validate_errors(db, app.state.settings, job, invalid)
    result = admin.get(base + '/jobs/' + jobs[0] + '/error-samples').json()['data']
    assert result['supported'] and result['samples'][0]['source']['label'] == '正向'
    assert not admin.get(base + '/jobs/' + jobs[1] + '/error-samples').json()['data']['supported']


def test_error_sample_source_must_match_execution_snapshot(app, admin, workspace):
    base, jobs, _ = fixtures(app, admin, workspace)
    with app.state.sessions() as db:
        job = db.get(Job, jobs[0])
        job.result = {'labels': ['正向', '负向'], 'error_samples': [], 'error_sample_count': 0}
        job.snapshot = {**job.snapshot, 'dataset_sha256': '0' * 64}
        db.commit()
    assert admin.get(base + '/jobs/' + jobs[0] + '/error-samples').status_code == 409


def test_call_creation_rechecks_current_service_status(app, admin, workspace):
    from model_platform.job_schemas import CallInput
    _, _, service_id = fixtures(app, admin, workspace)
    with app.state.sessions() as db:
        actor = db.scalar(select(User).where(User.account == 'owner'))
        cached = db.get(Job, service_id)
        with app.state.sessions() as other:
            service = other.get(Job, service_id); service.status = 'stopped'; other.commit()
        with pytest.raises(Problem):
            service_calls.create_call(db, actor, cached, CallInput(text='合成请求'))
