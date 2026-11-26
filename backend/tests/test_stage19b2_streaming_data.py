# -*- coding: utf-8 -*-
"""Stage 19B-2：训练数据流式读取与单样本/空验证集零分母防护。"""
import inspect
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker/src"))

import pytest
from PIL import Image

from training_worker.training_data import (
    image_input,
    iter_rows,
    read_rows,
    row_pixels,
    scores,
    split_rows,
)


def _text_spec(tmp_path, rows):
    path = tmp_path / "data.csv"
    path.write_text("text,label\n" + "".join(f"{text},{label}\n" for text, label in rows), encoding="utf-8")
    return {"dataset_path": str(path), "snapshot": {"task_type": "text_classification"}}


def _sft_spec(tmp_path, rows):
    path = tmp_path / "data.jsonl"
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return {"dataset_path": str(path), "snapshot": {"task_type": "llm_sft"}}


def _image_spec(tmp_path):
    path = tmp_path / "images.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("labels.csv", "filename,label\na.png,cat\nb.png,dog\n")
        for name, color in (("a.png", (255, 0, 0)), ("b.png", (0, 255, 0))):
            image = Image.new("RGB", (8, 8), color)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            archive.writestr(name, buffer.getvalue())
    return {"dataset_path": str(path), "snapshot": {"task_type": "image_classification"}}


def test_iter_rows_text_is_generator(tmp_path):
    spec = _text_spec(tmp_path, [("你好", "ham"), ("中奖了", "spam")])
    rows = iter_rows(spec)
    assert inspect.isgenerator(rows)
    assert [(row["text"], row["label"]) for row in rows] == [("你好", "ham"), ("中奖了", "spam")]


def test_iter_rows_llm_sft_skips_blank_lines(tmp_path):
    spec = _sft_spec(tmp_path, [{"instruction": "a", "output": "b"}])
    path = Path(spec["dataset_path"])
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert list(iter_rows(spec)) == [{"instruction": "a", "output": "b"}]


def test_read_rows_keeps_list_compat(tmp_path):
    spec = _text_spec(tmp_path, [("a", "x"), ("b", "y")])
    rows = read_rows(spec)
    assert isinstance(rows, list) and len(rows) == 2


def test_iter_rows_image_defers_pixel_decode(tmp_path):
    spec = _image_spec(tmp_path)
    rows = list(iter_rows(spec))
    assert [row["label"] for row in rows] == ["cat", "dog"]
    # 流式读取时不立即解码像素：行内只有原始压缩字节，没有像素列表。
    assert all("pixels" not in row and isinstance(row["image_bytes"], bytes) for row in rows)
    pixels = row_pixels(rows[0])
    assert len(pixels) == 32 * 32 * 3
    assert rows[0]["pixels"] is pixels
    assert "image_bytes" not in rows[0]
    # 第二次调用直接命中缓存，不重复解码。
    assert row_pixels(rows[0]) is pixels


def test_image_input_rejects_invalid_base64():
    with pytest.raises(ValueError, match="Base64"):
        image_input("不是图片")


def test_split_rows_single_sample_goes_to_train():
    rows = [{"instruction": "a", "output": "b"}]
    train, validation = split_rows(rows, 0.2, 42, classification=False)
    assert train == rows and validation == []
    # 单样本划分后训练侧不再出现除零：训练集非空，验证集为空。
    assert len(train) == 1 and len(validation) == 0


def test_split_rows_empty_dataset_raises():
    with pytest.raises(ValueError, match="数据集为空"):
        split_rows([], 0.2, 42, classification=False)


def test_split_rows_two_samples_still_splits():
    rows = [{"instruction": "a", "output": "b"}, {"instruction": "c", "output": "d"}]
    train, validation = split_rows(rows, 0.5, 7, classification=False)
    assert len(train) == 1 and len(validation) == 1


def test_split_rows_classification_single_class_sample_still_rejected():
    with pytest.raises(ValueError, match="至少需要两条"):
        split_rows([{"label": "x", "text": "a"}], 0.2, 42)


def test_scores_empty_validation_no_zero_division():
    result = scores(["a", "b"], [], [])
    assert result["accuracy"] == 0.0
    assert result["macro_f1"] == 0.0
    assert result["samples"] == 0
    assert result["confusion_matrix"] == [[0, 0], [0, 0]]


def test_scores_empty_labels_no_zero_division():
    result = scores([], [], [])
    assert result["accuracy"] == 0.0
    assert result["macro_f1"] == 0.0
    assert result["confusion_matrix"] == []


def test_scores_single_sample():
    result = scores(["a", "b"], [0], [0])
    assert result["accuracy"] == 1.0
    assert result["samples"] == 1
    # 类别 b 无正样本也无预测：该类 F1 按 0 计，不触发除零。
    assert result["macro_f1"] == 0.5
