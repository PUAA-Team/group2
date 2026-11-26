import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from model_platform.errors import Problem
from model_platform.security import csrf_token
from model_platform.services.model_connections import validate_remote

ROOT = Path(__file__).resolve().parents[2]


def test_ssrf_validate_remote_normalization_and_ip_pinning():
    with pytest.raises(Problem):
        validate_remote("https://127.0.0.1/v1")
    with pytest.raises(Problem):
        validate_remote("https://8.8.8.8/v1?foo=bar")

    with patch("model_platform.services.model_connections.socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        pinned = validate_remote("https://api.example.com/v1/../v2/")
        assert pinned["pinned_url"] == "https://93.184.216.34:443/v1/v2/chat/completions"
        assert pinned["host"] == "api.example.com"
        assert pinned["sni_hostname"] == "api.example.com"


def test_csrf_uses_server_secret(settings):
    t1 = csrf_token("raw-session-id", settings.resolved_csrf_secret)
    t2 = csrf_token("raw-session-id", settings.resolved_csrf_secret)
    t3 = csrf_token("raw-session-id", "different-server-secret")
    assert t1 == t2
    assert t1 != t3


def test_worker_max_new_tokens_bounds_and_executor_isolation(tmp_path):
    worker_src = str(ROOT / "worker/src")
    if worker_src not in sys.path:
        sys.path.insert(0, worker_src)
    from training_worker.executor import Executor
    from training_worker.inference_contract import prepare_request

    class DummyTokenizer:
        eos_token_id = 2
        all_special_ids = [1, 2]

        def apply_chat_template(self, messages, **_kwargs):
            return [10, 11, 12]

    with pytest.raises(ValueError, match="max_new_tokens"):
        prepare_request(DummyTokenizer(), {"text": "hello", "max_new_tokens": 100000})
    with pytest.raises(ValueError, match="max_new_tokens"):
        prepare_request(DummyTokenizer(), {"text": "hello", "max_new_tokens": 0})

    ok = prepare_request(DummyTokenizer(), {"text": "hello", "max_new_tokens": 64})
    assert ok["max_new_tokens"] == 64

    agent = SimpleNamespace(root=tmp_path, client=object())
    ex = Executor(agent)
    ex.active["exe_bad"] = {"assignment": {"kind": "train"}, "phase": "running", "cursor": 0, "pid": None}
    (ex.root / "exe_bad").mkdir(parents=True)
    with patch.object(ex, "_tick_one", side_effect=KeyError("boom")):
        ex.tick()
    res = json.loads((ex.root / "exe_bad/result.json").read_text(encoding="utf-8"))
    assert res["status"] == "failed" and "KeyError" in res["error"]
