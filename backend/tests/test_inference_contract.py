from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker/src"))


def test_deployment_contract_validates_fixed_labels():
    from model_platform.job_schemas import InferenceConfig
    value = InferenceConfig(mode="label", instruction="Classify the SMS.", labels=["ham", "spam"])
    assert value.labels == ["ham", "spam"]
    for payload in [dict(mode="label", labels=[]), dict(mode="label", labels=["ham", "ham"]),
                    dict(mode="label", labels=["ham", "bad\nlabel"]), dict(mode="label", labels=["ham", "spam"], instruction="")]:
        with pytest.raises(ValidationError):
            InferenceConfig(**payload)
    assert InferenceConfig().mode == "generate"


def test_label_token_trie_only_admits_labels_and_end():
    from training_worker.inference_contract import LabelConstraint
    tokenizer = Tokenizer()
    allowed = LabelConstraint(tokenizer, ["ham", "spam", "spammer"], prompt_length=3)
    assert set(allowed(0, [8, 8, 8])) == {1, 2}
    assert set(allowed(0, [8, 8, 8, 2])) == {3}
    assert set(allowed(0, [8, 8, 8, 2, 3])) == {4, 9}
    assert allowed(0, [8, 8, 8, 1]) == [9]
    with pytest.raises(ValueError, match="不属于"):
        allowed(0, [8, 8, 8, 7])
    with pytest.raises(ValueError):
        LabelConstraint(tokenizer, ["ham", "special"], prompt_length=3)


def test_raw_sms_receives_task_instruction_and_budget_is_checked():
    from training_worker.inference_contract import prepare_request
    tokenizer = Tokenizer()
    profile = {"mode": "label", "instruction": "Classify the SMS as ham or spam.", "labels": ["ham", "spam"]}
    request = prepare_request(tokenizer, {"text": "call me to get VIP", "max_new_tokens": 32}, profile)
    assert tokenizer.last_messages[0]["content"] == "Classify the SMS as ham or spam.\ncall me to get VIP"
    assert request["constraint"] and request["max_new_tokens"] == 3
    assert tokenizer.last_thinking is False
    with pytest.raises(ValueError, match="输出长度"):
        prepare_request(tokenizer, {"text": "hello", "max_new_tokens": 1}, profile)
    tokenizer.prompt_length = 513
    with pytest.raises(ValueError, match="输入"):
        prepare_request(tokenizer, {"text": "long"}, profile)


def test_generation_and_legacy_call_remain_open():
    from training_worker.inference_contract import prepare_request
    tokenizer = Tokenizer()
    old = prepare_request(tokenizer, {"text": "hello", "max_new_tokens": 20}, None)
    assert old["constraint"] is None and old["max_new_tokens"] == 20
    assert tokenizer.last_messages[0]["content"] == "hello"
    configured = prepare_request(tokenizer, {"text": "hello"}, {"mode": "generate", "instruction": "Translate to French.", "labels": []})
    assert configured["constraint"] is None
    assert tokenizer.last_messages[0]["content"] == "Translate to French.\nhello"


class Tokenizer:
    eos_token_id = 9
    all_special_ids = [9]
    prompt_length = 3

    def encode(self, value, add_special_tokens=False):
        return {"ham": [1], "spam": [2, 3], "spammer": [2, 3, 4], "special": [9]}[value]

    def decode(self, values, skip_special_tokens=True):
        return {(1,): "ham", (2, 3): "spam", (2, 3, 4): "spammer"}.get(tuple(values), "invalid")

    def apply_chat_template(self, messages, tokenize, add_generation_prompt, enable_thinking):
        self.last_messages, self.last_thinking = messages, enable_thinking
        return [8] * self.prompt_length


def available_qwen(app, admin, workspace):
    import json
    from model_platform.database import new_id
    from model_platform.job_models import Job
    from model_platform.models import ModelVersion
    base = f"/api/v1/workspaces/{workspace}"
    model = admin.post(base + "/models", json={"name": "Qwen分类", "task_type": "llm_sft", "trainer_id": "qwen-lora-v1", "source_ref": "Qwen/Qwen3-0.6B"}).json()["data"]
    version = admin.post(base + f"/models/{model['id']}/versions", json={"version": "base-v1", "source_ref": "Qwen/Qwen3-0.6B"}).json()["data"]
    dataset = admin.post(base + "/datasets", json={"name": "分类指令", "task_type": "llm_sft"}).json()["data"]
    content = "\n".join(json.dumps({"instruction": "Classify the SMS.", "input": text, "output": label}) for text, label in [("hi", "ham"), ("win", "spam")]).encode()
    data = admin.post(base + f"/datasets/{dataset['id']}/versions", files={"file": ("sms.jsonl", content)}).json()["data"]
    actor = admin.get("/api/v1/auth/session").json()["data"]["user"]["id"]
    with app.state.sessions() as db:
        # 仅API测试夹具使用元数据产物；不将其作为真实模型执行。
        train = Job(id=new_id("job"), workspace_id=workspace, created_by=actor, name="测试训练", kind="train", status="succeeded", model_version_id=version["id"], dataset_version_id=data["id"],
                    snapshot={"dataset_sha256": data["sha256"]}, artifact_key="fixture/artifact.zip", artifact_sha256="a" * 64)
        db.add(train); db.flush()
        output = ModelVersion(id=new_id("mvr"), model_id=model["id"], version="trained", source_ref=f"artifact://{train.id}", status="available", created_by=actor)
        db.add(output); db.flush(); train.output_model_version_id = output.id; db.commit()
        return base, output.id, data["id"]


def test_suggested_profile_is_confirmed_and_frozen_in_service(app, admin, workspace):
    base, version, _ = available_qwen(app, admin, workspace)
    model = next(model for model in admin.get(base + "/job-options").json()["data"]["models"] if model["id"] == version)
    profile = model["inference_suggestion"]
    assert profile == {"mode": "label", "instruction": "Classify the SMS.", "labels": ["ham", "spam"]}
    payload = {"name": "分类服务", "kind": "service", "model_version_id": version, "device_kind": "cuda", "config": {"inference": profile}}
    created = admin.post(base + "/jobs", json=payload)
    assert created.status_code == 201, created.text
    job = created.json()["data"]
    result = admin.post(base + f"/jobs/{job['id']}/submit", headers={"If-Match": str(job["revision"])})
    assert result.status_code == 200, result.text
    assert result.json()["data"]["snapshot"]["config"]["inference"] == profile
    invalid = {**payload, "config": {"inference": {**profile, "labels": ["ham", "ham"]}}}
    assert admin.post(base + "/jobs", json=invalid).status_code == 422


def test_unconfigured_legacy_service_remains_generation(app, admin, workspace):
    base, version, _ = available_qwen(app, admin, workspace)
    payload = {"name": "旧客户端服务", "kind": "service", "model_version_id": version, "device_kind": "cuda"}
    result = admin.post(base + "/jobs", json=payload)
    assert result.status_code == 201 and result.json()["data"]["config"]["inference"] is None


def test_old_worker_cannot_claim_contract_and_bad_result_is_not_accepted(app, admin, workspace):
    import secrets
    from fastapi.testclient import TestClient
    from conftest import create_group
    from test_compute import enrollment, registration
    base, version, _ = available_qwen(app, admin, workspace)
    group = create_group(admin)
    actor = admin.get("/api/v1/auth/session").json()["data"]["user"]
    assert admin.patch(f"/api/v1/admin/users/{actor['id']}", headers={"If-Match": str(actor["revision"])}, json={"group_id": group["id"]}).status_code == 200
    profile = {"mode": "label", "instruction": "Classify.", "labels": ["ham", "spam"]}
    draft = admin.post(base + "/jobs", json={"name": "约束服务", "kind": "service", "model_version_id": version, "device_kind": "cuda", "config": {"inference": profile}}).json()["data"]
    assert admin.post(base + f"/jobs/{draft['id']}/submit", headers={"If-Match": str(draft["revision"])}).status_code == 200
    _, code = enrollment(admin, workspace); key = secrets.token_urlsafe(32)
    payload = registration(code, key); payload["inventory"]["runtime"]["trainers"] = ["qwen-lora-v1"]
    with TestClient(app) as worker:
        assert worker.post("/api/worker/v1/register", json=payload).status_code == 200
        worker.headers["Authorization"] = "Bearer " + key
        assert worker.post("/api/worker/v1/claim", json={}).json()["data"] is None
        payload["inventory"]["runtime"]["inference_contract_version"] = 1
        assert worker.post("/api/worker/v1/inventory", json={"request_id": "startup", "inventory": payload["inventory"]}).status_code == 200
        assignment = worker.post("/api/worker/v1/claim", json={}).json()["data"]
        assert assignment and assignment["job_id"] == draft["id"]
        eid = assignment["execution_id"]
        assert worker.post(f"/api/worker/v1/executions/{eid}/events", json={"seq": 1, "type": "ready", "payload": {}}).status_code == 200
        call = admin.post(base + f"/jobs/{draft['id']}/calls", json={"text": "hello"}).json()["data"]
        invalid = {"status": "succeeded", "result": {"text": "I cannot assist with that"}}
        assert worker.post(f"/api/worker/v1/executions/{eid}/calls/{call['id']}", json=invalid).status_code == 200
        assert worker.post(f"/api/worker/v1/executions/{eid}/calls/{call['id']}", json=invalid).status_code == 200
        result = admin.get(base + f"/calls/{call['id']}").json()["data"]
        assert result["status"] == "failed" and "I cannot assist" not in str(result["result"])
        second = admin.post(base + f"/jobs/{draft['id']}/calls", json={"text": "win prize"}).json()["data"]
        valid = {"status": "succeeded", "result": {"label": "spam", "text": "spam"}}
        assert worker.post(f"/api/worker/v1/executions/{eid}/calls/{second['id']}", json=valid).status_code == 200
        assert admin.get(base + f"/calls/{second['id']}").json()["data"]["result"] == valid["result"]
