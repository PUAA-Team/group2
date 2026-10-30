import hashlib
import io
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from conftest import create_group, create_user, login
from model_platform.data_models import DataOperation
from model_platform.models import Dataset, DatasetVersion, User
from model_platform.operations_runner import exclusive_runner, recover_interrupted, run_one
from model_platform.services.datasets import store_versions
from test_datasets import dataset_url
from test_jobs import prepare


def uploaded(admin, workspace, task="text_classification", content=None):
    url = dataset_url(admin, workspace, task)
    filename = {"text_classification": "data.csv", "image_classification": "data.zip", "llm_sft": "data.jsonl"}[task]
    result = admin.post(url + "/versions", files={"file": (filename, content or b"text,label\na,yes\nb,no\nc,yes\n")})
    assert result.status_code == 201, result.text
    return f"/api/v1/workspaces/{workspace}", url, result.json()["data"]


def batch(admin, base, version, **changes):
    result = admin.post(base + "/annotation-batches", json={"name": "人工复核", "version_id": version["id"],
        "labels": ["yes", "no"], "limit": 2, **changes})
    assert result.status_code == 201, result.text
    return base + "/annotation-batches/" + result.json()["data"]["id"]


def operation(admin, base, version, kind="clean", options=None):
    result = admin.post(base + "/data-operations", json={"name": "真实数据处理", "version_id": version["id"],
        "kind": kind, "options": options or {}})
    assert result.status_code == 201, result.text
    return base + "/data-operations/" + result.json()["data"]["id"]


def process(app):
    assert run_one(app.state.sessions, app.state.settings)


def test_samples_download_pagination_and_workspace_isolation(app, admin, workspace):
    base, _, version = uploaded(admin, workspace)
    path = base + f"/dataset-versions/{version['id']}"
    data = admin.get(path + "/samples?page=2&page_size=2").json()["data"]
    assert data["samples"] == [{"index": 2, "text": "c", "label": "yes"}]
    assert data["labels"] == {"yes": 2, "no": 1}
    raw = admin.get(path + "/download")
    assert hashlib.sha256(raw.content).hexdigest() == version["sha256"]
    assert "storage_key" not in admin.get(path + "/samples").text
    group = create_group(admin)
    create_user(admin, group_id=group["id"])
    with TestClient(app) as member:
        login(member, "member")
        assert member.get(path + "/samples").status_code == 404
        assert member.get(path + "/download").status_code == 404


def test_annotation_save_review_publish_and_immutable_source(admin, workspace):
    base, _, version = uploaded(admin, workspace)
    path = batch(admin, base, version)
    assert admin.post(path + "/publish").status_code == 409
    for index, value in [(0, "no"), (1, "yes")]:
        result = admin.post(path + f"/results/{index}", json={"value": value, "revision": 0, "submit": True})
        assert result.status_code == 200, result.text
        assert admin.post(path + f"/results/{index}", json={"value": value, "revision": 0}).status_code == 412
    assert admin.post(path + "/results/2", json={"value": "yes", "revision": 0}).status_code == 404
    detail = admin.get(path).json()["data"]
    assert detail["counts"]["submitted"] == 2
    assert admin.post(path + "/review", json={"indices": [0, 1], "decision": "approved", "revision": detail["revision"] - 1}).status_code == 412
    reviewed = admin.post(path + "/review", json={"indices": [0, 1], "decision": "approved", "revision": detail["revision"]})
    assert reviewed.status_code == 200, reviewed.text
    result = admin.post(path + "/publish")
    assert result.status_code == 200, result.text
    output = result.json()["data"]
    assert output["number"] == 2 and output["parent_version_id"] == version["id"]
    assert admin.post(path + "/publish").json()["data"]["id"] == output["id"]
    assert admin.post(path + "/results/0", json={"value": "yes", "revision": 1}).status_code == 409
    samples = admin.get(base + f"/dataset-versions/{output['id']}/samples").json()["data"]["samples"]
    assert [row["label"] for row in samples] == ["no", "yes", "yes"]
    assert admin.get(base + f"/dataset-versions/{version['id']}/samples").json()["data"]["samples"][0]["label"] == "yes"


def test_annotation_assignment_and_viewer_permissions(app, admin, workspace):
    base, _, version = uploaded(admin, workspace)
    group = create_group(admin)
    assigned = create_user(admin, group_id=group["id"])
    other = create_user(admin, "other", group_id=group["id"])
    viewer = create_user(admin, "viewer", group_id=group["id"])
    for user, role in [(assigned, "editor"), (other, "editor"), (viewer, "viewer")]:
        assert admin.post(base + "/members", json={"user_id": user["id"], "role": role}).status_code == 200
    path = batch(admin, base, version, assigned_to=assigned["id"])
    with TestClient(app) as member:
        login(member, "other")
        assert member.post(path + "/results/0", json={"value": "yes", "revision": 0}).status_code == 403
        login(member, "member")
        assert member.post(path + "/results/0", json={"value": "yes", "revision": 0, "submit": True}).status_code == 200
        detail = member.get(path).json()["data"]
        assert not detail["can_review"]
        assert member.post(path + "/review", json={"indices": [0], "decision": "approved", "revision": detail["revision"]}).status_code == 403
        login(member, "viewer")
        assert member.get(path).status_code == 200
        assert member.post(path + "/results/0", json={"value": "yes", "revision": 1}).status_code == 403


def test_clean_real_output_preview_publish_and_idempotency(app, admin, workspace):
    base, _, version = uploaded(admin, workspace, content=b"text,label\n a ,yes\na,yes\nb,no\n")
    path = operation(admin, base, version)
    assert admin.get(path + "/preview").status_code == 404
    process(app)
    data = admin.get(path).json()["data"]
    assert data["status"] == "review" and data["candidates"][0]["sample_count"] == 2
    assert "storage_key" not in str(data)
    assert admin.get(path + "/preview").json()["data"]["samples"][0]["text"] == "a"
    published = admin.post(path + "/publish").json()["data"]
    assert published["status"] == "published" and len(published["output_version_ids"]) == 1
    assert admin.post(path + "/publish").json()["data"]["output_version_ids"] == published["output_version_ids"]
    assert admin.get(base + f"/dataset-versions/{version['id']}/samples").json()["data"]["total"] == 3


def test_split_reproducibility_and_training_partition_guard(app, admin, workspace):
    base, payload = prepare(app, admin, workspace)
    content = b"text,label\n" + b"".join(f"sample{i},{i % 2}\n".encode() for i in range(12))
    _, _, version = uploaded(admin, workspace, content=content)
    path = operation(admin, base, version, "split")
    process(app)
    result = admin.post(path + "/publish")
    assert result.status_code == 200, result.text
    ids = result.json()["data"]["output_version_ids"]
    partitions = [admin.get(base + f"/dataset-versions/{vid}/samples").json()["data"]["samples"] for vid in ids]
    texts = [set(row["text"] for row in rows) for rows in partitions]
    assert sum(map(len, texts)) == 12 and not texts[0] & texts[1] and not texts[0] & texts[2] and not texts[1] & texts[2]
    for vid in ids[1:]:
        assert admin.post(base + "/jobs", json={**payload, "dataset_version_id": vid}).json()["error"]["code"] == "EVALUATION_PARTITION"
        assert admin.post(base + "/data-operations", json={"name": "错误增强", "version_id": vid, "kind": "augment", "options": {"methods": ["punctuation"]}}).status_code == 409
    second = operation(admin, base, version, "split")
    process(app)
    assert [admin.get(second + f"/preview?candidate={i}").json()["data"]["samples"] for i in range(3)] == partitions


def image_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("labels.csv", "filename,label\nx.png,yes\n")
        image = Image.new("RGB", (2, 1))
        image.putdata([(10, 20, 30), (100, 110, 120)])
        png = io.BytesIO()
        image.save(png, format="PNG")
        archive.writestr("x.png", png.getvalue())
    return buffer.getvalue()


def test_image_preview_and_real_flip_artifact(app, admin, workspace):
    base, _, version = uploaded(admin, workspace, "image_classification", image_zip())
    image_path = base + f"/dataset-versions/{version['id']}/images"
    assert admin.get(image_path + "/0").headers["content-type"] == "image/png"
    assert admin.get(image_path + "/1").status_code == 404
    path = operation(admin, base, version, "augment", {"methods": ["flip"]})
    process(app)
    assert admin.get(path).json()["data"]["status"] == "review"
    image = Image.open(io.BytesIO(admin.get(path + "/images/1").content))
    assert [image.getpixel((x, 0)) for x in range(2)] == [(100, 110, 120), (10, 20, 30)]
    assert admin.post(path + "/publish").json()["data"]["status"] == "published"


def test_cancel_interrupted_and_recover_preserves_review(app, admin, workspace):
    base, _, version = uploaded(admin, workspace)
    path = operation(admin, base, version)
    assert admin.post(path + "/cancel").json()["data"]["status"] == "cancelled"
    assert not run_one(app.state.sessions, app.state.settings)
    ready = operation(admin, base, version)
    process(app)
    interrupted = operation(admin, base, version)
    with app.state.sessions() as db:
        item = db.get(DataOperation, interrupted.rsplit("/", 1)[1])
        item.status = "running"
        db.commit()
    with exclusive_runner(app.state.settings):
        with pytest.raises(OSError):
            with exclusive_runner(app.state.settings):
                pass
        recover_interrupted(app.state.sessions)
    assert admin.get(interrupted).json()["data"]["status"] == "failed"
    assert admin.get(ready).json()["data"]["status"] == "review"
    assert admin.post(path + "/publish").status_code == 409


def test_candidate_integrity_failure_keeps_source_and_no_version(app, admin, workspace):
    base, url, version = uploaded(admin, workspace)
    path = operation(admin, base, version)
    process(app)
    with app.state.sessions() as db:
        item = db.get(DataOperation, path.rsplit("/", 1)[1])
        (app.state.settings.storage_dir / item.candidates[0]["storage_key"]).write_bytes(b"text,label\nchanged,no\n")
    assert admin.post(path + "/publish").status_code == 409
    assert admin.get(url + "/versions").json()["pagination"]["total"] == 1
    assert admin.get(base + f"/dataset-versions/{version['id']}/download").status_code == 200


def test_running_cancel_wins_result_and_does_not_publish(app, admin, workspace, monkeypatch):
    base, url, version = uploaded(admin, workspace)
    path = operation(admin, base, version)

    def cancelled_processor(task_type, rows, content, kind, options, check, max_samples):
        assert admin.post(path + "/cancel").status_code == 200
        check(0, len(rows))
        raise AssertionError("已取消的处理不应继续生成结果")

    monkeypatch.setattr("model_platform.operations_runner.process_data", cancelled_processor)
    process(app)
    state = admin.get(path).json()["data"]
    assert state["status"] == "cancelled" and not state["candidates"]
    assert admin.get(url + "/versions").json()["pagination"]["total"] == 1


def test_multiple_versions_rollback_cleans_only_own_files(app, admin, workspace):
    _, url, version = uploaded(admin, workspace)
    settings = app.state.settings
    before = {p for p in settings.storage_dir.rglob("*") if p.is_file()}
    with app.state.sessions() as db:
        actor = db.get(User, admin.get("/api/v1/auth/session").json()["data"]["user"]["id"])
        parent = db.get(DatasetVersion, version["id"])
        dataset = db.get(Dataset, parent.dataset_id)

        def reject(_):
            raise ValueError("test transaction failure")

        with pytest.raises(ValueError):
            store_versions(db, settings, actor, dataset, [("one.csv", b"text,label\nx,yes\n", {}),
                ("two.csv", b"text,label\ny,no\n", {})], parent=parent, finalize=reject)
    assert before == {p for p in settings.storage_dir.rglob("*") if p.is_file()}
    assert admin.get(url + "/versions").json()["pagination"]["total"] == 1


def test_instruction_output_editing(admin, workspace):
    base, _, version = uploaded(admin, workspace, "llm_sft", b'{"instruction":"classify","input":"sample","output":"old"}\n')
    path = batch(admin, base, version, labels=[], limit=1)
    assert admin.post(path + "/results/0", json={"value": "new output", "revision": 0, "submit": True}).status_code == 200
    detail = admin.get(path).json()["data"]
    assert admin.post(path + "/review", json={"indices": [0], "decision": "approved", "revision": detail["revision"]}).status_code == 200
    output = admin.post(path + "/publish").json()["data"]
    assert admin.get(base + f"/dataset-versions/{output['id']}/samples").json()["data"]["samples"][0]["output"] == "new output"
