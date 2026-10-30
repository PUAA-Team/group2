from collections import defaultdict
import hashlib
import io
import json
import random
import zipfile

from PIL import Image, ImageEnhance, ImageOps

from ..errors import Problem
from .data_samples import encode_rows


def process_data(task_type, rows, content, kind, options, check, max_samples):
    rng = random.Random(options["seed"])
    if kind == "clean":
        result, seen = [], set()
        image_zip = zipfile.ZipFile(io.BytesIO(content)) if task_type == "image_classification" else None
        try:
            for i, original in enumerate(rows):
                check(i, len(rows))
                row = dict(original)
                if options["trim"]:
                    row = {key: value.strip() if key != "filename" else value for key, value in row.items()}
                if "label" in row:
                    row["label"] = options["label_map"].get(row["label"], row["label"])
                    if options["drop_unlabeled"] and not row["label"]:
                        continue
                identity = (hashlib.sha256(image_zip.read(row["filename"])).hexdigest(), row["label"]) if image_zip else json.dumps(row, sort_keys=True, ensure_ascii=False)
                if options["deduplicate"] and identity in seen:
                    continue
                seen.add(identity)
                result.append(row)
        finally:
            if image_zip:
                image_zip.close()
        if not result:
            raise Problem(422, "EMPTY_RESULT", "处理后没有有效样本，请调整规则")
        return [("clean", *encode_rows(task_type, result, content))]
    if kind == "split":
        groups = defaultdict(list)
        for i, row in enumerate(rows):
            check(i, len(rows))
            if "label" in row and not row["label"]:
                raise Problem(422, "MISSING_LABEL", "划分前请完成标签")
            groups[row.get("label", "all")].append(row)
        partitions = [[], [], []]
        for group in groups.values():
            if len(group) < 3:
                raise Problem(422, "TOO_FEW_SAMPLES", "分层划分要求每类至少3条；指令样本总数至少3条")
            rng.shuffle(group)
            train = min(len(group) - 2, max(1, round(len(group) * options["train_ratio"])))
            validation = min(len(group) - train - 1, max(1, round(len(group) * options["validation_ratio"])))
            for output, part in zip(partitions, (group[:train], group[train:train + validation], group[train + validation:])):
                output.extend(part)
        return [(name, *encode_rows(task_type, output, content)) for name, output in zip(("train", "validation", "test"), partitions)]
    methods = options["methods"]
    if len(rows) * (1 + len(methods)) > max_samples:
        raise Problem(422, "TOO_MANY_SAMPLES", "增强结果超过当前样本上限")
    result, extra = [], {}
    if task_type == "text_classification":
        for i, row in enumerate(rows):
            check(i, len(rows))
            result.append(row)
            result.append({**row, "text": row["text"].rstrip("。.!！?？") + rng.choice(["。", "！", "?"])})
    else:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for i, row in enumerate(rows):
                check(i, len(rows))
                result.append(row)
                with Image.open(io.BytesIO(archive.read(row["filename"]))) as image:
                    original = image.convert("RGB")
                for method in methods:
                    if method == "flip":
                        transformed = ImageOps.mirror(original)
                    elif method == "brightness":
                        transformed = ImageEnhance.Brightness(original).enhance(rng.choice([0.85, 1.15]))
                    else:
                        pixels = bytes(max(0, min(255, value + rng.randint(-8, 8))) for value in original.tobytes())
                        transformed = Image.frombytes("RGB", original.size, pixels)
                    filename = f"aug/{i}-{method}.png"
                    while filename in archive.namelist() or filename in extra:
                        filename = "aug/" + filename
                    buffer = io.BytesIO()
                    transformed.save(buffer, format="PNG")
                    extra[filename] = buffer.getvalue()
                    result.append({"filename": filename, "label": row["label"]})
    return [("augment", *encode_rows(task_type, result, content, extra))]
