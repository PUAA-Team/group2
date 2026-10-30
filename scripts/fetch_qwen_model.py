"""下载批准的 Qwen 公开 safetensors 快照，仅写入指定 D 盘缓存。"""
import argparse
import hashlib
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("D:/model-training-demo/worker-llm-runtime"))
    root = parser.parse_args().root.resolve()
    if os.name == "nt" and root.drive.upper() != "D:":
        raise ValueError("本机模型缓存必须在 D 盘")
    os.environ["HF_HOME"] = str(root / "cache/huggingface")
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    from huggingface_hub import HfApi, snapshot_download
    repo = "Qwen/Qwen3-0.6B"
    print("读取公开模型的固定版本…", flush=True)
    revision = "c1899de289a04d12100db370d81485cdf75e47ca"
    info = HfApi(token=False).model_info(repo, revision=revision, files_metadata=True)
    folder = Path(snapshot_download(repo_id=repo, revision=revision, token=False,
                  cache_dir=str(root / "cache/huggingface/hub"),
                  allow_patterns=["*.json", "*.safetensors", "merges.txt", "vocab.json", "*.jinja"], max_workers=2))
    files = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        checksum = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1048576), b""):
                checksum.update(chunk)
        files.append({"name": path.relative_to(folder).as_posix(), "size_bytes": path.stat().st_size, "sha256": checksum.hexdigest()})
    assert any(item["name"].endswith(".safetensors") for item in files)
    record = {"repo_id": repo, "revision": info.sha, "snapshot_dir": str(folder), "files": files,
              "size_bytes": sum(item["size_bytes"] for item in files)}
    destination = root / "qwen-model.json"
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metadata": str(destination), "revision": info.sha, "size_bytes": record["size_bytes"]}), flush=True)


if __name__ == "__main__":
    main()
