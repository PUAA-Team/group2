import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from model_platform.main import create_app
from conftest import create_group, create_user, login


def dataset_url(admin, workspace, task_type="text_classification"):
    path = f"/api/v1/workspaces/{workspace}/datasets"
    result = admin.post(path, json={"name": f"测试数据-{task_type}", "task_type": task_type})
    assert result.status_code == 201, result.text
    return path + "/" + result.json()["data"]["id"]


def test_real_upload_immutable_preview_and_restart(admin, workspace, settings):
    url = dataset_url(admin, workspace)
    content = "text,label\n测试文本,正向\n另一个,负向\n".encode()
    result = admin.post(url + "/versions", files={"file": ("train.csv", content, "text/csv")})
    assert result.status_code == 201, result.text
    version = result.json()["data"]
    assert version["sha256"] == hashlib.sha256(content).hexdigest()
    assert version["size_bytes"] == len(content) and version["sample_count"] == 2
    assert version["status"] == "available" and "storage_key" not in version
    assert admin.get(url).json()["data"]["revision"] == 2
    second = admin.post(url + "/versions", files={"file": ("train.csv", b"text,label\nnew,\n")}).json()["data"]
    assert second["number"] == 2 and second["status"] == "needs_annotation"
    app2 = create_app(settings)
    try:
        with TestClient(app2) as restarted:
            login(restarted)
            preview = restarted.get(url + f"/versions/{version['id']}/preview", params={"limit": 1})
            assert preview.status_code == 200
            assert preview.json()["data"]["samples"] == [{"text": "测试文本", "label": "正向"}]
            assert len(restarted.get(url + "/versions").json()["data"]) == 2
    finally:
        app2.state.engine.dispose()


@pytest.mark.parametrize("filename,content,status", [
    ("train.csv", b"", 422), ("train.csv", b"text,wrong\na,b\n", 422),
    ("train.csv", b"text,label\n,yes\n", 422), ("train.csv", b"text,label\na\n", 422),
    ("train.csv", b"text,label\n\xff,yes\n", 422), ("../train.csv", b"text,label\na,b", 422),
    ("..\\train.csv", b"text,label\na,b", 422), ("images.zip", b"archive", 415),
    ("train.csv", b"text,label\n" + b"a,b\n" * 4, 422), ("train.csv", b"x" * 2049, 413),
])
def test_invalid_upload_leaves_no_versions_or_files(admin, workspace, settings, filename, content, status):
    url = dataset_url(admin, workspace)
    result = admin.post(url + "/versions", files={"file": (filename, content)})
    assert result.status_code == status, result.text
    assert admin.get(url + "/versions").json()["pagination"]["total"] == 0
    assert admin.get(url).json()["data"]["revision"] == 1
    assert not settings.storage_dir.exists() or not list(settings.storage_dir.rglob("*.*"))


def test_jsonl_and_image_format_boundary(admin, workspace):
    url = dataset_url(admin, workspace, "llm_sft")
    content = json.dumps({"instruction": "分类", "input": "文本", "output": "积极"}, ensure_ascii=False).encode()
    assert admin.post(url + "/versions", files={"file": ("sft.jsonl", content)}).status_code == 201
    for invalid in [b'{"instruction":"x"}', b"{bad}", b'{"instruction":"x","output":"y","script":"run"}']:
        assert admin.post(url + "/versions", files={"file": ("sft.jsonl", invalid)}).status_code == 422
    image_url = dataset_url(admin, workspace, "image_classification")
    assert admin.post(image_url + "/versions", files={"file": ("images.zip", b"zip")}).status_code == 422


def test_preview_cross_workspace_and_audit(app, admin, workspace):
    url = dataset_url(admin, workspace)
    version = admin.post(url + "/versions", files={"file": ("train.csv", b"text,label\nsecret,yes")}).json()["data"]
    group = create_group(admin)
    user = create_user(admin, group_id=group["id"])
    with TestClient(app) as client:
        login(client, "member")
        preview = client.get(url + f"/versions/{version['id']}/preview")
        assert preview.status_code == 404 and "secret" not in preview.text
        assert client.post(url + "/versions", files={"file": ("train.csv", b"text,label\nx,y")}).status_code == 404
    records = admin.get(f"/api/v1/workspaces/{workspace}/audit").json()["data"]
    assert any(row["action"] == "dataset_versions.create" for row in records)
    assert "secret" not in json.dumps(records)


def test_dataset_metadata_requires_revision(admin, workspace):
    url = dataset_url(admin, workspace)
    assert admin.patch(url, json={"name": "renamed"}).status_code == 428
    assert admin.patch(url, json={"name": "renamed"}, headers={"If-Match": '"1"'}).status_code == 200
    assert admin.patch(url, json={"task_type": "llm_sft"}, headers={"If-Match": '"2"'}).status_code == 422
