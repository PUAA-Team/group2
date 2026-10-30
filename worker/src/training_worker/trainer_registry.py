import importlib.util


def supported_trainers():
    if not importlib.util.find_spec("torch") or not importlib.util.find_spec("safetensors"):
        return []
    result = ["text-classifier-v1"]
    if importlib.util.find_spec("PIL"):
        result.append("image-classifier-v1")
    if all(importlib.util.find_spec(name) for name in ("transformers", "peft", "accelerate")):
        result.append("qwen-lora-v1")
    return result
