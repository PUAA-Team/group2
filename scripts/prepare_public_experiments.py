"""下载公开数据，固定划分并生成平台可导入文件；运行文件仅存 D 盘。"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import random
import re
import struct
import time
import unicodedata
import urllib.request
import zipfile

from PIL import Image

SMS_URL = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
FASHION_URL = "https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/"
FASHION_FILES = {"train-images-idx3-ubyte.gz": "8d4fb7e6c68d591d4c3dfef9ec88bf0d", "train-labels-idx1-ubyte.gz": "25c81989df183df01b3e8a0aad5dffbe",
                 "t10k-images-idx3-ubyte.gz": "bef4ecab320f06d8554ea6380940ec79", "t10k-labels-idx1-ubyte.gz": "bb300cfdad3c16e7a12a480ee83cd310"}
LABELS = ["T-shirt", "Trouser", "Pullover", "Dress", "Coat", "Sandal", "Shirt", "Sneaker", "Bag", "Ankle-boot"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def download(url, path, md5=None):
    if not path.exists():
        staged = path.with_suffix(path.suffix + ".download")
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "ModelPlatform-Research/1.0"})
                # UCI本次已验证直连，避免现有请求代理的TLS错误；不修改环境或系统代理。
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if "archive.ics.uci.edu/" in url else urllib.request.build_opener()
                with opener.open(request, timeout=45) as response, staged.open("wb") as stream:
                    size = 0
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > 40 * 1024 * 1024:
                            raise ValueError("公开数据文件超过预定大小")
                        stream.write(chunk)
                staged.replace(path); break
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(2)
    content = path.read_bytes()
    if md5 and hashlib.md5(content, usedforsecurity=False).hexdigest() != md5:
        raise ValueError("公开文件MD5与作者公布值不符: " + path.name)
    return {"url": url, "filename": path.name, "bytes": len(content), "sha256": sha(content), "official_md5": md5}


def normal(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def save_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["text", "label"]); writer.writeheader()
        writer.writerows({"text": row["text"], "label": row["label"]} for row in rows)


def prepare_sms(root):
    raw = root / "raw/sms.zip"; source = download(SMS_URL, raw)
    with zipfile.ZipFile(raw) as archive:
        lines = archive.read("SMSSpamCollection").decode("utf-8-sig").splitlines()
        (root / "raw/sms-readme.txt").write_bytes(archive.read("readme"))
    groups = defaultdict(list); malformed = 0
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if "\t" not in line or line.split("\t", 1)[0] not in {"ham", "spam"}:
            malformed += 1; continue
        label, text = line.split("\t", 1)
        key = normal(text)
        groups[key].append({"text": text.strip(), "label": label, "id": f"sms-{index + 1}", "content_sha256": sha(key.encode())})
    conflicts = [key for key, rows in groups.items() if len({row["label"] for row in rows}) > 1]
    rows = [values[0] for key, values in groups.items() if key not in set(conflicts)]
    training, testing = [], []; generator = random.Random(42)
    for label in ["ham", "spam"]:
        items = sorted((row for row in rows if row["label"] == label), key=lambda row: row["id"])
        generator.shuffle(items); count = round(len(items) * 0.2)
        testing.extend(items[:count]); training.extend(items[count:])
    assert not {row["content_sha256"] for row in training} & {row["content_sha256"] for row in testing}
    save_csv(root / "prepared/sms-development.csv", training); save_csv(root / "prepared/sms-test.csv", testing)
    instruction = "Classify the SMS as ham or spam. Reply with exactly ham or spam."
    llm_train, llm_test = [], []
    for label in ["ham", "spam"]:
        development = [row for row in training if row["label"] == label]
        held_out = [row for row in testing if row["label"] == label]
        if len(development) < 256 or len(held_out) < 64:
            raise ValueError("实际数据量不足以完成计划中的平衡采样")
        llm_train.extend(development[:256]); llm_test.extend(held_out[:64])
    for name, items in [("qwen-sms-development", llm_train), ("qwen-sms-test", llm_test)]:
        with (root / f"prepared/{name}.jsonl").open("w", encoding="utf-8") as stream:
            for row in items:
                stream.write(json.dumps({"instruction": instruction, "input": row["text"], "output": row["label"]}, ensure_ascii=False) + "\n")
    (root / "prepared/sms-splits.json").write_text(json.dumps({"development": training, "test": testing, "qwen_development": llm_train, "qwen_test": llm_test}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"source": source, "license": "CC BY 4.0", "attribution": "Almeida, T. & Hidalgo, J. (2011). SMS Spam Collection. UCI. DOI:10.24432/C5CC84",
            "raw_lines": len(lines), "malformed_lines": malformed, "duplicate_rows": sum(len(items) - 1 for items in groups.values()), "conflicting_groups_removed": len(conflicts),
            "development": dict(Counter(row["label"] for row in training)), "test": dict(Counter(row["label"] for row in testing)), "qwen_development": len(llm_train), "qwen_test": len(llm_test), "cross_split_overlap": 0}


def prepare_fashion(root):
    sources = [download(FASHION_URL + name, root / "raw" / name, digest) for name, digest in FASHION_FILES.items()]
    download("https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/LICENSE", root / "raw/Fashion-MNIST-LICENSE.txt")
    seen = set(); counts = {}; manifest = {}
    for prefix, target, name in [("train", 600, "fashion-development"), ("t10k", 200, "fashion-test")]:
        pixels = gzip.decompress((root / f"raw/{prefix}-images-idx3-ubyte.gz").read_bytes())
        labels = gzip.decompress((root / f"raw/{prefix}-labels-idx1-ubyte.gz").read_bytes())
        magic, count, height, width = struct.unpack(">IIII", pixels[:16]); label_magic, label_count = struct.unpack(">II", labels[:8])
        if (magic, label_magic, height, width, label_count) != (2051, 2049, 28, 28, count) or len(pixels) != 16 + count * 784:
            raise ValueError("IDX格式异常")
        candidates = list(range(count)); random.Random(42).shuffle(candidates)
        selected = []; per_label = Counter(); removed = 0
        with zipfile.ZipFile(root / f"prepared/{name}.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            listing = io.StringIO(newline=""); writer = csv.writer(listing); writer.writerow(["filename", "label"])
            for index in candidates:
                label = labels[8 + index]
                if per_label[label] >= target:
                    continue
                raw = pixels[16 + index * 784:16 + (index + 1) * 784]; fingerprint = sha(raw)
                if fingerprint in seen:
                    removed += 1; continue
                seen.add(fingerprint); per_label[label] += 1
                filename = f"images/{prefix}-{index}.png"
                buffer = io.BytesIO(); Image.frombytes("L", (28, 28), raw).save(buffer, format="PNG")
                entry = zipfile.ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0)); entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, buffer.getvalue()); writer.writerow([filename, LABELS[label]])
                selected.append({"id": f"{prefix}-{index}", "label": LABELS[label], "pixel_sha256": fingerprint})
                if sum(per_label.values()) == target * 10:
                    break
            if min(per_label.values()) != target or len(per_label) != 10:
                raise ValueError("去重后Fashion样本数量不足")
            entry = zipfile.ZipInfo("labels.csv", date_time=(2026, 1, 1, 0, 0, 0)); entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, listing.getvalue())
        manifest[name] = selected
        counts[name] = {"samples": len(selected), "per_class": {LABELS[key]: value for key, value in sorted(per_label.items())}, "duplicates_skipped": removed}
    assert not {row["pixel_sha256"] for row in manifest["fashion-development"]} & {row["pixel_sha256"] for row in manifest["fashion-test"]}
    (root / "prepared/fashion-splits.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"sources": sources, "license": "MIT", "attribution": "Xiao, H., Rasul, K. & Vollgraf, R. (2017). Fashion-MNIST. Zalando SE.", "counts": counts, "cross_split_overlap": 0}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path("D:/model-training-demo/public-experiments-20261029"))
    root = parser.parse_args().root.resolve()
    if not root.is_relative_to(Path("D:/model-training-demo").resolve()):
        raise ValueError("实验原始数据只能放D盘项目目录")
    (root / "raw").mkdir(parents=True, exist_ok=True); (root / "prepared").mkdir(exist_ok=True)
    report = {"seed": 42}
    print("准备SMS公开短信…", flush=True); report["sms"] = prepare_sms(root)
    print("准备Fashion-MNIST公开图像…", flush=True); report["fashion"] = prepare_fashion(root)
    report["files"] = [{"filename": path.name, "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())} for path in sorted((root / "prepared").iterdir()) if path.suffix in {".csv", ".jsonl", ".zip"}]
    (root / "dataset-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sms": report["sms"], "fashion_counts": report["fashion"]["counts"], "prepared": report["files"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
