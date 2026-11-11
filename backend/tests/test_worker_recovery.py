from pathlib import Path
from types import SimpleNamespace
import sys
import io
import subprocess
import time
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker/src"))
from training_worker.executor import Executor
from training_worker.journal import read_json, write_json


@pytest.mark.skipif(not Path('/proc').is_dir(), reason='仅验证Linux已退出子进程')
def test_exited_child_is_not_reported_as_running():
    from training_worker.executor import alive
    process = subprocess.Popen([sys.executable, '-c', 'pass'])
    try:
        stat = Path(f'/proc/{process.pid}/stat')
        deadline = time.monotonic() + 5
        while stat.exists() and stat.read_text().rpartition(') ')[2].split()[0] != 'Z':
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert not alive(process.pid), '已退出的子进程不能继续占用执行设备'
        assert not alive(process.pid)
    finally:
        process.wait(timeout=5)


def test_trainer_probe_requires_serialization_dependency(monkeypatch):
    from training_worker import trainer_registry
    monkeypatch.setattr(trainer_registry.importlib.util, 'find_spec', lambda name: None if name == 'numpy' else object())
    assert trainer_registry.supported_trainers() == []


@pytest.mark.parametrize('code,terminal', [('STORAGE_LIMIT', True), ('NETWORK_ERROR', False)])
def test_artifact_rejection_finishes_but_network_failure_keeps_retry(tmp_path, monkeypatch, code, terminal):
    from training_worker import executor as module
    from training_worker.client import WorkerError
    directory = tmp_path / 'executions/exe_test'
    write_json(directory / 'journal.json', {'phase': 'completed', 'pid': None, 'cursor': 0,
        'assignment': {'execution_id': 'exe_test', 'kind': 'train'}})
    write_json(directory / 'result.json', {'status': 'succeeded', 'result': {'accuracy': 0.5}})
    (directory / 'artifact.zip').write_bytes(b'fixture')
    def reject(*args): raise WorkerError(413 if terminal else 0, code, '受控传输错误')
    monkeypatch.setattr(module, 'upload', reject)
    executor = Executor(agent(tmp_path))
    if terminal:
        executor.tick()
        assert not executor.active
        assert read_json(directory / 'result.json')['status'] == 'failed'
        assert (directory / 'artifact.zip').exists()
    else:
        with pytest.raises(WorkerError): executor.tick()
        assert executor.active and read_json(directory / 'result.json')['status'] == 'succeeded'


def test_cpu_sampling_uses_counter_differences_and_keeps_initial_unknown(monkeypatch):
    from training_worker import system_metrics as module
    monkeypatch.setattr(module, '_previous', None)
    values = iter([(100, 40), (200, 60), (10, 2)])
    monkeypatch.setattr(module, 'counters', lambda: next(values))
    monkeypatch.setattr(module, 'used_memory', lambda: 123)
    assert module.sample() == (None, 123)
    assert module.sample() == (80.0, 123)
    assert module.sample() == (None, 123)


def test_runtime_failure_reports_actual_stage_without_starting_torch(tmp_path, monkeypatch):
    from training_worker import runner
    path = tmp_path / 'spec.json'; write_json(path, {})
    def failed_runtime(spec): raise ValueError('受控准备失败')
    monkeypatch.setattr(runner, 'Runtime', failed_runtime)
    runner.run_job(path)
    result = read_json(tmp_path / 'result.json')
    assert result['status'] == 'failed' and result['result']['failure_stage'] == 'preparing'


def test_long_class_labels_keep_evaluation_under_result_limit():
    from training_worker.result_limits import evaluation_result, result_bytes
    from model_platform.job_schemas import FinishInput, CallResult
    labels = [str(i).zfill(2) + '类' * 98 for i in range(32)]
    errors = [{'index': i, 'actual': labels[i % 32], 'predicted': labels[(i + 1) % 32]} for i in range(100)]
    result = evaluation_result({'labels': labels, 'confusion_matrix': [[0] * 32 for _ in range(32)]}, errors)
    assert result_bytes(result) <= 65536 and result['error_sample_count'] == 100
    assert len(result['error_samples']) < 100 and result['errors_truncated']
    FinishInput(status='succeeded', result=result)
    CallResult(status='succeeded', result={'scores': {label: 1 / 32 for label in labels}})


def test_oversized_prediction_becomes_failed_call_without_stopping_service(tmp_path, monkeypatch):
    from training_worker import runner
    from training_worker.result_limits import result_bytes
    call_dir = tmp_path / 'calls'; write_json(call_dir / 'cal_fixture.json', {'text': '合成输入'})
    class Runtime:
        root = tmp_path
        count = 0
        def emit(self, *args): pass
        def check_stop(self):
            self.count += 1
            if self.count > 1: raise runner.Stopped()
    model = SimpleNamespace(predict=lambda value: {'text': 'x' * 70000})
    monkeypatch.setattr(runner.time, 'sleep', lambda *args: None)
    with pytest.raises(runner.Stopped): runner.serve(model, Runtime())
    result = read_json(call_dir / 'cal_fixture.result.json')
    assert result['status'] == 'failed' and result_bytes(result['result']) < 65536


@pytest.mark.parametrize('code,terminal', [('FILE_NOT_READY', True), ('NETWORK_ERROR', False)])
def test_input_integrity_failure_finishes_but_network_error_retries(tmp_path, monkeypatch, code, terminal):
    from training_worker.client import WorkerError
    executor = Executor(agent(tmp_path))
    executor.launch({'execution_id': 'exe_test', 'kind': 'train'})
    def reject(*args): raise WorkerError(409 if terminal else 0, code, '受控输入错误')
    monkeypatch.setattr(executor, 'prepare', reject)
    if terminal:
        executor.tick()
        result = read_json(tmp_path / 'executions/exe_test/result.json')
        assert result['status'] == 'failed' and result['result']['failure_stage'] == 'input_transfer'
        assert not executor.active
    else:
        with pytest.raises(WorkerError): executor.tick()
        assert executor.active


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
