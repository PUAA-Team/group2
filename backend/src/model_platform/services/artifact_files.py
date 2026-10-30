import hashlib
import io
import json
import struct
import zipfile

from ..errors import Problem

MAX_ARTIFACT = 64 * 1024 * 1024


def validate_artifact(content, trainer_id):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            allowed = {"manifest.json", "weights.safetensors", "adapter_config.json", "adapter_model.safetensors"}
            if not infos or len(infos) > 4 or len({i.filename for i in infos}) != len(infos) or any(i.filename not in allowed or i.file_size > MAX_ARTIFACT for i in infos) or sum(i.file_size for i in infos) > MAX_ARTIFACT:
                raise ValueError("entries")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("trainer_id") != trainer_id or manifest.get("format_version") != 1:
                raise ValueError("manifest")
            required = {"adapter_config.json", "adapter_model.safetensors"} if trainer_id == "qwen-lora-v1" else {"weights.safetensors"}
            if not required.issubset(archive.namelist()):
                raise ValueError("weights")
            # 控制端只检查有界文件结构，模型张量由隔离的 Worker 加载。
            for name in required:
                raw = archive.read(name)
                if name.endswith(".json"):
                    config = json.loads(raw)
                    if config.get("peft_type") != "LORA" or config.get("auto_mapping") or config.get("r", 0) not in {4, 8, 16}:
                        raise ValueError("adapter config")
                else:
                    if len(raw) < 8:
                        raise ValueError("tensor")
                    length = struct.unpack("<Q", raw[:8])[0]
                    if length > min(1024 * 1024, len(raw) - 8):
                        raise ValueError("tensor header")
                    json.loads(raw[8:8 + length])
            return hashlib.sha256(content).hexdigest()
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile, struct.error, UnicodeError):
        raise Problem(422, "INVALID_ARTIFACT", "模型产物不符合安全格式") from None
