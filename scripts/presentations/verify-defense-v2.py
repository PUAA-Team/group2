"""核对修订版 PPT 的页数、放映范围、空备注及原生内容。"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
BANNED = ["截图来源", "X178", "原始像素提取", "不能据此声称", "来源：", "建议补充", "本页结论"]


def verify(target, manifest):
    records = json.loads(manifest.read_text(encoding="utf-8"))
    with ZipFile(target) as package:
        slides = sorted((n for n in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.search(r"slide(\d+)", n).group(1)))
        assert len(slides) == len(records), "页数与内容设计不同"
        main_pages = []
        for name, record in zip(slides, records):
            tree = ET.fromstring(package.read(name))
            visible = tree.get("show", "1") != "0"
            assert visible == record["main"], f"放映范围不符：{record['page']}"
            if visible:
                main_pages.append(record["page"])
            text = "".join(node.text or "" for node in tree.findall(".//a:t", NS))
            for term in BANNED:
                assert term not in text, f"残留制作提示：{term}"
            if record["kind"] == "table":
                assert tree.find(".//a:tbl", NS) is not None, "表格不可编辑"
            if record["kind"] in ("charts", "survey"):
                assert b"chart" in package.read(name), "缺少原生图表"
        for name in package.namelist():
            if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name):
                notes = "".join(n.text or "" for n in ET.fromstring(package.read(name)).findall(".//a:t", NS))
                assert not notes.strip(), f"备注非空：{name}"
    result = {"file": str(target), "slides": len(records), "main_pages": main_pages,
              "chapters": sum(r["kind"] == "chapter" for r in records),
              "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("revision")
    parser.add_argument("--key", choices=["research", "analysis"])
    args = parser.parse_args()
    for key, label in [("research", "需求调研"), ("analysis", "需求分析")]:
        if args.key and args.key != key:
            continue
        verify(args.workspace / f"output-{args.revision}" / f"大模型集成训练平台_{label}答辩_修订版.pptx",
               args.workspace / f"private-{args.revision}" / key / "manifest.json")
