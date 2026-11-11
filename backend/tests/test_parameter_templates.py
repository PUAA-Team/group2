from fastapi.testclient import TestClient

from conftest import create_group, create_user, login


def value(response, expected=200):
    assert response.status_code == expected, response.text
    return response.json()['data']


def setup(admin, workspace):
    base = f'/api/v1/workspaces/{workspace}'
    for task, trainer, name, source in [('text_classification', 'text-classifier-v1', '文本', 'builtin://text-linear-v1'),
                                      ('image_classification', 'image-classifier-v1', '图像', 'builtin://tiny-cnn-v1')]:
        asset = value(admin.post(base + '/models', json={'name': name, 'task_type': task, 'trainer_id': trainer, 'source_ref': source}), 201)
        value(admin.post(base + '/models/' + asset['id'] + '/versions', json={'version': 'v1', 'source_ref': source}), 201)
    choices = value(admin.get(base + '/job-options'))
    model = next(row for row in choices['models'] if row['task_type'] == 'text_classification')
    path = base + '/training-parameter-templates'
    payload = {'name': '团队短训练', 'task_type': 'text_classification', 'trainer_id': 'text-classifier-v1',
        'config': {'epochs': 2, 'batch_size': 4, 'learning_rate': 0.05}}
    return base, path, payload, model, choices


def test_templates_copy_values_revisions_archive_and_compatibility(admin, workspace):
    base, path, payload, model, choices = setup(admin, workspace)
    item = value(admin.post(path, json=payload), 201)
    assert set(item['config']) == {'epochs', 'batch_size', 'learning_rate', 'validation_ratio', 'seed'}
    url = path + '/' + item['id']
    resolved = value(admin.post(url + '/resolve', json={'model_version_id': model['id']}, headers={'If-Match': '1'}))
    assert resolved['config']['epochs'] == 2 and resolved['revision'] == 1
    updated = value(admin.patch(url, json={'name': '改名', 'config': {'epochs': 3}}, headers={'If-Match': '1'}))
    assert updated['revision'] == 2 and resolved['config']['epochs'] == 2
    assert admin.patch(url, json={'name': '旧更新', 'config': {}}, headers={'If-Match': '1'}).status_code == 412
    assert admin.post(url + '/resolve', json={'model_version_id': model['id']}, headers={'If-Match': '1'}).status_code == 412
    image = next(row for row in choices['models'] if row['task_type'] == 'image_classification')
    assert admin.post(url + '/resolve', json={'model_version_id': image['id']}, headers={'If-Match': '2'}).status_code == 422
    archived = value(admin.post(url + '/archive', json={'archived': True}, headers={'If-Match': '2'}))
    assert archived['archived'] and not value(admin.get(path))
    assert len(value(admin.get(path + '?status=archived'))) == 1
    assert admin.post(url + '/resolve', json={'model_version_id': model['id']}, headers={'If-Match': '3'}).status_code == 409
    value(admin.post(url + '/archive', json={'archived': False}, headers={'If-Match': '3'}))
    assert value(admin.post(url + '/resolve', json={'model_version_id': model['id']}, headers={'If-Match': '4'}))['config']['epochs'] == 3


def test_template_permissions_scope_names_and_invalid_config(app, admin, workspace):
    _, path, payload, model, _ = setup(admin, workspace)
    item = value(admin.post(path, json=payload), 201)
    assert admin.post(path, json=payload).status_code == 409
    assert admin.post(path, json={**payload, 'name': '无效', 'config': {'epochs': 0}}).status_code == 422
    assert admin.post(path, json={**payload, 'name': '无效', 'trainer_id': 'qwen-lora-v1'}).status_code == 422
    assert admin.post(path, json={**payload, 'name': '推理', 'config': {'inference': {'mode': 'generate'}}}).status_code == 422
    assert admin.patch(path + '/' + item['id'], json={'name': 'x', 'config': {}}).status_code == 428
    other = value(admin.post('/api/v1/workspaces', json={'name': '另一个空间'}), 201)
    cross = f"/api/v1/workspaces/{other['id']}/training-parameter-templates/{item['id']}"
    assert admin.post(cross + '/resolve', json={'model_version_id': model['id']}, headers={'If-Match': '1'}).status_code == 404
    group = create_group(admin); user = create_user(admin, group_id=group['id'])
    with TestClient(app) as member:
        login(member, 'member')
        assert member.get(path).status_code == 404
        value(admin.post(f'/api/v1/workspaces/{workspace}/members', json={'user_id': user['id'], 'role': 'viewer'}))
        assert member.get(path).status_code == 200
        assert member.post(path, json={**payload, 'name': 'viewer'}).status_code == 403
