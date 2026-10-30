from fastapi.testclient import TestClient

from conftest import create_group, create_user, login, model_payload


def test_group_personal_deny_quota_and_viewer(app, admin, workspace):
    group = create_group(admin, deny_actions=["models.write"])
    user = create_user(admin, group_id=group["id"], allow_actions=["models.write"],
                       deny_actions=["audit.read"], quota={"gpu_count": 1, "storage_gib": 100})
    path = f"/api/v1/workspaces/{workspace}"
    assert admin.post(path + "/members", json={"user_id": user["id"], "role": "editor"}).status_code == 200
    with TestClient(app) as client:
        login(client, "member")
        policy = client.get(path + "/access").json()["data"]
        assert policy["quota"] == {"gpu_count": 1, "storage_gib": 50, "concurrent_jobs": 3}
        assert "models.write" not in policy["actions"] and "audit.read" not in policy["actions"]
        assert client.post(path + "/models", json=model_payload()).status_code == 403
        assert client.post(path + "/datasets", json={"name": "text", "task_type": "text_classification"}).status_code == 201
        assert admin.post(path + "/members", json={"user_id": user["id"], "role": "viewer"}).status_code == 200
        assert client.post(path + "/datasets", json={"name": "other", "task_type": "text_classification"}).status_code == 403


def test_nonmember_and_cross_workspace_identifiers(app, admin, workspace):
    group = create_group(admin)
    user = create_user(admin, group_id=group["id"])
    path = f"/api/v1/workspaces/{workspace}"
    model = admin.post(path + "/models", json=model_payload()).json()["data"]
    with TestClient(app) as client:
        login(client, "member")
        assert client.get(path + "/models").status_code == 404
        assert client.get("/api/v1/workspaces").json()["pagination"]["total"] == 0
        second = client.post("/api/v1/workspaces", json={"name": "独立空间"}).json()["data"]["id"]
        assert client.get(f"/api/v1/workspaces/{second}/models/{model['id']}").status_code == 404
    assert admin.post(path + "/members", json={"user_id": user["id"], "role": "viewer"}).status_code == 200


def test_admin_explicit_deny_and_revisions(app, admin):
    user = create_user(admin, account="second", is_admin=True, deny_actions=["groups.manage"])
    with TestClient(app) as client:
        login(client, "second")
        assert client.get("/api/v1/admin/groups").status_code == 403
    path = f"/api/v1/admin/users/{user['id']}"
    assert admin.patch(path, json={"display_name": "changed"}).status_code == 428
    assert admin.patch(path, json={"display_name": "changed"}, headers={"If-Match": '"1"'}).status_code == 200
    assert admin.patch(path, json={"display_name": "stale"}, headers={"If-Match": '"1"'}).status_code == 412


def test_models_versions_concurrency_and_pagination(admin, workspace):
    path = f"/api/v1/workspaces/{workspace}/models"
    created = admin.post(path, json=model_payload())
    assert created.status_code == 201, created.text
    model = created.json()["data"]
    url = path + "/" + model["id"]
    assert admin.get(url).headers["etag"] == '"1"'
    assert admin.patch(url, json={"description": "v2"}, headers={"If-Match": '"1"'}).headers["etag"] == '"2"'
    assert admin.patch(url, json={"name": "stale"}, headers={"If-Match": '"1"'}).status_code == 412
    payload = {"version": "v1", "source_ref": "team/model@commit"}
    assert admin.post(url + "/versions", json=payload).status_code == 201
    assert admin.post(url + "/versions", json=payload).status_code == 409
    assert admin.patch(url + "/versions", json=payload).status_code == 405
    assert admin.get(url + "/versions").json()["data"][0]["status"] == "registered"
    assert admin.post(path, json=model_payload(name="第二个模型")).status_code == 201
    page = admin.get(path, params={"page_size": 1, "page": 2}).json()
    assert page["pagination"]["total"] == 2 and len(page["data"]) == 1
    assert admin.get(path, params={"page_size": 101}).status_code == 422


def test_source_trainer_and_status_validation(admin, workspace):
    path = f"/api/v1/workspaces/{workspace}/models"
    for payload in [model_payload(trainer_id="unknown"), model_payload(task_type="llm_sft"),
                    model_payload(source_ref="https://secret:password@host/model"),
                    model_payload(source_ref="https://host/model?access_token=secret"),
                    model_payload(status="available")]:
        assert admin.post(path, json=payload).status_code == 422
    templates = admin.get("/api/v1/trainer-templates").json()["data"]
    assert {row["id"] for row in templates} == {"text-classifier-v1", "image-classifier-v1", "qwen-lora-v1"}
    assert all(row["execution_available"] for row in templates)


def test_group_patch_revision_and_unknown_policy(admin):
    group = create_group(admin)
    path = f"/api/v1/admin/groups/{group['id']}"
    assert admin.patch(path, json={"quota": {"gpu_count": -1}}, headers={"If-Match": '"1"'}).status_code == 422
    assert admin.patch(path, json={"name": "更新组"}, headers={"If-Match": '"1"'}).status_code == 200
    assert admin.patch(path, json={"name": "旧修改"}, headers={"If-Match": '"1"'}).status_code == 412
