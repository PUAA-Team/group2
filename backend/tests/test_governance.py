from datetime import timedelta
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select

from conftest import create_user, login
from model_platform.compute_models import ComputeDevice, ComputeNode
from model_platform.database import utcnow
from model_platform.governance_models import NodeSample, StoredObject
from model_platform.job_models import Execution
from model_platform.models import User, UserGroup
from test_datasets import dataset_url
from test_jobs import node_client, prepare, submit


def data(result, expected=200):
    assert result.status_code == expected, result.text
    return result.json()['data']


def test_storage_counts_real_bytes_and_rejects_over_budget(app, admin, workspace):
    path = dataset_url(admin, workspace)
    content = b'text,label\na,yes\nb,no\n'
    version = data(admin.post(path + '/versions', files={'file': ('data.csv', content)}), 201)
    usage = data(admin.get(f'/api/v1/workspaces/{workspace}/storage-usage'))
    assert usage['personal_bytes'] == usage['workspace_bytes'] == len(content)
    assert usage['categories'] == {'dataset': len(content)}
    catalog = data(admin.get('/api/v1/admin/asset-catalog/datasets'))
    assert catalog[0]['storage_bytes'] == len(content) and catalog[0]['actor_name'] == '测试管理员'
    assert data(admin.get('/api/v1/admin/statistics'))['resources']['storage_bytes'] == len(content)
    group_id = admin.get('/api/v1/auth/session').json()['data']['user']['group_id']
    budget = data(admin.post(f'/api/v1/admin/groups/{group_id}/budget', json={'revision': 0, 'storage_gib': 0}))
    assert budget['usage']['storage_bytes'] == len(content)
    rejected = admin.post(path + '/versions', files={'file': ('data.csv', content)})
    assert rejected.status_code == 413 and rejected.json()['error']['code'] == 'GROUP_STORAGE_LIMIT'
    assert admin.get(path + '/versions').json()['pagination']['total'] == 1
    with app.state.sessions() as db:
        assert len(db.scalars(select(StoredObject)).all()) == 1
    assert data(admin.get(path))['revision'] == 2
    assert data(admin.get(path + f"/versions/{version['id']}/preview"))['samples'][0]['text'] == 'a'


def test_storage_reloads_group_quota_after_obtaining_write_lock(app, admin, workspace):
    from model_platform.errors import Problem
    from model_platform.permissions import effective_policy
    from model_platform.services.budgets import charge_objects
    with app.state.sessions() as db:
        actor = db.scalar(select(User).where(User.account == 'owner'))
        cached_group = db.get(UserGroup, actor.group_id)
        assert effective_policy(db, actor)[1]['storage_gib'] == 50
        with app.state.sessions() as other:
            group = other.get(UserGroup, actor.group_id)
            group.quota = {**group.quota, 'storage_gib': 0}; other.commit()
        assert cached_group.quota['storage_gib'] == 50
        with pytest.raises(Problem) as error:
            charge_objects(db, actor, [{'id': 'stale-quota-fixture', 'workspace_id': workspace,
                'kind': 'dataset', 'object_id': 'quota-fixture', 'storage_key': 'fixture/quota', 'size_bytes': 1}])
        assert error.value.code == 'STORAGE_LIMIT'


def test_archive_preserves_download_and_storage_but_blocks_new_versions(app, admin, workspace):
    path = dataset_url(admin, workspace)
    version = data(admin.post(path + '/versions', files={'file': ('data.csv', b'text,label\na,yes\nb,no\n')}), 201)
    asset = data(admin.get(path))
    archived = data(admin.post(path + '/archive', json={'revision': asset['revision'], 'archived': True}))
    assert archived['archived']
    assert len(data(admin.get('/api/v1/admin/asset-catalog/datasets?status=archived'))) == 1
    assert not data(admin.get('/api/v1/admin/asset-catalog/datasets?status=active'))
    assert admin.post(path + '/versions', files={'file': ('data.csv', b'text,label\na,yes')}).status_code == 409
    assert admin.get(path + f"/versions/{version['id']}/preview").status_code == 200
    assert data(admin.get(f'/api/v1/workspaces/{workspace}/storage-usage'))['workspace_bytes'] > 0
    assert admin.post(path + '/archive', json={'revision': asset['revision'], 'archived': False}).status_code == 412
    data(admin.post(path + '/archive', json={'revision': archived['revision'], 'archived': False}))
    assert admin.post(path + '/versions', files={'file': ('data.csv', b'text,label\na,yes')}).status_code == 201


def test_model_archive_blocks_new_version_until_restored(admin, workspace):
    from conftest import model_payload
    base = f'/api/v1/workspaces/{workspace}/models'
    model = data(admin.post(base, json=model_payload()), 201)
    path = base + '/' + model['id']
    archived = data(admin.post(path + '/archive', json={'revision': model['revision'], 'archived': True}))
    payload = {'version': 'v1', 'source_ref': 'team/text-model'}
    assert admin.post(path + '/versions', json=payload).status_code == 409
    assert admin.get(path).status_code == 200
    data(admin.post(path + '/archive', json={'revision': archived['revision'], 'archived': False}))
    assert admin.post(path + '/versions', json=payload).status_code == 201


def test_device_denial_and_shared_zero_budget_prevent_claim(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    submit(admin, base, payload)
    me = data(admin.get('/api/v1/auth/session'))['user']
    with node_client(app, admin, workspace) as worker:
        node = data(admin.get('/api/v1/admin/nodes'))[0]
        device = next(item for item in node['devices'] if item['kind'] == 'cpu')
        policy_path = f"/api/v1/resources/devices/{device['id']}/policy"
        policy = data(admin.post(policy_path, json={'revision': 0, 'allow_users': [me['id']], 'deny_groups': [me['group_id']]}))
        assert data(worker.post('/api/worker/v1/claim', json={})) is None
        data(admin.post(policy_path, json={**policy, 'deny_groups': []}))
        budget_path = f"/api/v1/admin/groups/{me['group_id']}/budget"
        budget = data(admin.post(budget_path, json={'revision': 0, 'concurrent_jobs': 0}))
        assert data(worker.post('/api/worker/v1/claim', json={})) is None
        data(admin.post(budget_path, json={'revision': budget['revision'], 'concurrent_jobs': 1}))
        assignment = data(worker.post('/api/worker/v1/claim', json={}))
        assert assignment
        assert data(admin.get(budget_path))['usage']['concurrent_jobs'] == 1
        with app.state.sessions() as db:
            assert db.get(Execution, assignment['execution_id']).group_id == me['group_id']


def test_archived_assets_block_queued_claim_and_new_jobs(app, admin, workspace):
    from model_platform.models import DatasetVersion
    base, payload = prepare(app, admin, workspace)
    submit(admin, base, payload)
    with app.state.sessions() as db:
        dataset_id = db.get(DatasetVersion, payload['dataset_version_id']).dataset_id
    path = base + '/datasets/' + dataset_id
    asset = data(admin.get(path))
    data(admin.post(path + '/archive', json={'revision': asset['revision'], 'archived': True}))
    assert admin.post(base + '/jobs', json=payload).status_code == 409
    with node_client(app, admin, workspace) as worker:
        assert data(worker.post('/api/worker/v1/claim', json={})) is None


def test_old_worker_cannot_take_new_job_but_can_finish_outstanding(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    submit(admin, base, payload)
    with node_client(app, admin, workspace) as worker:
        node_id = data(admin.get('/api/v1/admin/nodes'))[0]['id']
        def version(value):
            with app.state.sessions() as db:
                node = db.get(ComputeNode, node_id)
                node.inventory = {**node.inventory, 'runtime': {**node.inventory['runtime'], 'execution_contract_version': value}}
                db.commit()
        version(0)
        assert data(worker.post('/api/worker/v1/claim', json={})) is None
        version(1)
        assignment = data(worker.post('/api/worker/v1/claim', json={}))
        version(0)
        assert data(worker.post('/api/worker/v1/claim', json={}))['execution_id'] == assignment['execution_id']
        assert worker.post('/api/worker/v1/executions/' + assignment['execution_id'] + '/finish', json={'status': 'failed'}).status_code == 200


def test_history_keeps_unknown_values_and_does_not_invent_points(app, admin, workspace):
    with node_client(app, admin, workspace):
        node = data(admin.get('/api/v1/admin/nodes'))[0]
        device = node['devices'][0]
        path = f"/api/v1/resources/nodes/{node['id']}/history?device_id={device['id']}"
        assert data(admin.get(path))['points'] == []
        with app.state.sessions() as db:
            db.add(NodeSample(id='sample-zero', node_id=node['id'], seq=1,
                created_at=utcnow() - timedelta(minutes=1), metrics={device['id']: {'utilization': 0, 'used_memory_mb': None}}))
            db.add(NodeSample(id='sample-unknown', node_id=node['id'], seq=2,
                created_at=utcnow(), metrics={device['id']: {'utilization': None}}))
            db.commit()
        points = data(admin.get(path))['points']
        assert len(points) == 2 and points[0]['utilization'] == 0 and points[1]['utilization'] is None
        assert points[0]['used_memory_mb'] is None
        assert admin.get(path + '&hours=169').status_code == 422


def test_manual_reconciliation_requires_pause_and_retains_late_finish_conflict(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    submit(admin, base, payload)
    with node_client(app, admin, workspace) as worker:
        assignment = data(worker.post('/api/worker/v1/claim', json={}))
        identifier = assignment['execution_id']
        path = '/api/v1/admin/executions/' + identifier
        info = data(admin.get(path + '/review'))
        body = {'revision': info['job']['revision'], 'outcome': 'failed', 'reason': '已在隔离节点确认子进程退出', 'process_exit_confirmed': True}
        assert admin.post(path + '/reconcile', json=body).status_code == 409
        node = data(admin.get('/api/v1/admin/nodes'))[0]
        data(admin.patch('/api/v1/resources/nodes/' + node['id'], json={'enabled': False}, headers={'If-Match': str(node['revision'])}))
        with app.state.sessions() as db:
            item = db.get(ComputeNode, node['id']); item.active_executions = [identifier]; db.commit()
        assert admin.post(path + '/reconcile', json=body).status_code == 409
        with app.state.sessions() as db:
            item = db.get(ComputeNode, node['id']); item.last_seen_at = utcnow() - timedelta(minutes=2); db.commit()
        result = data(admin.post(path + '/reconcile', json=body))
        assert result['review']['reason'] == body['reason'] and result['job']['status'] == 'failed'
        assert identifier in result['node']['active_executions']  # 原始上报留存
        assert admin.post(path + '/reconcile', json=body).status_code == 409
        assert worker.post('/api/worker/v1/executions/' + identifier + '/finish', json={'status': 'failed'}).status_code == 409
        with app.state.sessions() as db:
            assert db.get(ComputeDevice, result['execution']['device_id']).reserved_execution_id is None


def test_resource_policy_and_review_are_admin_only(app, admin, workspace):
    me = data(admin.get('/api/v1/auth/session'))['user']
    user = create_user(admin, group_id=me['group_id'])
    data(admin.post(f'/api/v1/workspaces/{workspace}/members', json={'user_id': user['id'], 'role': 'editor'}))
    with TestClient(app) as client:
        login(client, 'member')
        assert client.get('/api/v1/admin/resource-principals').status_code == 403
        assert client.get(f"/api/v1/admin/groups/{me['group_id']}/budget").status_code == 403
        assert client.get('/api/v1/admin/executions/unknown/review').status_code == 403
