"""核对实际划分互斥、子集来源、样本数与可导入文件摘要。"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from run_public_experiments import classification_scores


def main():
    root = Path("D:/model-training-demo/public-experiments-20261029")
    report = json.loads((root / "dataset-manifest.json").read_text(encoding="utf-8"))
    sms = json.loads((root / "prepared/sms-splits.json").read_text(encoding="utf-8"))
    fashion = json.loads((root / "prepared/fashion-splits.json").read_text(encoding="utf-8"))
    checks = []
    for left, right, field in [(sms["development"], sms["test"], "content_sha256"), (fashion["fashion-development"], fashion["fashion-test"], "pixel_sha256")]:
        assert not {row[field] for row in left} & {row[field] for row in right}
        assert len({row[field] for row in left}) == len(left) and len({row[field] for row in right}) == len(right)
    checks.append("短信与图像划分均无规范化文本或相同像素交集")
    for child, parent, count in [("qwen_development", "development", 512), ("qwen_test", "test", 128)]:
        assert {row["id"] for row in sms[child]} <= {row["id"] for row in sms[parent]}
        assert len(sms[child]) == count and set(Counter(row["label"] for row in sms[child]).values()) == {count // 2}
    assert len(fashion["fashion-development"]) == 6000 and len(fashion["fashion-test"]) == 2000
    checks.append("Qwen 512/128平衡采样来自对应开发/测试集合，Fashion为6000/2000")
    for item in report["files"]:
        raw = (root / "prepared" / item["filename"]).read_bytes()
        assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        assert len(raw) <= 10 * 1024 * 1024
    checks.append("六个导入文件内容摘要一致且均在平台10MiB限制内")
    result = classification_scores(["ham", "spam"], ["ham", "invalid"], ["ham", "spam"])
    assert result["accuracy"] == 0.5 and abs(result["macro_f1"] - 0.5) < 1e-12 and result["invalid_outputs"] == 1
    checks.append("分类统计将无效输出计为错误")
    (root / "data-checks.json").write_text(json.dumps({"success": True, "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": True, "checks": checks}, ensure_ascii=False))


if __name__ == "__main__":
    main()
