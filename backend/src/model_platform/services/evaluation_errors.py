from ..errors import Problem
from ..models import Dataset, DatasetVersion
from ..permissions import workspace_access
from .data_samples import read_source
from .jobs import get_job


def evaluation_source(db, job):
    version = db.get(DatasetVersion, job.dataset_version_id)
    dataset = db.get(Dataset, version.dataset_id) if version else None
    if not dataset or dataset.workspace_id != job.workspace_id or version.sha256 != job.snapshot.get('dataset_sha256') or dataset.task_type != job.snapshot.get('task_type'):
        raise Problem(409, 'INVALID_SOURCE', '评估数据与执行快照不一致')
    return dataset, version


def validate_errors(db, settings, job, result):
    if "error_samples" not in result:
        return
    errors, labels = result["error_samples"], result.get("labels")
    if job.kind != "evaluate" or job.snapshot.get("task_type") not in {"text_classification", "image_classification"}:
        raise Problem(422, "INVALID_ERRORS", "错误样本仅适用于分类评估")
    if not isinstance(errors, list) or len(errors) > 100 or not isinstance(labels, list) or not 2 <= len(labels) <= 32 or any(not isinstance(label, str) for label in labels):
        raise Problem(422, "INVALID_ERRORS", "错误样本或标签列表无效")
    dataset, version = evaluation_source(db, job)
    rows, _ = read_source(settings, dataset, version)
    seen = set()
    for item in errors:
        if not isinstance(item, dict) or set(item) != {"index", "actual", "predicted"}:
            raise Problem(422, "INVALID_ERRORS", "错误样本字段无效")
        index = item["index"]
        if type(index) is not int or index in seen or not 0 <= index < len(rows):
            raise Problem(422, "INVALID_ERRORS", "错误样本序号无效")
        if item["actual"] != rows[index]["label"] or item["predicted"] not in labels or item["actual"] == item["predicted"]:
            raise Problem(422, "INVALID_ERRORS", "错误样本标签与源数据不一致")
        seen.add(index)
    count = result.get("error_sample_count")
    if type(count) is not int or not len(errors) <= count <= len(rows):
        raise Problem(422, "INVALID_ERRORS", "错误样本总数无效")


def error_samples(db, settings, actor, workspace_id, job_id, page, page_size):
    job = get_job(db, actor, workspace_id, job_id)
    workspace_access(db, actor, workspace_id, "datasets.read")
    if job.kind != "evaluate" or job.status != "succeeded":
        raise Problem(409, "EVALUATION_NOT_READY", "请选择已完成的评估")
    errors = job.result.get("error_samples")
    if errors is None:
        return {"supported": False, "job_id": job.id, "samples": []}
    dataset, version = evaluation_source(db, job)
    rows, _ = read_source(settings, dataset, version)
    selected = errors[(page - 1) * page_size:page * page_size]
    return {"supported": True, "job_id": job.id, "version_id": version.id, "task_type": dataset.task_type,
            "dataset_id": dataset.id, "error_sample_count": job.result.get("error_sample_count"),
            "reported_count": len(errors), "truncated": bool(job.result.get("errors_truncated")),
            "samples": [{**item, "source": rows[item["index"]]} for item in selected]}
