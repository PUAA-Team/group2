import hashlib
import os
from pathlib import Path
import secrets
import signal
import sys
import threading
import time
import uuid

from .client import Client, WorkerError
from .journal import AgentLock, read_json, write_json
from .probe import devices, full_probe, machine_id


class Agent:
    def __init__(self, args):
        self.args = args
        self.root = Path(args.state_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_file = self.root / "node-state.json"
        self.stop = threading.Event()
        self.probe_thread = None
        self.probe_result = None
        self.probe_inflight_id = None
        for name, relative in {"TEMP": "temp", "TMP": "temp", "CUDA_CACHE_PATH": "cache/cuda", "TORCH_HOME": "cache/torch", "TORCH_EXTENSIONS_DIR": "cache/extensions"}.items():
            path = self.root / relative; path.mkdir(parents=True, exist_ok=True); os.environ[name] = str(path)
        model_cache = Path(args.model_cache).expanduser().resolve() if args.model_cache else self.root / "cache/huggingface"
        model_cache.mkdir(parents=True, exist_ok=True); os.environ["HF_HOME"] = str(model_cache)
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

    def run(self):
        with AgentLock(self.root):
            self.state = read_json(self.state_file, {})
            pending_file = self.root / "registration-pending.json"
            self.state.setdefault("installation_id", str(uuid.uuid4()))
            self.state.setdefault("machine_id", machine_id())
            self.state.setdefault("heartbeat_seq", 0)
            code = sys.stdin.readline().strip() if self.args.join_code_stdin else None
            if code:
                fingerprint = hashlib.sha256(code.encode()).hexdigest()
                if fingerprint not in {self.state.get("pending_enrollment"), self.state.get("enrollment_fingerprint")}:
                    pending = read_json(pending_file, {})
                    if pending.get("pending_enrollment") == fingerprint:
                        self.state = pending
                    else:
                        self.state["credential"] = secrets.token_urlsafe(48)
                        self.state["pending_enrollment"] = fingerprint
                        self.state["node_id"] = None
                        self.state["heartbeat_seq"] = 0
                        self.state.pop("heartbeat_pending", None)
            if not self.state.get("credential"):
                raise ValueError("首次运行需要接入码，请重新生成接入命令")
            self.state["trainer_python"] = self.args.trainer_python
            self.state["pid"] = os.getpid()
            # 新接入身份先暂存，注册失败不能破坏原节点的可用凭据。
            write_json(pending_file if self.state.get("pending_enrollment") and not self.state.get("node_id") else self.state_file, self.state)
            self.client = Client(self.args.controller, self.state["credential"], self.args.allow_http)
            print("正在探测硬件与训练运行时…", flush=True)
            inventory = full_probe(self.state["machine_id"], self.args.trainer_python, self.args.bundle)
            if not self.state.get("node_id"):
                if not code:
                    raise ValueError("注册尚未确认，请重新执行原接入命令")
                payload = {"protocol_version": 1, "join_code": code, "installation_id": self.state["installation_id"],
                           "machine_id": self.state["machine_id"], "credential_digest": hashlib.sha256(self.state["credential"].encode()).hexdigest(),
                           "slots": self.args.slots, "inventory": inventory}
                while True:
                    try:
                        receipt = self.client.request("/register", payload)
                        break
                    except WorkerError as error:
                        if error.status:
                            raise
                        print(error, flush=True); time.sleep(3)
                self.state["node_id"] = receipt["node_id"]
                self.state["enrollment_fingerprint"] = self.state.get("pending_enrollment")
                self.state["heartbeat_seq"] = max(self.state["heartbeat_seq"], receipt["next_seq"] - 1)
                self.state.pop("pending_enrollment", None)
                write_json(self.state_file, self.state)
                pending_file.unlink(missing_ok=True)
            else:
                self.client.request("/inventory", {"request_id": "startup", "inventory": inventory})
            print(f"Worker 已连接：{self.state['node_id']}", flush=True)
            from .executor import Executor
            executor = Executor(self)
            signal.signal(signal.SIGINT, lambda *_: self.stop.set())
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, lambda *_: self.stop.set())
            while not self.stop.is_set():
                if (self.root / "stop-request.json").exists() and not executor.active:
                    break
                try:
                    payload = self.state.get("heartbeat_pending")
                    if payload is None:
                        metrics, _ = devices(self.state["machine_id"])
                        payload = {"protocol_version": 1, "seq": self.state["heartbeat_seq"] + 1, "active_executions": list(executor.active), "metrics": metrics}
                        self.state["heartbeat_pending"] = payload
                        write_json(self.state_file, self.state)
                    receipt = self.client.request("/heartbeat", payload)
                    self.state["heartbeat_seq"] = payload["seq"]
                    self.state.pop("heartbeat_pending", None)
                    write_json(self.state_file, self.state)
                    if self.probe_result:
                        request_id, report = self.probe_result
                        try:
                            self.client.request("/inventory", {"request_id": request_id, "inventory": report})
                        except WorkerError as error:
                            if error.code != "STALE_PROBE":
                                raise
                        self.probe_result = None
                    if receipt.get("probe_request_id") and receipt["probe_request_id"] != self.probe_inflight_id and not (self.probe_thread and self.probe_thread.is_alive()):
                        request_id = receipt["probe_request_id"]
                        self.probe_inflight_id = request_id
                        def probe():
                            self.probe_result = (request_id, full_probe(self.state["machine_id"], self.args.trainer_python, self.args.bundle))
                        self.probe_thread = threading.Thread(target=probe, daemon=True); self.probe_thread.start()
                    executor.tick()
                    if not (self.root / "stop-request.json").exists() and len(executor.active) < self.args.slots:
                        assignment = self.client.request("/claim", {"known_executions": list(executor.active)})
                        if assignment:
                            executor.launch(assignment)
                except WorkerError as error:
                    print(f"Worker 通信：{error.code}", flush=True)
                    if error.status == 401:
                        break
                    if error.code == "STALE_HEARTBEAT" and error.details:
                        self.state["heartbeat_seq"] = int(error.details[0]["message"]) - 1
                        self.state.pop("heartbeat_pending", None)
                self.stop.wait(3)
            write_json(self.root / "stopped.json", {"pid": os.getpid(), "finished_at": time.time()})
            (self.root / "stop-request.json").unlink(missing_ok=True)
            print("Worker 已停止", flush=True)
