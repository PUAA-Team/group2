import base64
import csv
import io
import json
import random
import zipfile

from PIL import Image


def read_rows(spec):
    content = open(spec["dataset_path"], "rb").read()
    kind = spec["snapshot"]["task_type"]
    if kind == "text_classification":
        return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    if kind == "llm_sft":
        return [json.loads(line) for line in content.decode("utf-8-sig").splitlines() if line.strip()]
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read("labels.csv").decode("utf-8-sig"))))
        for row in rows:
            row["pixels"] = image_pixels(archive.read(row["filename"]))
        return rows


def image_pixels(raw):
    with Image.open(io.BytesIO(raw)) as image:
        if image.format not in {"PNG", "JPEG"} or image.width * image.height > 4096 * 4096:
            raise ValueError("图片格式或尺寸超限")
        image = image.convert("RGB").resize((32, 32))
        return list(image.tobytes())


def image_input(encoded):
    try:
        return image_pixels(base64.b64decode(encoded, validate=True))
    except Exception:
        raise ValueError("图片须为有效 PNG/JPEG 的 Base64 内容") from None


def split_rows(rows, ratio, seed, classification=True):
    randomizer = random.Random(seed)
    if not classification:
        shuffled = list(rows); randomizer.shuffle(shuffled)
        count = max(1, min(len(rows) - 1, round(len(rows) * ratio)))
        return shuffled[count:], shuffled[:count]
    groups = {}
    for row in rows:
        groups.setdefault(row["label"], []).append(row)
    train, validation = [], []
    for label, group in sorted(groups.items()):
        if not label or len(group) < 2:
            raise ValueError("每类至少需要两条已标注样本")
        randomizer.shuffle(group)
        count = max(1, min(len(group) - 1, round(len(group) * ratio)))
        validation.extend(group[:count]); train.extend(group[count:])
    return train, validation


def scores(labels, expected, predicted):
    matrix = [[0 for _ in labels] for _ in labels]
    for actual, result in zip(expected, predicted):
        matrix[actual][result] += 1
    f1 = []
    for index in range(len(labels)):
        tp = matrix[index][index]
        precision_den = sum(row[index] for row in matrix)
        recall_den = sum(matrix[index])
        f1.append(2 * tp / (precision_den + recall_den) if precision_den + recall_den else 0)
    return {"accuracy": sum(a == p for a, p in zip(expected, predicted)) / max(1, len(expected)),
            "macro_f1": sum(f1) / len(f1), "labels": labels, "confusion_matrix": matrix, "samples": len(expected)}
