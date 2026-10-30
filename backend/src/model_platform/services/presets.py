import csv
import io
import json
import zipfile

from fastapi import UploadFile
from PIL import Image, ImageDraw
from sqlalchemy import select

from ..database import new_id
from ..models import Dataset, DatasetVersion, ModelAsset, ModelVersion
from ..permissions import workspace_access
from .common import audit, commit
from .datasets import store_version
from .jobs import BUILTINS


def preset_content(kind):
    positive = ["操作简单上手很快", "运行稳定效果很好", "文档清楚部署顺利", "界面清晰很满意", "响应迅速非常方便", "训练成功结果准确", "服务可靠值得推荐", "上传很快使用顺畅"]
    negative = ["响应太慢一直等待", "上传失败无法使用", "日志难懂错误太多", "界面混乱体验很差", "训练中断结果不好", "服务异常反复报错", "部署失败无法连接", "程序卡住速度很慢"]
    if kind == "text_classification":
        stream = io.StringIO(newline=""); writer = csv.writer(stream); writer.writerow(["text", "label"])
        for texts, label in [(positive, "正向"), (negative, "负向")]:
            writer.writerows((text, label) for text in texts)
        return "feedback.csv", stream.getvalue().encode("utf-8")
    if kind == "llm_sft":
        rows = [{"instruction": "判断反馈情感，只回答正向或负向。", "input": text, "output": label} for texts, label in [(positive[:4], "正向"), (negative[:4], "负向")] for text in texts]
        return "sentiment.jsonl", ("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n").encode()
    buffer = io.BytesIO(); labels = io.StringIO(newline=""); writer = csv.writer(labels); writer.writerow(["filename", "label"])
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for label in ("圆形", "方形"):
            for index in range(12):
                image = Image.new("RGB", (32, 32), "white"); draw = ImageDraw.Draw(image)
                margin = 3 + index % 5
                (draw.ellipse if label == "圆形" else draw.rectangle)((margin, margin, 31 - margin, 31 - margin), fill="black")
                raw = io.BytesIO(); image.save(raw, format="PNG")
                name = f"images/{'circle' if label == '圆形' else 'square'}-{index}.png"
                archive.writestr(name, raw.getvalue()); writer.writerow([name, label])
        archive.writestr("labels.csv", labels.getvalue().encode("utf-8"))
    return "shapes.zip", buffer.getvalue()


async def seed_presets(db, settings, actor, workspace_id, selected):
    workspace_access(db, actor, workspace_id, "models.write")
    workspace_access(db, actor, workspace_id, "datasets.write")
    records = []
    for kind, trainer, name, data_name in [("text_classification", "text-classifier-v1", "文本线性分类器", "反馈情感教学样本"),
                                           ("image_classification", "image-classifier-v1", "TinyCNN", "几何图形教学样本"),
                                           ("llm_sft", "qwen-lora-v1", "Qwen3-0.6B LoRA", "情感分类教学指令")]:
        if kind not in selected:
            continue
        model = db.scalar(select(ModelAsset).where(ModelAsset.workspace_id == workspace_id, ModelAsset.name == name))
        if not model:
            model = ModelAsset(id=new_id("mdl"), workspace_id=workspace_id, name=name, task_type=kind, trainer_id=trainer, source_ref=BUILTINS[trainer], description="教学预置")
            db.add(model); db.flush()
            db.add(ModelVersion(id=new_id("mvr"), model_id=model.id, version="base-v1", source_ref=BUILTINS[trainer], created_by=actor.id))
        dataset = db.scalar(select(Dataset).where(Dataset.workspace_id == workspace_id, Dataset.name == data_name))
        if not dataset:
            dataset = Dataset(id=new_id("dat"), workspace_id=workspace_id, name=data_name, task_type=kind, description="程序生成的教学样本，用于验证完整流程")
            db.add(dataset); db.flush()
        if not db.scalar(select(DatasetVersion.id).where(DatasetVersion.dataset_id == dataset.id)):
            filename, content = preset_content(kind)
            await store_version(db, settings, actor, dataset, UploadFile(io.BytesIO(content), filename=filename))
        records.append({"model_id": model.id, "dataset_id": dataset.id, "task_type": kind})
    audit(db, actor, "presets.create", workspace_id, workspace_id); commit(db)
    return records
