import io
from contextlib import ExitStack

from fastapi.testclient import TestClient

from conftest import create_group, create_user, login, model_payload
from test_device_purposes import attach, data


def test_workspace_roles_annotator_admin_and_owner_transfer(app, admin, workspace):
    grp = create_group(
        admin,
        name="研发组21A",
        allow_actions=["datasets.read", "datasets.write", "models.read", "models.write", "training.read", "training.write", "assistants.use"],
        quota={"gpu_count": 2, "concurrent_jobs": 4, "storage_gib": 50},
    )
    ann_user = create_user(admin, account="ann21a", group_id=grp["id"])
    sub_admin = create_user(admin, account="wsadmin21a", group_id=grp["id"])
    dev_user = create_user(admin, account="dev21a", group_id=grp["id"])

    # 将成员加入空间：annotator / admin / editor（带子配额）
    data(admin.post(f"/api/v1/workspaces/{workspace}/members", json={"user_id": ann_user["id"], "role": "annotator"}))
    data(admin.post(f"/api/v1/workspaces/{workspace}/members", json={"user_id": sub_admin["id"], "role": "admin"}))
    data(admin.post(f"/api/v1/workspaces/{workspace}/members", json={
        "user_id": dev_user["id"], "role": "editor", "quota": {"gpu_count": 1, "concurrent_jobs": 1, "storage_gib": 10},
    }))

    # 1. annotator 只能数据读写，不能模型/训练写
    ann_c = TestClient(app)
    login(ann_c, "ann21a")
    assert ann_c.get(f"/api/v1/workspaces/{workspace}/datasets").status_code == 200
    assert ann_c.post(f"/api/v1/workspaces/{workspace}/models", json=model_payload(name="禁止模型")).status_code == 403
    ann_access = data(ann_c.get(f"/api/v1/workspaces/{workspace}/access"))
    assert ann_access["role"] == "annotator"
    assert "training.write" not in ann_access["actions"]

    # 2. dev_user 的空间有效配额按子配额收敛
    dev_c = TestClient(app)
    login(dev_c, "dev21a")
    dev_access = data(dev_c.get(f"/api/v1/workspaces/{workspace}/access"))
    assert dev_access["quota"] == {"gpu_count": 1, "concurrent_jobs": 1, "storage_gib": 10}

    # 3. 空间副管理员可管理普通成员，但不能提拔 admin 或改动所有者
    ws_admin_c = TestClient(app)
    login(ws_admin_c, "wsadmin21a")
    assert ws_admin_c.post(f"/api/v1/workspaces/{workspace}/members", json={"user_id": dev_user["id"], "role": "viewer"}).status_code == 200
    assert ws_admin_c.post(f"/api/v1/workspaces/{workspace}/members", json={"user_id": dev_user["id"], "role": "admin"}).status_code == 403

    # 4. 所有权转让给 wsadmin21a
    ws_list = data(admin.get("/api/v1/workspaces"))
    ws_item = next(w for w in ws_list if w["id"] == workspace)
    transferred = data(admin.post(
        f"/api/v1/workspaces/{workspace}/transfer-owner",
        headers={"If-Match": str(ws_item["revision"])},
        json={"user_id": sub_admin["id"]},
    ))
    assert transferred["owner_id"] == sub_admin["id"]


def test_workspace_admin_device_policy_and_budget_governance_summary(app, admin, workspace):
    grp = create_group(
        admin,
        name="算力自治组21A",
        allow_actions=["datasets.read", "datasets.write", "resources.read", "training.read"],
        quota={"gpu_count": 2, "concurrent_jobs": 4, "storage_gib": 50},
    )
    ws_admin = create_user(admin, account="leader21a", group_id=grp["id"])
    outsider = create_user(admin, account="outsider21a", group_id=grp["id"])
    data(admin.post(f"/api/v1/workspaces/{workspace}/members", json={"user_id": ws_admin["id"], "role": "admin"}))

    leader_c = TestClient(app)
    login(leader_c, "leader21a")

    with ExitStack() as stack:
        _, node_id, policy_path = attach(app, admin, workspace, stack, "gov-node")
        dev_id = policy_path.split("/")[5]

        # 空间管理员可读取并修改本空间设备用途和本空间成员白名单
        principals = data(leader_c.get(f"/api/v1/workspaces/{workspace}/resource-principals"))
        assert any(u["id"] == ws_admin["id"] for u in principals["users"])
        assert principals["groups"] == []

        pol = data(leader_c.get(f"/api/v1/workspaces/{workspace}/devices/{dev_id}/policy"))
        updated = data(leader_c.post(f"/api/v1/workspaces/{workspace}/devices/{dev_id}/policy", json={
            "revision": pol["revision"], "enabled": True, "purpose": "train_eval", "allow_users": [ws_admin["id"]],
        }))
        assert updated["purpose"] == "train_eval" and updated["allow_users"] == [ws_admin["id"]]

        # 不能把非本空间成员加入白名单
        bad = leader_c.post(f"/api/v1/workspaces/{workspace}/devices/{dev_id}/policy", json={
            "revision": updated["revision"], "enabled": True, "purpose": "train_eval", "allow_users": [outsider["id"]],
        })
        assert bad.status_code == 422

    # 空间总预算：平台管理员设存储预算为 0 GiB 后，上传数据集被拒绝 413
    budget = data(admin.post(f"/api/v1/admin/workspaces/{workspace}/budget", json={
        "revision": 0, "gpu_count": 2, "concurrent_jobs": 4, "storage_gib": 0,
    }))
    assert budget["storage_gib"] == 0

    ds = data(leader_c.post(f"/api/v1/workspaces/{workspace}/datasets", json={"name": "预算受限数据", "task_type": "text_classification", "description": ""}), 201)
    blocked = leader_c.post(f"/api/v1/workspaces/{workspace}/datasets/{ds['id']}/versions", files={"file": ("train.csv", io.BytesIO(b"text,label\na,pos\nb,neg\n"))})
    assert blocked.status_code == 413
    assert blocked.json()["error"]["code"] == "WORKSPACE_STORAGE_LIMIT"

    # 空间管理员可查询空间预算与成员账单汇总
    summary = data(leader_c.get(f"/api/v1/workspaces/{workspace}/governance/summary"))
    assert summary["budget"]["storage_gib"] == 0
    assert any(m["account"] == "leader21a" and m["role"] == "admin" for m in summary["members"])
