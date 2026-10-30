from pydantic import ValidationError

from ..job_schemas import InferenceConfig
from ..models import Dataset, DatasetVersion
from ..errors import Problem
from .dataset_files import controlled_path, parse_samples
from .jobs import source_job


def inference_suggestion(db, settings, workspace_id, version):
    parent = source_job(db, workspace_id, version)
    fallback = InferenceConfig().model_dump()
    if not parent or not parent.dataset_version_id:
        return fallback
    data = db.get(DatasetVersion, parent.dataset_version_id)
    dataset = db.get(Dataset, data.dataset_id) if data else None
    if not dataset or dataset.workspace_id != workspace_id or dataset.task_type != "llm_sft":
        return fallback
    path = controlled_path(settings, data.storage_key)
    if not path.is_file():
        return fallback
    try:
        rows, metadata = parse_samples(path.read_bytes(), dataset.task_type, data.filename, settings.max_samples)
    except (Problem, OSError):
        return fallback
    if metadata["sha256"] != data.sha256 or parent.snapshot.get("dataset_sha256") != data.sha256:
        return fallback
    instructions = {row["instruction"] for row in rows}
    if len(instructions) != 1:
        return fallback
    instruction = next(iter(instructions))
    if len(instruction) > 2048:
        return fallback
    labels = sorted({row["output"] for row in rows})
    try:
        return InferenceConfig(mode="label", instruction=instruction, labels=labels).model_dump()
    except ValidationError:
        return InferenceConfig(instruction=instruction).model_dump()
