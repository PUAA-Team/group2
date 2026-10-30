from fastapi.testclient import TestClient

from conftest import create_group, create_user, login, model_payload
from test_jobs import node_client, prepare, submit


def test_overview_uses_whole_workspace_and_keeps_empty_counts(admin, workspace):
    base = f"/api/v1/workspaces/{workspace}"
    result = admin.get(base + "/overview")
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["counts"] == dict(projects=0, queued=0, active=0, succeeded=0, datasets=0, models=0)
    admin.post(base + "/projects", json={"name": "本空间项目"})
    other = admin.post("/api/v1/workspaces", json={"name": "隔离空间"}).json()["data"]["id"]
    admin.post(f"/api/v1/workspaces/{other}/projects", json={"name": "不可串入"})
    assert admin.get(base + "/overview").json()["data"]["counts"]["projects"] == 1


def test_catalog_classification_pagination_and_unversioned_assets(admin, workspace):
    base = f"/api/v1/workspaces/{workspace}"
    for index, source in enumerate(["builtin://text-linear-v1", "team/pretrained", "artifact://sample-job"]):
        model = admin.post(base + "/models", json=model_payload(name=f"模型{index}", source_ref=source)).json()["data"]
        admin.post(base + f"/models/{model['id']}/versions", json={"version": "v1", "source_ref": source})
    admin.post(base + "/models", json=model_payload(name="未登记版本"))
    data = admin.get(base + "/model-catalog?page_size=2").json()
    assert data["pagination"]["total"] == 4 and len(data["data"]) == 2
    for category in ["network", "prebuilt", "trained"]:
        result = admin.get(base + f"/model-catalog?category={category}").json()
        assert result["pagination"]["total"] == 1
        assert result["data"][0]["category"] == category
    assert admin.get(base + "/model-catalog?q=未登记").json()["data"][0]["latest_version"] is None
    assert admin.get(base + "/model-catalog?category=invalid").status_code == 422


def test_dataset_catalog_latest_version_and_type_filter(admin, workspace):
    base = f"/api/v1/workspaces/{workspace}"
    item = admin.post(base + "/datasets", json={"name": "文本数据", "task_type": "text_classification"}).json()["data"]
    for content in [b"text,label\na,x\nb,y\n", b"text,label\nc,x\nd,y\ne,x\n"]:
        result = admin.post(base + f"/datasets/{item['id']}/versions", files={"file": ("sample.csv", content)})
        assert result.status_code == 201, result.text
    latest = admin.get(base + "/dataset-catalog").json()["data"][0]["latest_version"]
    assert latest["number"] == 2 and latest["sample_count"] == 3 and "storage_key" not in latest
    assert admin.get(base + "/dataset-catalog?task_type=llm_sft").json()["pagination"]["total"] == 0


def test_upload_preview_validates_without_creating_assets(admin, workspace):
    base = f"/api/v1/workspaces/{workspace}"
    result = admin.post(base + "/dataset-previews", data={"task_type": "text_classification"}, files={"file": ("sample.csv", b"text,label\na,x\nb,y\n")})
    assert result.status_code == 200, result.text
    assert result.json()["data"]["sample_count"] == 2 and result.json()["data"]["sha256"]
    assert admin.get(base + "/datasets").json()["pagination"]["total"] == 0
    assert admin.post(base + "/dataset-previews", data={"task_type": "text_classification"}, files={"file": ("sample.csv", b"wrong,columns\na,x\n")}).status_code == 422


def test_overview_does_not_expose_forbidden_sections_or_other_workspaces(app, admin, workspace):
    group = create_group(admin, allow_actions=["datasets.read"])
    user = create_user(admin, group_id=group["id"])
    base = f"/api/v1/workspaces/{workspace}"
    admin.post(base + "/members", json={"user_id": user["id"], "role": "viewer"})
    other = admin.post("/api/v1/workspaces", json={"name": "保密空间"}).json()["data"]["id"]
    with TestClient(app) as member:
        login(member, "member")
        data = member.get(base + "/overview").json()["data"]
        assert data["counts"]["datasets"] == 0 and data["counts"]["models"] is None
        assert data["recent_jobs"] == [] and data["activity"] == []
        assert member.get(base + "/model-catalog").status_code == 403
        assert member.get(f"/api/v1/workspaces/{other}/overview").status_code == 404


def test_jobs_filters_and_project_summary_match_records(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    project = admin.post(base + "/projects", json={"name": "真实实验"}).json()["data"]
    payload["project_id"] = project["id"]
    submit(admin, base, payload)
    admin.post(base + "/jobs", json={**payload, "name": "尚未提交"})
    result = admin.get(base + "/jobs?status=queued&task_type=text_classification&device_kind=cpu").json()
    assert result["pagination"]["total"] == 1
    assert result["data"][0]["model_name"] and "artifact_key" not in result["data"][0]
    summary = admin.get(base + "/project-catalog").json()["data"][0]
    assert summary["job_count"] == 2 and summary["active_count"] == 1 and summary["best_accuracy"] is None
    assert admin.get(base + "/jobs?status=unknown").status_code == 422


def test_log_download_preserves_sequence_and_requires_workspace_access(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    job = submit(admin, base, payload)
    with node_client(app, admin, workspace) as worker:
        execution = worker.post("/api/worker/v1/claim", json={}).json()["data"]["execution_id"]
        for seq, message in [(1, "开始读取"), (2, "损失 0.0")]:
            assert worker.post(f"/api/worker/v1/executions/{execution}/events", json={"seq": seq, "type": "log", "payload": {"message": message}}).status_code == 200
    result = admin.get(base + f"/jobs/{job['id']}/logs")
    assert result.status_code == 200 and result.text == "开始读取\n损失 0.0\n"
    assert 'attachment;' in result.headers["content-disposition"]
    other = admin.post("/api/v1/workspaces", json={"name": "其他"}).json()["data"]["id"]
    assert admin.get(f"/api/v1/workspaces/{other}/jobs/{job['id']}/logs").status_code == 404
