import io
import json
import struct
import zipfile
from contextlib import ExitStack

from conftest import model_payload
from test_device_purposes import attach, claim, data


def make_weights_zip(trainer_id="text-classifier-v1", *, corrupt_header=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps({"trainer_id": trainer_id, "format_version": 1}))
        if corrupt_header:
            zf.writestr("weights.safetensors", b"not-safetensors")
        elif trainer_id == "qwen-lora-v1":
            zf.writestr("adapter_config.json", json.dumps({"peft_type": "LORA", "r": 4}))
            header = json.dumps({"w": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
            zf.writestr("adapter_model.safetensors", struct.pack("<Q", len(header)) + header + b"\x00\x00\x00\x00")
        else:
            header = json.dumps({"w": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
            zf.writestr("weights.safetensors", struct.pack("<Q", len(header)) + header + b"\x00\x00\x00\x00")
    return buf.getvalue()


def test_controlled_model_weight_upload_validation_and_service_download(app, admin, workspace):
    from sqlalchemy import select
    from model_platform.models import User, UserGroup
    with app.state.sessions() as db:
        owner = db.scalar(select(User).where(User.account == "owner"))
        group = db.get(UserGroup, owner.group_id)
        group.quota = {**group.quota, "concurrent_jobs": 4}
        db.commit()
    mdl = admin.post(f"/api/v1/workspaces/{workspace}/models", json=model_payload(name="导入文本模型")).json()["data"]
    base = f"/api/v1/workspaces/{workspace}/models/{mdl['id']}/versions/upload"

    # 非 zip / 错误 trainer / 损坏 safetensors 均拒绝
    bad_ext = admin.post(base, data={"version": "v1"}, files={"file": ("model.pkl", io.BytesIO(b"pickle"), "application/octet-stream")})
    assert bad_ext.status_code == 415

    wrong_trainer = admin.post(base, data={"version": "v1"}, files={"file": ("w.zip", io.BytesIO(make_weights_zip("image-classifier-v1")), "application/zip")})
    assert wrong_trainer.status_code == 422

    bad_header = admin.post(base, data={"version": "v1"}, files={"file": ("w.zip", io.BytesIO(make_weights_zip(corrupt_header=True)), "application/zip")})
    assert bad_header.status_code == 422

    # 合法受控权重上传成功
    raw = make_weights_zip("text-classifier-v1")
    ok = admin.post(base, data={"version": "import-v1"}, files={"file": ("weights.zip", io.BytesIO(raw), "application/zip")})
    assert ok.status_code == 201, ok.text
    ver = ok.json()["data"]
    assert ver["status"] == "available" and ver["source_ref"].startswith("upload://") and ver["size_bytes"] == len(raw)

    # 可直接部署在线服务并被 Worker 下载
    svc = data(admin.post(f"/api/v1/workspaces/{workspace}/jobs", json={
        "name": "导入权重推理服务", "kind": "service", "model_version_id": ver["id"], "device_kind": "cpu",
    }), 201)
    admin.post(f"/api/v1/workspaces/{workspace}/jobs/{svc['id']}/submit", headers={"If-Match": str(svc["revision"])})
    with ExitStack() as stack:
        worker, _, _ = attach(app, admin, workspace, stack, "权重加载节点")
        assigned = claim(worker)
        assert assigned["job_id"] == svc["id"]
        downloaded = worker.get(f"/api/worker/v1/executions/{assigned['execution_id']}/model")
        assert downloaded.status_code == 200 and downloaded.content == raw
        assert downloaded.headers["X-Content-SHA256"] == ver["sha256"]


def test_delete_uploaded_model_cleans_storage(app, admin, workspace):
    mdl = admin.post(f"/api/v1/workspaces/{workspace}/models", json=model_payload(name="待删导入模型")).json()["data"]
    ver = admin.post(f"/api/v1/workspaces/{workspace}/models/{mdl['id']}/versions/upload",
                     data={"version": "v1"}, files={"file": ("w.zip", io.BytesIO(make_weights_zip()), "application/zip")}).json()["data"]
    assert admin.post(f"/api/v1/workspaces/{workspace}/models/{mdl['id']}/archive", json={"revision": mdl["revision"], "archived": True}).status_code == 200
    assert admin.delete(f"/api/v1/workspaces/{workspace}/models/{mdl['id']}").status_code == 200
    storage_dir = app.state.settings.storage_dir / workspace / "imported-models" / f"{ver['id']}.zip"
    assert not storage_dir.exists()
