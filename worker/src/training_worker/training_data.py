import base64
import csv
import io
import json
import random
import zipfile

from PIL import Image


def iter_rows(spec):
    """按行流式读取数据集，不一次性读入整个文件。

    文本按行迭代、JSONL 按行解析；图像只流式读 labels.csv 与每张图的原始
    压缩字节，像素按需解码（见 row_pixels），避免整套图像转 Python list[int]
    驻留内存。调用方如需多次遍历或随机划分，可用 read_rows() 取列表。
    """
    path = spec["dataset_path"]
    kind = spec["snapshot"]["task_type"]
    if kind == "text_classification":
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
        return
    if kind == "llm_sft":
        with open(path, "r", encoding="utf-8-sig") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)
        return
    with zipfile.ZipFile(path) as archive:
        with io.TextIOWrapper(archive.open("labels.csv"), encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                row["image_bytes"] = archive.read(row["filename"])
                yield row


def read_rows(spec):
    return list(iter_rows(spec))


def row_pixels(row):
    """按需解码图像行像素，解码后缓存到行内并释放原始字节，避免重复解码。"""
    pixels = row.get("pixels")
    if pixels is None:
        pixels = image_pixels(row["image_bytes"])
        row["pixels"] = pixels
        row.pop("image_bytes", None)
    return pixels


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
    rows = list(rows)
    if not rows:
        raise ValueError("数据集为空，无法划分训练集与验证集")
    randomizer = random.Random(seed)
    if not classification:
        if len(rows) == 1:
            # 单样本无法同时分出训练集与验证集：全进训练集，验证集为空，
            # 训练侧以零分母保护处理空验证集，不触发除零错误。
            return rows, []
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
    labels = list(labels)
    if not labels:
        return {"accuracy": 0.0, "macro_f1": 0.0, "labels": labels, "confusion_matrix": [], "samples": len(expected)}
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
