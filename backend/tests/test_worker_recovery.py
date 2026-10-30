from pathlib import Path
from types import SimpleNamespace
import sys
import io
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker/src"))
from training_worker.executor import Executor
from training_worker.journal import read_json, write_json


class Client:
    def request(self, *args):
        return {"finished": False, "stop": False, "calls": []}


def agent(tmp_path):
    return SimpleNamespace(root=tmp_path, client=Client(), args=SimpleNamespace())


def test_redelivered_without_journal_is_quarantined(tmp_path):
    executor = Executor(agent(tmp_path))
    executor.launch({"execution_id": "exe_test", "redelivered": True})
    executor.tick()
    assert executor.active["exe_test"]["phase"] == "uncertain"
    assert not (tmp_path / "executions/exe_test/spec.json").exists()


def test_recovery_retains_launching_state_and_finished_ack(tmp_path):
    directory = tmp_path / "executions/exe_test"
    write_json(directory / "journal.json", {"phase": "launching", "pid": None, "cursor": 0, "assignment": {"execution_id": "exe_test"}})
    executor = Executor(agent(tmp_path)); executor.tick()
    assert executor.active["exe_test"]["phase"] == "launching"
    write_json(directory / "journal.json", {"acknowledged": True})
    assert not Executor(agent(tmp_path)).active


def test_repeating_same_join_command_reuses_local_identity(tmp_path, monkeypatch):
    import training_worker.agent as module
    registrations = []
    class FakeClient:
        def __init__(self, *args):
            pass
        def request(self, path, payload=None):
            if path == "/register":
                registrations.append(payload)
                return {"node_id": "nod-test", "next_seq": 1}
            return {}
    monkeypatch.setattr(module, "Client", FakeClient)
    monkeypatch.setattr(module, "full_probe", lambda *args: {})
    args = SimpleNamespace(state_dir=str(tmp_path), model_cache=str(tmp_path / "models"), join_code_stdin=True,
                           trainer_python="test-python", bundle=tmp_path / "test.pyz", controller="http://127.0.0.1", allow_http=True, slots=2)
    for _ in range(2):
        monkeypatch.setattr(sys, "stdin", io.StringIO("enr_test.test-code\n"))
        worker = module.Agent(args); worker.stop.set(); worker.run()
    state = read_json(tmp_path / "node-state.json")
    assert len(registrations) == 1 and state["node_id"] == "nod-test"
    assert state["credential"] and state["enrollment_fingerprint"]
    from training_worker.client import WorkerError
    class RejectedClient(FakeClient):
        def request(self, path, payload=None):
            if path == "/register":
                raise WorkerError(409, "NODE_EXISTS", "已有节点")
            return {}
    monkeypatch.setattr(module, "Client", RejectedClient)
    monkeypatch.setattr(sys, "stdin", io.StringIO("enr_other.new-code\n"))
    worker = module.Agent(args); worker.stop.set()
    with pytest.raises(WorkerError):
        worker.run()
    preserved = read_json(tmp_path / "node-state.json")
    assert preserved["credential"] == state["credential"] and preserved["node_id"] == state["node_id"]
