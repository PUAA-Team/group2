import io
from fastapi.testclient import TestClient

from conftest import PASSWORD, create_group, create_user, login, model_payload


def test_self_registration_respects_platform_setting_and_default_group(app, admin):
    with TestClient(app) as anon:
        denied = anon.post("/api/v1/auth/register", json={
            "account": "selfuser",
            "display_name": "自助用户",
            "password": PASSWORD,
        })
        assert denied.status_code == 409

    group = create_group(admin, name="开放注册默认组")
    settings = admin.get("/api/v1/admin/settings").json()["data"]
    updated = admin.patch("/api/v1/admin/settings", headers={"If-Match": str(settings["revision"])}, json={
        "platform_name": settings["platform_name"],
        "invitations_enabled": settings["invitations_enabled"],
        "self_registration_enabled": True,
        "default_group_id": group["id"],
        "max_upload_mib": settings["max_upload_mib"],
        "max_samples": settings["max_samples"],
        "global_concurrent_jobs": settings["global_concurrent_jobs"],
    })
    assert updated.status_code == 200
    assert updated.json()["data"]["self_registration_enabled"] is True

    with TestClient(app) as anon:
        info = anon.get("/api/v1/platform-info").json()["data"]
        assert info["self_registration_enabled"] is True
        reg = anon.post("/api/v1/auth/register", json={
            "account": "selfuser",
            "display_name": "自助用户",
            "password": PASSWORD,
        })
        assert reg.status_code == 201
        login(anon, "selfuser")
        assert anon.get("/api/v1/auth/session").json()["data"]["user"]["group_id"] == group["id"]


def test_workspace_invites_direct_and_approval_flow(app, admin, workspace):
    group = create_group(admin, name="成员组")
    u1 = create_user(admin, account="join_direct", group_id=group["id"])
    u2 = create_user(admin, account="join_review", group_id=group["id"])

    direct_inv = admin.post(f"/api/v1/workspaces/{workspace}/invites", json={
        "role": "viewer", "require_approval": False, "days": 7, "max_uses": 1,
    })
    assert direct_inv.status_code == 201
    direct_code = direct_inv.json()["data"]["code"]

    review_inv = admin.post(f"/api/v1/workspaces/{workspace}/invites", json={
        "role": "editor", "require_approval": True, "days": 7,
    })
    assert review_inv.status_code == 201
    review_code = review_inv.json()["data"]["code"]
    review_inv_id = review_inv.json()["data"]["id"]

    with TestClient(app) as c1:
        login(c1, u1["account"])
        res1 = c1.post("/api/v1/workspaces/join", json={"code": direct_code})
        assert res1.status_code == 200 and res1.json()["data"]["status"] == "joined"

    with TestClient(app) as c2:
        login(c2, u2["account"])
        # direct_inv max_uses=1 已耗尽
        assert c2.post("/api/v1/workspaces/join", json={"code": direct_code}).status_code == 409
        res2 = c2.post("/api/v1/workspaces/join", json={"code": review_code})
        assert res2.status_code == 200 and res2.json()["data"]["status"] == "pending"
        req_id = res2.json()["data"]["request_id"]

    # 非成员尚未加入前不可见空间，批准后可见
    reqs = admin.get(f"/api/v1/workspaces/{workspace}/join-requests").json()["data"]
    assert any(item["id"] == req_id and item["status"] == "pending" for item in reqs)
    approved = admin.post(f"/api/v1/workspaces/{workspace}/join-requests/{req_id}/review", json={"decision": "approve"})
    assert approved.status_code == 200 and approved.json()["data"]["status"] == "approved"

    with TestClient(app) as c2:
        login(c2, u2["account"])
        assert c2.get(f"/api/v1/workspaces/{workspace}/access").status_code == 200

    # 撤销邀请后不可再使用
    assert admin.post(f"/api/v1/workspaces/{workspace}/invites/{review_inv_id}/revoke").status_code == 200
    u3 = create_user(admin, account="join_revoked", group_id=group["id"])
    with TestClient(app) as c3:
        login(c3, u3["account"])
        assert c3.post("/api/v1/workspaces/join", json={"code": review_code}).status_code == 422


def test_workspace_delete_requires_clearing_assets_and_projects(app, admin):
    ws = admin.post("/api/v1/workspaces", json={"name": "待清理空间"}).json()["data"]
    ws_id = ws["id"]

    prj = admin.post(f"/api/v1/workspaces/{ws_id}/projects", json={"name": "临时项目"}).json()["data"]
    mdl = admin.post(f"/api/v1/workspaces/{ws_id}/models", json=model_payload()).json()["data"]
    ds = admin.post(f"/api/v1/workspaces/{ws_id}/datasets", json={"name": "临时数据", "task_type": "text_classification"}).json()["data"]
    assert admin.post(f"/api/v1/workspaces/{ws_id}/datasets/{ds['id']}/versions",
                      files={"file": ("sample.csv", io.BytesIO("text,label\n好,正向\n坏,负向\n".encode("utf-8")), "text/csv")}).status_code == 201

    # 未清空时拒绝删除空间
    blocked = admin.delete(f"/api/v1/workspaces/{ws_id}", params={"confirm_name": "待清理空间"}, headers={"If-Match": str(ws["revision"])})
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "WORKSPACE_NOT_EMPTY"

    # 未归档时拒绝删除项目/模型/数据集
    assert admin.delete(f"/api/v1/workspaces/{ws_id}/projects/{prj['id']}").status_code == 409
    assert admin.delete(f"/api/v1/workspaces/{ws_id}/models/{mdl['id']}").status_code == 409
    assert admin.delete(f"/api/v1/workspaces/{ws_id}/datasets/{ds['id']}").status_code == 409

    # 归档并逐个清理
    assert admin.post(f"/api/v1/workspaces/{ws_id}/projects/{prj['id']}/archive", json={"archived": True}, headers={"If-Match": str(prj["revision"])}).status_code == 200
    assert admin.delete(f"/api/v1/workspaces/{ws_id}/projects/{prj['id']}").status_code == 200
    assert admin.post(f"/api/v1/workspaces/{ws_id}/models/{mdl['id']}/archive", json={"revision": mdl["revision"], "archived": True}).status_code == 200
    assert admin.delete(f"/api/v1/workspaces/{ws_id}/models/{mdl['id']}").status_code == 200
    ds_latest = admin.get(f"/api/v1/workspaces/{ws_id}/datasets/{ds['id']}").json()["data"]
    assert admin.post(f"/api/v1/workspaces/{ws_id}/datasets/{ds['id']}/archive", json={"revision": ds_latest["revision"], "archived": True}).status_code == 200
    assert admin.delete(f"/api/v1/workspaces/{ws_id}/datasets/{ds['id']}").status_code == 200

    # 确认名称不匹配拒绝；匹配后删除成功
    assert admin.delete(f"/api/v1/workspaces/{ws_id}", params={"confirm_name": "错误名称"}, headers={"If-Match": str(ws["revision"])}).status_code == 422
    deleted = admin.delete(f"/api/v1/workspaces/{ws_id}", params={"confirm_name": "待清理空间"}, headers={"If-Match": str(ws["revision"])})
    assert deleted.status_code == 200 and deleted.json()["data"]["deleted"] is True
    assert all(item["id"] != ws_id for item in admin.get("/api/v1/workspaces").json()["data"])
