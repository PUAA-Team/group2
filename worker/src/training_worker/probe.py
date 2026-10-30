import csv
import ctypes
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid

RUNTIME_CODE = r'''
import importlib.util, importlib.metadata, json, platform, sys
out={'python_version':platform.python_version(),'torch_version':None,'cuda_version':None,'cuda_available':False,'trainers':[],'packages':{},'error':None}
try:
    import torch
    out['torch_version']=torch.__version__;out['cuda_version']=torch.version.cuda
    out['cuda_available']=torch.cuda.is_available()
    if out['cuda_available']:
        torch.ones(4,device='cuda').sum().item()
    for distribution,module in [('transformers','transformers'),('peft','peft'),('accelerate','accelerate'),('safetensors','safetensors'),('Pillow','PIL')]:
        if importlib.util.find_spec(module):
            out['packages'][distribution]=importlib.metadata.version(distribution)
    sys.path.insert(0,sys.argv[1])
    try:
        from training_worker.trainer_registry import supported_trainers
        out['trainers']=supported_trainers()
        try:
            from training_worker.inference_contract import prepare_request
            out['inference_contract_version']=1
        except ImportError:
            pass
    except ImportError:
        pass
except Exception:
    out['error']='runtime_probe_failed'
print(json.dumps(out))
'''


def machine_id():
    return hashlib.sha256(f"{platform.system()}|{platform.node()}|{uuid.getnode()}".encode()).hexdigest()


def memory_mb():
    try:
        if os.name == "nt":
            class Memory(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
            value = Memory(); value.length = ctypes.sizeof(value)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
                return value.total // 1048576
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") // 1048576
    except (ValueError, OSError, AttributeError):
        return 0


def devices(fingerprint):
    result = [{"uuid": fingerprint, "kind": "cpu", "name": platform.processor() or "CPU", "memory_mb": memory_mb(), "utilization": None, "used_memory_mb": None, "driver": None}]
    errors = []
    executable = shutil.which("nvidia-smi")
    if not executable:
        return result, ["nvidia_smi_unavailable"]
    try:
        output = subprocess.run([executable, "--query-gpu=uuid,name,memory.total,utilization.gpu,memory.used,driver_version", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8, check=True)
        for row in csv.reader(output.stdout.splitlines()):
            if len(row) != 6:
                continue
            uid, name, total, utilization, used, driver = (part.strip() for part in row)
            number = lambda value: int(value) if value.isdigit() else None
            result.append({"uuid": uid, "kind": "cuda", "name": name, "memory_mb": number(total) or 0,
                           "utilization": number(utilization), "used_memory_mb": number(used), "driver": driver})
    except (OSError, subprocess.SubprocessError, ValueError):
        errors.append("nvidia_probe_failed")
    return result, errors


def full_probe(fingerprint, training_python, bundle):
    hardware, errors = devices(fingerprint)
    try:
        process = subprocess.run([training_python, "-B", "-c", RUNTIME_CODE, str(bundle)], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=60, check=True)
        runtime = json.loads(process.stdout.strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        runtime = {"error": "training_python_unavailable"}
    return {"hostname": platform.node() or "worker", "platform": platform.platform(), "cpu_count": os.cpu_count() or 1,
            "memory_mb": memory_mb(), "runtime": runtime, "devices": hardware, "errors": errors}
