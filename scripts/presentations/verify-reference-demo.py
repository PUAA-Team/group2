"""检查补充 demo 的原生模型、表格、备注、文档链接和提取页序。"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
ROOT = Path(__file__).resolve().parents[2]


def verify(target):
    tables, diagrams = [], []
    with ZipFile(target) as package:
        slides = sorted((n for n in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.search(r"slide(\d+)", n).group(1)))
        assert len(slides) == 22, "应为22页"
        for index, name in enumerate(slides, 1):
            tree = ET.fromstring(package.read(name))
            assert tree.get("show", "1") != "0", "demo页面均可见"
            copy = "".join(node.text or "" for node in tree.findall(".//a:t", NS))
            for term in ["截图来源", "X178", "原始像素提取", "三轮原型测试", "全面赋能"]:
                assert term not in copy, term
            if tree.find(".//a:tbl", NS) is not None:
                tables.append(index)
            connectors = tree.findall(".//p:cxnSp", NS)
            if connectors:
                diagrams.append(index)
                tail_arrows = 0
                for connector in connectors:
                    head = connector.find(".//a:headEnd", NS)
                    tail = connector.find(".//a:tailEnd", NS)
                    assert head is None or head.get("type", "none") == "none", "存在反向箭头"
                    tail_arrows += int(tail is not None and tail.get("type", "none") != "none")
                assert tail_arrows >= 2, "缺少目标端箭头"
                children = list(tree.find("p:cSld/p:spTree", NS))
                background = next(i for i, child in enumerate(children)
                                  if any(el.get("name", "").replace(" ", "") == "矩形6"
                                         for el in child.findall(".//p:cNvPr", NS)))
                assert all(children.index(c) > background for c in connectors), "连线在背景下"
        for name in package.namelist():
            if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name):
                copy = "".join(n.text or "" for n in ET.fromstring(package.read(name)).findall(".//a:t", NS))
                assert not copy.strip(), "备注不应包含制作说明"
    assert diagrams == [10, 12, 13], diagrams
    assert len(tables) == 8, tables

    checked = 0
    for folder in [ROOT / "docs/参考", ROOT / "docs/需求调研+需求分析/参考对照补充样稿"]:
        for source in folder.glob("*.md"):
            for raw in re.findall(r"\]\((<[^>]+>|[^)]+)\)", source.read_text(encoding="utf-8")):
                link = unquote(raw.strip("<> ").split("#")[0])
                if not link or re.match(r"^[a-z]+:", link):
                    continue
                assert (source.parent / link).exists(), f"链接缺失：{source.name} {link}"
                checked += 1
    for source, expected in [("01-01-需求调研", 26), ("01-02-需求模型", 19)]:
        files = list((ROOT / "docs/参考/前两阶段" / source).glob("*.文字提取.md"))
        assert len(files) == 1
        pages = re.findall(r"^## 第 (\d+) 页$", files[0].read_text(encoding="utf-8"), re.M)
        assert pages == [str(n) for n in range(1, expected + 1)], "提取页序不连续"
    print(json.dumps({"slides": len(slides), "native_tables": tables, "native_diagrams": diagrams,
                      "local_links_checked": checked,
                      "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    verify(parser.parse_args().pptx)
