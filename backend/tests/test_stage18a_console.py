import io

from fastapi.testclient import TestClient

from conftest import PASSWORD, create_user, login, model_payload


def _ds_payload(name="18A数据集"):
    return {"name": name, "task_type": "text_classification", "description": ""}


def test_overview_pending_items_and_my_jobs(app, admin, workspace):
    # 创建普通成员并提交加入申请（待审批），验证 overview pending_items.join_requests
    create_user(admin, account="stage18_member")
    member_client = TestClient(app)

    invite = admin.post(f"/api/v1/workspaces/{workspace}/invites", json={
        "role": "editor",
        "require_approval": True,
    })
    assert invite.status_code == 201, invite.text
    code = invite.json()["data"]["code"]

    login(member_client, "stage18_member")
    join = member_client.post("/api/v1/workspaces/join", json={"code": code})
    assert join.status_code == 200, join.text

    # 管理员创建数据集与标注批次（待复核），并创建作业（验证 my-jobs 隔离）
    ds = admin.post(f"/api/v1/workspaces/{workspace}/datasets", json=_ds_payload("18A数据集")).json()["data"]
    csv_bytes = "text,label\n正面评论,pos\n负面评论,neg\n".encode("utf-8")
    ver = admin.post(
        f"/api/v1/workspaces/{workspace}/datasets/{ds['id']}/versions",
        files={"file": ("train.csv", io.BytesIO(csv_bytes), "text/csv")},
    ).json()["data"]

    batch_res = admin.post(f"/api/v1/workspaces/{workspace}/annotation-batches", json={
        "name": "待复核批次",
        "version_id": ver["id"],
        "labels": ["pos", "neg"],
    })
    assert batch_res.status_code == 201, batch_res.text
    batch = batch_res.json()["data"]
    assert batch["status"] == "open"

    mdl = admin.post(f"/api/v1/workspaces/{workspace}/models", json=model_payload(name="18A模型")).json()["data"]
    mver = admin.post(
        f"/api/v1/workspaces/{workspace}/models/{mdl['id']}/versions",
        json={"version": "v1", "source_ref": "hf://org/repo"},
    ).json()["data"]
    job = admin.post(f"/api/v1/workspaces/{workspace}/jobs", json={
        "name": "我的个人训练",
        "kind": "train",
        "model_version_id": mver["id"],
        "dataset_version_id": ver["id"],
        "device_kind": "cpu",
    }).json()["data"]

    ov = admin.get(f"/api/v1/workspaces/{workspace}/overview")
    assert ov.status_code == 200
    pending = {item["key"]: item["count"] for item in ov.json()["data"]["pending_items"]}
    assert pending["join_requests"] >= 1
    assert pending["annotation_batches"] >= 1
    assert "failed_jobs" not in pending

    my_jobs = admin.get(f"/api/v1/workspaces/{workspace}/my-jobs")
    assert my_jobs.status_code == 200
    assert any(item["id"] == job["id"] for item in my_jobs.json()["data"])


def test_dataset_version_report_and_admin_statistics_filters(app, admin, workspace):
    ds = admin.post(f"/api/v1/workspaces/{workspace}/datasets", json=_ds_payload("分布数据集")).json()["data"]
    csv_bytes = "text,label\n样本一,pos\n样本二,neg\n样本三,\n".encode("utf-8")
    ver_res = admin.post(
        f"/api/v1/workspaces/{workspace}/datasets/{ds['id']}/versions",
        files={"file": ("dist.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert ver_res.status_code == 201, ver_res.text
    ver = ver_res.json()["data"]

    report = admin.get(f"/api/v1/workspaces/{workspace}/datasets/{ds['id']}/versions/{ver['id']}/report")
    assert report.status_code == 200, report.text
    body = report.json()["data"]
    assert body["sample_count"] == 3
    assert body["empty_labels"] == 1
    assert body["integrity_ok"] is True
    dist = {item["label"]: item["count"] for item in body["label_distribution"]}
    assert dist["pos"] == 1
    assert dist["neg"] == 1
    assert body["sha256"] == ver["sha256"]

    # 按创建人筛选统计面板，不存在的 creator 应归零，owner 应有数据
    stats_all = admin.get(f"/api/v1/admin/statistics?space={workspace}")
    assert stats_all.status_code == 200
    assert stats_all.json()["data"]["counts"]["datasets"] >= 1

    stats_none = admin.get(f"/api/v1/admin/statistics?space={workspace}&creator=nonexistent_user")
    assert stats_none.status_code == 200
    assert stats_none.json()["data"]["counts"]["datasets"] == 0
    assert stats_none.json()["data"]["counts"]["jobs"] == 0

    stats_future = admin.get(f"/api/v1/admin/statistics?space={workspace}&created_from=2099-01-01")
    assert stats_future.status_code == 200
    assert stats_future.json()["data"]["counts"]["datasets"] == 0
