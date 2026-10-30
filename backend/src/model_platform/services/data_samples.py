from collections import Counter
import csv
import io
import json
import zipfile

from sqlalchemy import select

from ..errors import Problem
from ..models import Dataset, DatasetVersion
from .dataset_files import controlled_path, parse_samples


def source(db, workspace_id, version_id):
    result = db.execute(select(Dataset, DatasetVersion).join(DatasetVersion,
        DatasetVersion.dataset_id == Dataset.id).where(Dataset.workspace_id == workspace_id,
        DatasetVersion.id == version_id)).first()
    if result is None:
        raise Problem(404, "NOT_FOUND", "数据版本不存在")
    return result


def read_source(settings, dataset, version):
    path = controlled_path(settings, version.storage_key)
    if not path.is_file():
        raise Problem(503, "NOT_READY", "数据版本文件暂不可读")
    content = path.read_bytes()
    rows, metadata = parse_samples(content, dataset.task_type, version.filename,
                                   max(settings.max_samples, version.sample_count))
    if metadata["sha256"] != version.sha256:
        raise Problem(409, "CONFLICT", "数据版本完整性校验失败")
    return rows, content


def sample_page(settings, dataset, version, page, page_size):
    rows, _ = read_source(settings, dataset, version)
    start = (page - 1) * page_size
    labels = Counter(row.get("label", "") or "未标注" for row in rows) if dataset.task_type != "llm_sft" else {}
    return {"samples": [{"index": start + i, **row} for i, row in enumerate(rows[start:start + page_size])],
            "total": len(rows), "page": page, "page_size": page_size, "labels": dict(labels)}


def image_sample(settings, dataset, version, index):
    if dataset.task_type != "image_classification":
        raise Problem(415, "UNSUPPORTED_FORMAT", "当前数据不是图像分类")
    rows, content = read_source(settings, dataset, version)
    if index < 0 or index >= len(rows):
        raise Problem(404, "NOT_FOUND", "样本不存在")
    name = rows[index]["filename"]
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return archive.read(name), "image/png" if name.lower().endswith(".png") else "image/jpeg"


def encode_rows(task_type, rows, image_content=None, extra_images=None):
    if task_type == "llm_sft":
        return "samples.jsonl", ("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n").encode()
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["filename", "label"] if task_type == "image_classification" else ["text", "label"])
    writer.writeheader()
    writer.writerows(rows)
    if task_type != "image_classification":
        return "samples.csv", output.getvalue().encode("utf-8-sig")
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(image_content)) as source_zip, zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr("labels.csv", output.getvalue().encode("utf-8-sig"))
        for row in rows:
            name = row["filename"]
            target.writestr(name, extra_images[name] if extra_images and name in extra_images else source_zip.read(name))
    return "samples.zip", result.getvalue()
