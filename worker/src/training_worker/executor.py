import ctypes
import json
import os
from pathlib import Path
import subprocess
import time

from .journal import read_json, write_json
from .transfers import download, upload


def alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        try:
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Executor:
    def __init__(self, agent):
        self.agent, self.root, self.client = agent, agent.root / "executions", agent.client
        self.root.mkdir(exist_ok=True)
        self.active = {}
        for item in self.root.iterdir():
            journal = read_json(item / "journal.json", {}) if item.is_dir() else {}
            if journal and not journal.get("acknowledged"):
                self.active[item.name] = journal

    def launch(self, assignment):
        eid = assignment["execution_id"]
        if eid in self.active:
            return
        path = self.root / eid
        old = read_json(path / "journal.json", {})
        if old:
            self.active[eid] = old; return
        path.mkdir(exist_ok=True)
        # 启动前记录身份；无法确认的启动状态保留现场，绝不重新执行相同 ID。
        journal = {"assignment": assignment, "cursor": 0, "pid": None, "phase": "uncertain" if assignment.get("redelivered") else "preparing"}
        write_json(path / "journal.json", journal); self.active[eid] = journal

    def prepare(self, path, journal):
        task = journal["assignment"]; snapshot = task["snapshot"]
        spec = {**task, "run_dir": str(path), "dataset_path": None, "model_path": None}
        prefix = f"/executions/{task['execution_id']}"
        if snapshot.get("dataset_sha256"):
            spec["dataset_path"] = str(download(self.client, prefix + "/input", snapshot["dataset_sha256"], self.agent.root / "cache/objects"))
        if snapshot.get("model_sha256"):
            spec["model_path"] = str(download(self.client, prefix + "/model", snapshot["model_sha256"], self.agent.root / "cache/objects"))
        write_json(path / "spec.json", spec)
        journal["phase"] = "launching"; write_json(path / "journal.json", journal)
        environment = os.environ.copy()
        environment["CUDA_VISIBLE_DEVICES"] = task["device"]["hardware_id"].removeprefix("nvidia:") if task["device"]["kind"] == "cuda" else ""
        environment["PYTHONIOENCODING"] = "utf-8"; environment["TOKENIZERS_PARALLELISM"] = "false"
        with (path / "process.log").open("ab") as log:
            process = subprocess.Popen([self.agent.args.trainer_python, "-B", str(self.agent.args.bundle), "run", "--spec", str(path / "spec.json")],
                                       env=environment, cwd=path, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        journal.update(pid=process.pid, phase="running")
        write_json(path / "journal.json", journal)

    def tick(self):
        for eid, journal in list(self.active.items()):
            path = self.root / eid; prefix = f"/executions/{eid}"
            command = self.client.request(prefix + "/control")
            if command["finished"]:
                journal["acknowledged"] = True; write_json(path / "journal.json", journal); self.active.pop(eid); continue
            if command["stop"]:
                write_json(path / "cancel.json", {"requested_at": time.time()})
            if journal["phase"] == "preparing":
                if command["stop"]:
                    write_json(path / "result.json", {"status": "stopped", "result": {}})
                    journal["phase"] = "completed"
                else:
                    try:
                        self.prepare(path, journal)
                    except (ValueError, OSError) as error:
                        write_json(path / "result.json", {"status": "failed", "result": {}, "error": str(error)[:1000]})
                        journal["phase"] = "completed"; write_json(path / "journal.json", journal)
            if journal["phase"] in {"launching", "uncertain"}:
                # 此状态表示启动回执未落盘；需人工核查，保持租约和设备占用。
                continue
            for call in command["calls"]:
                call_dir = path / "calls"; call_dir.mkdir(exist_ok=True)
                result = read_json(call_dir / (call["id"] + ".result.json"), {})
                if result:
                    self.client.request(prefix + "/calls/" + call["id"], result)
                elif not (call_dir / (call["id"] + ".json")).exists():
                    write_json(call_dir / (call["id"] + ".json"), call["input"])
            events_file = path / "events.jsonl"
            if events_file.exists():
                lines = events_file.read_text(encoding="utf-8").splitlines()
                # 尾行未完整写入时等待下一轮。
                for line in lines[journal["cursor"]:journal["cursor"] + 100]:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        break
                    self.client.request(prefix + "/events", event)
                    journal["cursor"] += 1; write_json(path / "journal.json", journal)
            result = read_json(path / "result.json", {})
            if not result and journal["phase"] == "running" and not alive(journal["pid"]):
                result = {"status": "failed", "result": {}, "error": "训练子进程异常退出，请查看 Worker 执行日志"}
                write_json(path / "result.json", result)
            if result and (not events_file.exists() or journal["cursor"] >= len(events_file.read_text(encoding="utf-8").splitlines())):
                # 结果文件写成后仍等进程退出，避免提前释放设备。
                if alive(journal.get("pid")):
                    continue
                if result["status"] == "succeeded" and journal["assignment"]["kind"] == "train":
                    upload(self.client, eid, path / "artifact.zip")
                self.client.request(prefix + "/finish", result)
                journal["acknowledged"] = True; write_json(path / "journal.json", journal); self.active.pop(eid)
