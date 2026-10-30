import ipaddress
import json
import os
from pathlib import Path
import subprocess

from ..compute_models import ComputeNode
from ..compute_schemas import EnrollmentInput
from ..errors import Problem
from .compute import create_enrollment
from .worker_bundle import build_bundle
from .process_state import process_alive
from .compute import lock_node, node_busy
from .common import audit, commit
from ..database import utcnow


def local_allowed(request):
    try:
        return bool(request.app.state.settings.enable_local_worker and request.client
                    and ipaddress.ip_address(request.client.host).is_loopback
                    and request.url.hostname in {"localhost", "127.0.0.1", "::1"})
    except ValueError:
        return False


def configured_runtimes(settings):
    return [{"id": key, "name": name, "python": value, "configured": Path(value).is_file()} for key, name, value in [
        ("torch", "PyTorch", settings.torch_python), ("llm", "PyTorch + Qwen LoRA", settings.llm_python)]]


def start_local_worker(db, settings, actor, payload):
    runtime = next(item for item in configured_runtimes(settings) if item["id"] == payload.runtime_id)
    if not runtime["configured"]:
        raise Problem(422, "RUNTIME_UNAVAILABLE", "选择的训练环境尚未安装")
    root = settings.runtime_dir / "local-worker"
    root.mkdir(parents=True, exist_ok=True)
    state_file = root / "node-state.json"
    existing = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    node = db.get(ComputeNode, existing.get("node_id")) if existing.get("node_id") else None
    if node and not node.revoked and node.workspace_id != payload.workspace_id:
        raise Problem(409, "CONFLICT", "本机已属于其他空间，请在节点详情调整分配")
    join_code, enrollment_id = None, None
    if not node or node.revoked:
        enrollment = EnrollmentInput(workspace_id=payload.workspace_id, name=payload.name,
                                     controller_url=settings.local_controller_url, auto_approve=True)
        receipt, join_code = create_enrollment(db, settings, actor, enrollment, local=True)
        enrollment_id = receipt["id"]
    else:
        from ..database import aware, utcnow
        if process_alive(existing.get("pid")) and node.last_seen_at and (utcnow() - aware(node.last_seen_at)).total_seconds() <= settings.node_timeout_seconds:
            return {"status": "already_running", "node_id": node.id}
        node.enabled = True
        audit(db, actor, "resources.local.start", node.id, node.workspace_id)
        commit(db)
    bundle, _ = build_bundle(settings)
    args = [runtime["python"], "-B", str(bundle), "agent", "--controller", settings.local_controller_url,
            "--state-dir", str(root), "--trainer-python", runtime["python"], "--slots", "2", "--allow-http"]
    args.extend(["--model-cache", settings.local_model_cache])
    if join_code:
        args.append("--join-code-stdin")
    (root / "stop-request.json").unlink(missing_ok=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "TEMP": str(root / "temp"),
           "TMP": str(root / "temp"), "HF_HOME": str(root / "cache" / "huggingface"), "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1"}
    (root / "temp").mkdir(exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (root / "worker.out.log").open("ab") as stdout, (root / "worker.err.log").open("ab") as stderr:
        process = subprocess.Popen(args, stdin=subprocess.PIPE if join_code else subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, env=env, creationflags=flags)
        if join_code:
            process.stdin.write((join_code + "\n").encode()); process.stdin.close()
    (root / "process.json").write_text(json.dumps({"pid": process.pid, "bundle": str(bundle), "controller": settings.local_controller_url}), encoding="utf-8")
    return {"status": "starting", "pid": process.pid, "enrollment_id": enrollment_id, "node_id": node.id if node else None}


def stop_local_worker(db, settings, actor):
    root = settings.runtime_dir / "local-worker"
    path = root / "node-state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    node = db.get(ComputeNode, state.get("node_id")) if state.get("node_id") else None
    if not node:
        return {"status": "not_running"}
    lock_node(db, node)
    if node_busy(db, node):
        raise Problem(409, "CONFLICT", "本机仍有执行，请先停止任务或服务")
    node.enabled = False
    node.revision += 1
    audit(db, actor, "resources.local.stop", node.id, node.workspace_id)
    commit(db)
    (root / "stop-request.json").write_text(json.dumps({"requested_at": utcnow().isoformat()}), encoding="utf-8")
    return {"status": "stop_requested", "node_id": node.id}
