"""智能辅助的确认边界、输出校验和采纳事务回归。"""
import json

import pytest
from sqlalchemy import select

from model_platform.assistant_models import AssistantRequest, WorkspaceAIPolicy
from model_platform.assistant_schemas import AssistantApply
from model_platform.data_models import AnnotationResult
from model_platform.models import User
from model_platform.operations_runner import run_assistant
from model_platform.services import assistant_requests
from model_platform.services.assistant_sources import redact
from model_platform.services.assistant_outputs import normalize
from model_platform.errors import Problem
from test_data_workflows import uploaded, batch
from test_jobs import prepare


def connection(admin):
    result = admin.post('/api/v1/admin/model-connections', json={
        'name': '隔离协议测试', 'endpoint': 'https://api.example.com/v1',
        'model': 'test', 'secret': 'test-only-key-1234'})
    assert result.status_code == 201, result.text
    return result.json()['data']['id']


def authorize(admin, base, identifier, **changes):
    revision = admin.get(base + '/assistant-policy').json()['data']['revision']
    result = admin.post(base + '/assistant-policy', json={
        'revision': revision, 'enabled': True, 'connection_ids': [identifier],
        'scopes': ['configuration', 'logs', 'text_samples'], **changes})
    assert result.status_code == 200, result.text
    return result.json()['data']


def preview(admin, base, identifier, **changes):
    result = admin.post(base + '/assistant-requests', json={
        'purpose': 'parameters', 'connection_id': identifier, **changes})
    assert result.status_code == 201, result.text
    return result.json()['data']


def queue(admin, base, item):
    result = admin.post(base + '/assistant-requests/' + item['id'] + '/confirm',
                        json={'input_digest': item['input_digest']})
    assert result.status_code == 200, result.text


def mock_completion(monkeypatch, output):
    calls = []
    async def complete(*args, **kwargs):
        calls.append(kwargs)
        return json.dumps(output), {'total_tokens': 20, 'prompt_tokens': True, 'cost': 123}
    monkeypatch.setattr('model_platform.operations_runner.completion', complete)
    return calls


def test_parameters_preview_confirm_and_idempotent_adoption(app, admin, workspace, monkeypatch):
    base, job = prepare(app, admin, workspace)
    identifier = connection(admin)
    authorize(admin, base, identifier)
    calls = mock_completion(monkeypatch, {'suggestions': [
        {'field': 'batch_size', 'value': 4, 'reason': '控制内存占用'}]})
    item = preview(admin, base, identifier, job=job)
    path = base + '/assistant-requests/' + item['id']
    assert not calls and 'messages' not in item
    assert admin.post(path + '/confirm', json={'input_digest': '0' * 64}).status_code == 409
    queue(admin, base, item)
    assert run_assistant(app.state.sessions, app.state.settings)
    done = admin.get(path).json()['data']
    assert done['status'] == 'succeeded' and done['usage'] == {'total_tokens': 20}
    adopted = admin.post(path + '/apply', json={'fields': ['batch_size']})
    assert adopted.status_code == 200, adopted.text
    again = admin.post(path + '/apply', json={'fields': ['batch_size']})
    assert again.status_code == 200, again.text
    assert again.json()['data']['target'] == adopted.json()['data']['target']
    assert admin.post(path + '/apply', json={'fields': ['batch_size'], 'name': '其他'}).status_code == 409
    target = admin.get(base + '/jobs/' + adopted.json()['data']['target']['job_id']).json()['data']
    assert target['status'] == 'draft' and target['config']['batch_size'] == 4


@pytest.mark.parametrize('change', ['policy', 'permissions'])
def test_execution_rechecks_authorization_after_queue(app, admin, workspace, monkeypatch, change):
    base, job = prepare(app, admin, workspace)
    identifier = connection(admin)
    authorize(admin, base, identifier)
    item = preview(admin, base, identifier, job=job)
    queue(admin, base, item)
    calls = mock_completion(monkeypatch, {'suggestions': []})
    with app.state.sessions() as db:
        if change == 'policy':
            db.get(WorkspaceAIPolicy, workspace).revision += 1
        else:
            db.scalar(select(User).where(User.account == 'owner')).deny_actions = ['assistants.use']
        db.commit()
    assert run_assistant(app.state.sessions, app.state.settings)
    assert not calls
    with app.state.sessions() as db:
        assert db.get(AssistantRequest, item['id']).status == 'failed'


def test_annotation_adoption_rolls_back_as_one_transaction(app, admin, workspace, monkeypatch):
    base, _, version = uploaded(admin, workspace)
    batch_path = batch(admin, base, version)
    identifier = connection(admin)
    authorize(admin, base, identifier)
    item = preview(admin, base, identifier, purpose='annotation',
                   source_id=batch_path.rsplit('/', 1)[1], sample_indices=[0])
    queue(admin, base, item)
    mock_completion(monkeypatch, {'samples': [{'index': 0, 'value': 'L0', 'reason': '语义判断'}]})
    assert run_assistant(app.state.sessions, app.state.settings)
    original_audit = assistant_requests.audit
    def failing_audit(db, actor, action, *args):
        if action == 'assistants.apply':
            raise RuntimeError('模拟采纳记录失败')
        return original_audit(db, actor, action, *args)
    monkeypatch.setattr(assistant_requests, 'audit', failing_audit)
    with app.state.sessions() as db:
        actor = db.scalar(select(User).where(User.account == 'owner'))
        request = db.get(AssistantRequest, item['id'])
        with pytest.raises(RuntimeError):
            assistant_requests.apply(db, actor, request, AssistantApply(indices=[0]))
        db.rollback()
    with app.state.sessions() as db:
        assert db.scalar(select(AnnotationResult).where(AnnotationResult.batch_id == item['source']['batch_id'])) is None


@pytest.mark.parametrize('output', [
    {'suggestions': [{'field': 'batch_size', 'value': '4', 'reason': '建议'}]},
    {'suggestions': [{'field': 'batch_size', 'value': -1, 'reason': '建议'}]},
    {'suggestions': [{'field': 'shell', 'value': 1, 'reason': '建议'}]},
])
def test_invalid_output_never_applied(app, admin, workspace, monkeypatch, output):
    base, job = prepare(app, admin, workspace)
    identifier = connection(admin)
    authorize(admin, base, identifier)
    item = preview(admin, base, identifier, job=job)
    queue(admin, base, item)
    mock_completion(monkeypatch, output)
    assert run_assistant(app.state.sessions, app.state.settings)
    path = base + '/assistant-requests/' + item['id']
    failed_result = admin.get(path).json()['data']
    assert failed_result['status'] == 'failed'
    assert failed_result['usage'] == {'total_tokens': 20}
    assert admin.post(path + '/apply', json={}).status_code == 409


def test_disabled_policy_still_configurable_by_owner(admin, workspace):
    base = f'/api/v1/workspaces/{workspace}'
    identifier = connection(admin)
    result = admin.get(base + '/assistant-options')
    assert result.status_code == 200
    assert identifier in {item['id'] for item in result.json()['data']['connections']}


def test_quoted_and_structured_credentials_are_redacted():
    counts = {}
    result = redact({'password': 'private-example-value',
        'text': 'error {"api_key": "private-example-key"} contact a@example.com'}, counts)
    assert 'private-example' not in json.dumps(result)
    assert 'a@example.com' not in json.dumps(result)


def test_daily_quota_and_cancel_prevent_call(app, admin, workspace, monkeypatch):
    base, job = prepare(app, admin, workspace)
    identifier = connection(admin)
    authorize(admin, base, identifier, daily_requests=1)
    first = preview(admin, base, identifier, job=job)
    second = preview(admin, base, identifier, job=job)
    queue(admin, base, first)
    assert admin.post(base + '/assistant-requests/' + second['id'] + '/confirm',
        json={'input_digest': second['input_digest']}).status_code == 429
    assert admin.post(base + '/assistant-requests/' + first['id'] + '/cancel').status_code == 200
    calls = mock_completion(monkeypatch, {'suggestions': []})
    assert not run_assistant(app.state.sessions, app.state.settings)
    assert not calls


def test_annotation_changed_before_confirmation_is_rejected(app, admin, workspace):
    base, _, version = uploaded(admin, workspace)
    path = batch(admin, base, version)
    identifier = connection(admin)
    authorize(admin, base, identifier)
    item = preview(admin, base, identifier, purpose='annotation',
        source_id=path.rsplit('/', 1)[1], sample_indices=[0])
    assert admin.post(path + '/results/0', json={'value': 'yes', 'revision': 0}).status_code == 200
    result = admin.post(base + '/assistant-requests/' + item['id'] + '/confirm',
        json={'input_digest': item['input_digest']})
    assert result.status_code == 409 and result.json()['error']['code'] == 'STALE_SAMPLE'


def test_logs_reject_invented_evidence():
    binding = {'evidence': [2], 'job': {'config': {}}}
    output = {'summary': '排查设备', 'causes': [{'reason': '设备不足', 'evidence': [999], 'steps': ['检查设备']}], 'suggestions': []}
    with pytest.raises(Problem) as error:
        normalize('logs', json.dumps(output), binding)
    assert error.value.code == 'INVALID_OUTPUT'
    output['causes'][0]['evidence'] = [2]
    assert normalize('logs', json.dumps(output), binding)['causes'][0]['evidence'] == [2]


def test_instruction_edits_publish_new_version(admin, workspace):
    original = b'{"instruction":"classify","input":"text","output":"yes"}\n'
    base, _, version = uploaded(admin, workspace, task='llm_sft', content=original)
    path = batch(admin, base, version, labels=[], limit=1)
    response = admin.post(path + '/results/0', json={'value': 'new answer', 'revision': 0,
        'edits': {'instruction': 'new instruction', 'input': ''}, 'submit': True})
    assert response.status_code == 200, response.text
    current = admin.get(path).json()['data']
    reviewed = admin.post(path + '/review', json={'indices': [0], 'decision': 'approved', 'revision': current['revision']})
    assert reviewed.status_code == 200, reviewed.text
    published = admin.post(path + '/publish')
    assert published.status_code == 200, published.text
    new_id = published.json()['data']['id']
    result = admin.get(base + '/dataset-versions/' + new_id + '/download')
    assert json.loads(result.content) == {'instruction': 'new instruction', 'input': '', 'output': 'new answer'}
    assert admin.get(base + '/dataset-versions/' + version['id'] + '/download').content == original


def test_assistant_daily_limit_is_scoped_per_user(app, admin, workspace):
    from conftest import create_user
    from model_platform.database import utcnow
    other = create_user(admin, account='assistant_other')
    conn_id = connection(admin)
    with app.state.sessions() as db:
        owner = db.scalar(select(User).where(User.account == 'owner'))
        db.add(AssistantRequest(
            id='asr_limit_test', workspace_id=workspace, created_by=owner.id, purpose='parameters',
            connection_id=conn_id, connection_revision=1, policy_revision=1, source={}, messages=[],
            preview={}, input_digest='a' * 64, max_tokens=256, expires_at=utcnow(), confirmed_at=utcnow(),
            status='succeeded', result={}, usage={}, error={},
        ))
        db.commit()
        assert assistant_requests.current_day_count(db, workspace, owner.id) == 1
        assert assistant_requests.current_day_count(db, workspace, other['id']) == 0
