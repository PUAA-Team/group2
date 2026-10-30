import csv
import hashlib
import io
import json
from pathlib import Path

from ..errors import Problem


def validate_filename(filename):
    if not filename or len(filename) > 200 or any(char in filename for char in ("/", "\\", "\x00")) or filename in {".", ".."}:
        raise Problem(422, "VALIDATION_ERROR", "文件名不能包含目录或非法字符")


def parse_samples(content: bytes, task_type: str, filename: str, max_samples: int):
    validate_filename(filename)
    suffix = Path(filename).suffix.lower()
    expected = {"text_classification": ".csv", "llm_sft": ".jsonl", "image_classification": ".zip"}.get(task_type)
    if expected is None or expected != suffix:
        raise Problem(415, "UNSUPPORTED_FORMAT", "当前任务不支持此文件格式")
    if suffix == ".zip":
        from .image_files import image_rows
        rows = image_rows(content, max_samples)
        return rows, {"format": "zip", "size_bytes": len(content), "sample_count": len(rows),
                      "sha256": hashlib.sha256(content).hexdigest(), "status": "available" if all(row["label"] for row in rows) else "needs_annotation"}
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Problem(422, "VALIDATION_ERROR", "文件必须使用 UTF-8 编码") from None
    try:
        rows = _csv_rows(text, max_samples) if suffix == ".csv" else _jsonl_rows(text, max_samples)
    except (csv.Error, json.JSONDecodeError, ValueError, RecursionError):
        raise Problem(422, "VALIDATION_ERROR", "文件内容或字段不符合模板") from None
    if not rows:
        raise Problem(422, "VALIDATION_ERROR", "文件没有有效样本")
    status = "needs_annotation" if suffix == ".csv" and any(not row["label"] for row in rows) else "available"
    return rows, {"format": suffix[1:], "size_bytes": len(content), "sample_count": len(rows),
                  "sha256": hashlib.sha256(content).hexdigest(), "status": status}


def _csv_rows(text, max_samples):
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if not reader.fieldnames or len(reader.fieldnames) != 2 or set(reader.fieldnames) != {"text", "label"}:
        raise ValueError("columns")
    rows = []
    for row in reader:
        if len(rows) >= max_samples:
            raise ValueError("too many rows")
        if None in row or any(value is None for value in row.values()) or not row["text"].strip():
            raise ValueError("row")
        rows.append({"text": row["text"], "label": row["label"].strip()})
    return rows


def _jsonl_rows(text, max_samples):
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if len(rows) >= max_samples:
            raise ValueError("too many rows")
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) - {"instruction", "input", "output"}:
            raise ValueError("fields")
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in ("instruction", "output")):
            raise ValueError("required")
        if not isinstance(row.get("input", ""), str):
            raise ValueError("input")
        rows.append({"instruction": row["instruction"], "input": row.get("input", ""), "output": row["output"]})
    return rows


def controlled_path(settings, storage_key):
    root = settings.storage_dir.resolve()
    target = (root / storage_key).resolve()
    if not target.is_relative_to(root) or target == root:
        raise Problem(409, "CONFLICT", "存储引用无效")
    return target
