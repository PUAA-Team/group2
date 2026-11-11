import hashlib
import io
import json
import zipfile

import pytest
from sqlalchemy import select

from model_platform.errors import Problem
from model_platform.governance_models import StoredObject
from model_platform.services.dataset_mapping import inspect_columns, normalize_upload
from model_platform.services.presets import preset_content
from test_datasets import dataset_url


def test_mapped_csv_preview_save_hash_and_actual_storage_agree(app, admin, workspace):
    base = f'/api/v1/workspaces/{workspace}'
    content = '编号,正文,分类\n1,喜欢,好\n2,讨厌,坏\n'.encode()
    mapping = {'text': '正文', 'label': '分类'}
    inspect = admin.post(base + '/dataset-column-inspection', data={'task_type': 'text_classification'}, files={'file': ('raw.csv', content)})
    assert inspect.status_code == 200, inspect.text
    assert inspect.json()['data']['columns'] == ['编号', '正文', '分类']
    data = {'task_type': 'text_classification', 'column_mapping': json.dumps(mapping)}
    preview = admin.post(base + '/dataset-previews', data=data, files={'file': ('raw.csv', content)})
    assert preview.status_code == 200, preview.text
    expected = preview.json()['data']
    url = dataset_url(admin, workspace)
    saved = admin.post(url + '/versions', data=data, files={'file': ('raw.csv', content)})
    assert saved.status_code == 201, saved.text
    version = saved.json()['data']
    assert version['sha256'] == expected['sha256'] != hashlib.sha256(content).hexdigest()
    assert version['size_bytes'] == expected['size_bytes']
    assert version['provenance']['source']['sha256'] == hashlib.sha256(content).hexdigest()
    assert version['provenance']['ignored_columns'] == ['编号']
    samples = admin.get(url + '/versions/' + version['id'] + '/preview').json()['data']['samples']
    assert samples == [{'text': '喜欢', 'label': '好'}, {'text': '讨厌', 'label': '坏'}]
    with app.state.sessions() as db:
        assert db.scalar(select(StoredObject.size_bytes).where(StoredObject.object_id == version['id'])) == version['size_bytes']


@pytest.mark.parametrize('content,mapping', [
    (b'a,a\nx,y\n', {'text': 'a'}), (b'a,b\nx,y\n', {'text': 'missing'}),
    (b'a,b\nx,y\n', {'text': 'a', 'label': 'a'}), (b'a,b\nx,y\n', {'script': 'b'}),
    (b'a,b\nx\n', {'text': 'a'}), (b'a,b\nx,y\n', {'text': 1}),
    (b'a,b\nx,y\n', {}),
])
def test_invalid_mapping_is_rejected_before_persistence(content, mapping):
    with pytest.raises(Problem) as error:
        normalize_upload(content, 'text_classification', 'raw.csv', 3, mapping)
    assert error.value.status == 422


def test_optional_label_and_input_and_jsonl_mapped_types():
    _, _, _, rows, meta = normalize_upload(b'body\nhello\n', 'text_classification', 'raw.csv', 3, {'text': 'body'})
    assert rows == [{'text': 'hello', 'label': ''}] and meta['status'] == 'needs_annotation'
    raw = b'{"prompt":"classify","answer":"yes","unused":{"a":1}}\n'
    _, _, source, rows, _ = normalize_upload(raw, 'llm_sft', 'raw.jsonl', 3, {'instruction': 'prompt', 'output': 'answer'})
    assert rows == [{'instruction': 'classify', 'input': '', 'output': 'yes'}]
    assert source['ignored_columns'] == ['unused']
    with pytest.raises(Problem):
        normalize_upload(b'{"a":1,"b":"yes"}', 'llm_sft', 'raw.jsonl', 3, {'instruction': 'a', 'output': 'b'})
    with pytest.raises(Problem):
        inspect_columns(b'{"a":"x","a":"y"}', 'llm_sft', 'raw.jsonl', 3)


def test_image_mapping_preserves_image_bytes_and_validates_zip_paths(monkeypatch):
    _, raw = preset_content('image_classification')
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, 'w') as target:
        original = {}
        for info in source.infolist():
            data = source.read(info)
            if info.filename == 'labels.csv':
                data = data.replace(b'filename,label', b'path,category')
            else:
                original[info.filename] = data
            target.writestr(info.filename, data)
    monkeypatch.setattr('zipfile.time.localtime', lambda *args: (2026, 1, 1, 0, 0, 0, 0, 1, -1))
    _, mapped, _, rows, _ = normalize_upload(output.getvalue(), 'image_classification', 'raw.zip', 100, {'filename': 'path', 'label': 'category'})
    monkeypatch.setattr('zipfile.time.localtime', lambda *args: (2026, 1, 1, 0, 0, 10, 0, 1, -1))
    _, later, _, _, _ = normalize_upload(output.getvalue(), 'image_classification', 'raw.zip', 100, {'filename': 'path', 'label': 'category'})
    assert hashlib.sha256(mapped).hexdigest() == hashlib.sha256(later).hexdigest(), '预览与上传间隔不能改变标准ZIP摘要'
    assert rows and all(row['label'] for row in rows)
    with zipfile.ZipFile(io.BytesIO(mapped)) as result:
        assert all(result.read(name) == value for name, value in original.items())
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, 'w') as archive:
        archive.writestr('../escape.png', b'x'); archive.writestr('labels.csv', b'path,category\nx,y')
    with pytest.raises(Problem):
        inspect_columns(bad.getvalue(), 'image_classification', 'raw.zip', 100)
