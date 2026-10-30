from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
import httpx

from conftest import PASSWORD, create_group, create_user, login
from model_platform.administration_models import Invitation
from model_platform.database import utcnow
from test_jobs import node_client, prepare, submit


def test_settings_revision_and_dataset_limits_apply(app, admin, workspace):
    result = admin.get('/api/v1/admin/settings').json()['data']
    revision = result.pop('revision')
    result.update(platform_name='团队训练中心', max_samples=2)
    update = admin.patch('/api/v1/admin/settings', headers={'If-Match': str(revision)}, json=result)
    assert update.status_code == 200, update.text
    assert admin.get('/api/v1/platform-info').json()['data']['platform_name'] == '团队训练中心'
    assert admin.patch('/api/v1/admin/settings', headers={'If-Match': str(revision)}, json=result).status_code == 412
    response = admin.post(f'/api/v1/workspaces/{workspace}/dataset-previews', data={'task_type':'text_classification'}, files={'file':('sample.csv', b'text,label\na,x\nb,y\nc,x\n')})
    assert response.status_code == 422


def test_global_catalog_crosses_workspaces_but_requires_administrator(app, admin, workspace):
    other = admin.post('/api/v1/workspaces', json={'name':'其他空间'}).json()['data']['id']
    for space, name in [(workspace,'数据甲'),(other,'数据乙')]:
        admin.post(f'/api/v1/workspaces/{space}/datasets', json={'name':name,'task_type':'text_classification'})
    result = admin.get('/api/v1/admin/asset-catalog/datasets').json()
    assert result['pagination']['total'] == 2
    assert all(item['workspace_name'] and item['actor_name'] for item in result['data'])
    assert admin.get('/api/v1/admin/asset-catalog/datasets', params={'space':other}).json()['pagination']['total'] == 1
    group = create_group(admin)
    create_user(admin, group_id=group['id'])
    with TestClient(app) as member:
        login(member, 'member')
        assert member.get('/api/v1/admin/asset-catalog/datasets').status_code == 403
        assert member.get('/api/v1/admin/settings').status_code == 403


def test_model_credentials_are_private_and_never_returned(app, admin, tmp_path):
    secret='private-test-key-012345'
    payload={'name':'测试连接','endpoint':'https://api.example.com/v1','model':'test-model','secret':secret}
    result = admin.post('/api/v1/admin/model-connections',json=payload)
    assert result.status_code == 201,result.text
    item = result.json()['data']
    assert item['credential_set'] and 'secret_ref' not in item and secret not in result.text
    assert secret not in admin.get('/api/v1/admin/model-connections').text
    path = next((app.state.settings.runtime_dir/'private/connections').glob('*.key'))
    assert path.read_text()==secret
    changed={key:value for key,value in payload.items() if key!='secret'}
    changed['name']='更名后'
    update=admin.patch('/api/v1/admin/model-connections/'+item['id'],headers={'If-Match':str(item['revision'])},json=changed)
    assert update.status_code==200 and update.json()['data']['credential_set']
    assert admin.post('/api/v1/admin/model-connections',json={**payload,'endpoint':'http://api.example.com/v1'}).status_code==422


def test_rejected_connection_revision_does_not_leave_new_credentials(app, admin):
    payload={'name':'版本保护','endpoint':'https://api.example.com/v1','model':'test','secret':'first-private-key'}
    item=admin.post('/api/v1/admin/model-connections',json=payload).json()['data']
    assert admin.patch('/api/v1/admin/model-connections/'+item['id'],headers={'If-Match':'1'},json={**payload,'secret':'second-private-key'}).status_code==200
    directory=app.state.settings.runtime_dir/'private/connections'
    before={path.name for path in directory.glob('*.key')}
    assert admin.patch('/api/v1/admin/model-connections/'+item['id'],headers={'If-Match':'1'},json={**payload,'secret':'rejected-private-key'}).status_code==412
    assert {path.name for path in directory.glob('*.key')}==before


def test_global_job_kind_respects_explicit_read_denial(admin):
    user=admin.get('/api/v1/auth/session').json()['data']['user']
    assert admin.patch('/api/v1/admin/users/'+user['id'],headers={'If-Match':str(user['revision'])},json={'deny_actions':['training.read']}).status_code==200
    assert admin.get('/api/v1/admin/asset-catalog/jobs?job_kind=train').status_code==403
    assert admin.get('/api/v1/admin/asset-catalog/jobs?job_kind=service').status_code==200


def test_connection_test_records_failure_without_credential_leak(admin):
    item=admin.post('/api/v1/admin/model-connections',json={'name':'受限地址','endpoint':'https://127.0.0.1/v1','model':'test','secret':'private-key'}).json()['data']
    result=admin.post('/api/v1/admin/model-connections/'+item['id']+'/test')
    assert result.status_code==200
    assert result.json()['data']['health']['code']=='INVALID_ENDPOINT'
    assert 'private-key' not in result.text


def test_connection_protocol_uses_server_secret_and_sanitizes_provider_errors(admin, monkeypatch):
    from model_platform.services import model_connections
    original_client = httpx.AsyncClient
    calls = []
    def provider(request):
        calls.append(request)
        assert request.headers['authorization'] == 'Bearer protocol-test-secret'
        return httpx.Response(200, json={'choices':[{'message':{'content':'OK'}}],'usage':{'total_tokens':2}})
    monkeypatch.setattr(model_connections, 'validate_remote', lambda endpoint: None)
    monkeypatch.setattr(model_connections.httpx, 'AsyncClient', lambda **kwargs: original_client(transport=httpx.MockTransport(provider), **kwargs))
    item=admin.post('/api/v1/admin/model-connections',json={'name':'协议验收','endpoint':'https://api.example.com/v1','model':'test','secret':'protocol-test-secret'}).json()['data']
    result=admin.post('/api/v1/admin/model-connections/'+item['id']+'/test')
    assert result.json()['data']['health']['status']=='available' and len(calls)==1
    assert calls[0].url.path=='/v1/chat/completions'
    monkeypatch.setattr(model_connections.httpx, 'AsyncClient', lambda **kwargs: original_client(transport=httpx.MockTransport(lambda request: httpx.Response(401,text='protocol-test-secret')), **kwargs))
    result=admin.post('/api/v1/admin/model-connections/'+item['id']+'/test')
    assert result.json()['data']['health']['status']=='failed' and 'protocol-test-secret' not in result.text


def test_invitation_register_is_single_use_and_does_not_allow_privilege_injection(app, admin, workspace):
    group=create_group(admin)
    invite=admin.post('/api/v1/admin/invitations',json={'workspace_id':workspace,'group_id':group['id'],'role':'viewer'}).json()['data']
    payload={'account':'newmember','display_name':'新成员','password':PASSWORD,'invitation':invite['invitation']}
    with TestClient(app) as newcomer:
        assert newcomer.post('/api/v1/auth/register',json={**payload,'is_admin':True}).status_code==422
        assert newcomer.post('/api/v1/auth/register',json={**payload,'password':'secret'}).status_code==422
        result=newcomer.post('/api/v1/auth/register',json=payload)
        assert result.status_code==201,result.text
        assert newcomer.post('/api/v1/auth/register',json={**payload,'account':'secondmember'}).status_code in (409,422)
        login(newcomer,'newmember')
        session=newcomer.get('/api/v1/auth/session').json()['data']
        assert not session['user']['is_admin'] and session['user']['group_id']==group['id']
        assert newcomer.get(f'/api/v1/workspaces/{workspace}/access').json()['data']['role']=='viewer'


def test_expired_or_disabled_invitation_cannot_create_account(app, admin, workspace):
    item=admin.post('/api/v1/admin/invitations',json={'workspace_id':workspace}).json()['data']
    with app.state.sessions() as db:
        invite=db.get(Invitation,item['id']);invite.expires_at=utcnow()-timedelta(seconds=1);db.commit()
    payload={'account':'expired','display_name':'过期','password':PASSWORD,'invitation':item['invitation']}
    with TestClient(app) as client:
        assert client.post('/api/v1/auth/register',json=payload).status_code==422
    config=admin.get('/api/v1/admin/settings').json()['data'];revision=config.pop('revision');config['invitations_enabled']=False
    admin.patch('/api/v1/admin/settings',json=config,headers={'If-Match':str(revision)})
    assert admin.post('/api/v1/admin/invitations',json={'workspace_id':workspace}).status_code==409


def test_password_reset_revokes_existing_sessions(app, admin):
    user=create_user(admin)
    with TestClient(app) as member:
        login(member,'member')
        assert admin.post(f"/api/v1/admin/users/{user['id']}/password",json={'password':'new-password-2026-strong'}).status_code==200
        assert member.get('/api/v1/auth/session').status_code==401
        assert member.post('/api/v1/auth/login',json={'account':'member','password':PASSWORD}).status_code==401
        assert member.post('/api/v1/auth/login',json={'account':'member','password':'new-password-2026-strong'}).status_code==200


def test_own_password_requires_original_and_revokes_self_session(app, admin):
    create_user(admin)
    with TestClient(app) as member:
        login(member,'member')
        assert member.post('/api/v1/auth/password',json={'current_password':'wrong','password':'new-self-password-2026'}).status_code==403
        assert member.post('/api/v1/auth/password',json={'current_password':PASSWORD,'password':'new-self-password-2026'}).status_code==200
        assert member.get('/api/v1/auth/session').status_code==401


def test_space_owner_protected_and_removed_member_loses_access(app, admin, workspace):
    user=create_user(admin)
    base=f'/api/v1/workspaces/{workspace}'
    admin.post(base+'/members',json={'user_id':user['id'],'role':'viewer'})
    owner=admin.get('/api/v1/auth/session').json()['data']['user']
    assert admin.post(base+f"/members/{owner['id']}/remove").status_code==409
    assert admin.post(base+f"/members/{user['id']}/remove").status_code==200
    with TestClient(app) as member:
        login(member,'member');assert member.get(base+'/access').status_code==404


def test_global_concurrency_limit_applies_across_nodes(app, admin, workspace, monkeypatch):
    original_registration = node_client.__globals__['registration']
    def distinct_machine(*args, **kwargs):
        value = original_registration(*args, **kwargs)
        value.update(machine_id=uuid4().hex * 2, installation_id=str(uuid4()))
        for device in value['inventory']['devices']:
            device['uuid'] += '-' + uuid4().hex
        return value
    monkeypatch.setitem(node_client.__globals__, 'registration', distinct_machine)
    base,payload=prepare(app,admin,workspace)
    config=admin.get('/api/v1/admin/settings').json()['data'];revision=config.pop('revision');config['global_concurrent_jobs']=1
    assert admin.patch('/api/v1/admin/settings',json=config,headers={'If-Match':str(revision)}).status_code==200
    submit(admin,base,payload);submit(admin,base,{**payload,'name':'第二次训练'})
    with node_client(app,admin,workspace) as first,node_client(app,admin,workspace) as second:
        assert first.post('/api/worker/v1/claim',json={}).json()['data']
        assert second.post('/api/worker/v1/claim',json={}).json()['data'] is None
    data=admin.get('/api/v1/admin/statistics').json()['data']
    assert data['counts']['jobs']==2 and data['counts']['active']==1
