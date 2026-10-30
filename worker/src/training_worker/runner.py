import json
import math
import random
import time

from .journal import read_json, write_json


class Stopped(Exception):
    pass


class Runtime:
    def __init__(self, spec):
        from pathlib import Path
        self.root = Path(spec["run_dir"]); self.sequence = 0
        self.device = spec["device"]["kind"]
        import torch
        if self.device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA 运行时不可用")
        torch.set_num_threads(2)
        seed = spec["snapshot"]["config"]["seed"]; random.seed(seed); torch.manual_seed(seed)
        if self.device == "cuda":
            torch.cuda.manual_seed_all(seed)

    def check_stop(self):
        if (self.root / "cancel.json").exists():
            raise Stopped()

    def emit(self, kind, payload):
        self.sequence += 1
        event = {"seq": self.sequence, "type": kind, "payload": payload}
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"); stream.flush()

    def log(self, text):
        self.emit("log", {"message": text})


def serve(model, runtime):
    calls = runtime.root / "calls"; calls.mkdir(exist_ok=True)
    runtime.emit("ready", {})
    while True:
        runtime.check_stop()
        for path in sorted(calls.glob("cal_*.json")):
            if path.name.endswith(".result.json") or path.with_suffix(".result.json").exists():
                continue
            try:
                result = {"status": "succeeded", "result": model.predict(read_json(path))}
            except Stopped:
                raise
            except Exception as error:
                result = {"status": "failed", "result": {"error": str(error)[:500] if isinstance(error, ValueError) else type(error).__name__}}
            write_json(path.with_suffix(".result.json"), result)
        time.sleep(0.2)


def run_job(spec_path):
    spec = read_json(spec_path); root = spec_path.parent
    try:
        runtime = Runtime(spec); runtime.emit("started", {}); runtime.check_stop()
        if spec["snapshot"]["trainer_id"] == "qwen-lora-v1":
            from .qwen import Qwen
            model = Qwen(spec, runtime)
        else:
            from .classification import Classifier
            model = Classifier(spec, runtime)
        if spec["kind"] == "service":
            serve(model, runtime)
        metrics = model.train() if spec["kind"] == "train" else model.evaluate()
        runtime.check_stop()
        result = {"status": "succeeded", "result": metrics}
    except Stopped:
        result = {"status": "stopped", "result": {}}
    except Exception as error:
        import traceback
        # 完整错误仅保留执行节点日志；页面回传受控信息。
        traceback.print_exc()
        message = str(error)[:1000] if isinstance(error, ValueError) else ("GPU 显存不足" if "out of memory" in str(error).lower() else type(error).__name__)
        result = {"status": "failed", "result": {}, "error": message}
    write_json(root / "result.json", result)
