"""按演示顺序提取 PPTX 原生文字，供本地材料对照阅读。"""

import argparse
import posixpath
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def extract(source):
    lines = [f"# {source.stem}", "", "> 原生文字提取，图片及图示仍需核对原 PPT。", ""]
    with ZipFile(source) as archive:
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(
            archive.read("ppt/_rels/presentation.xml.rels"))}
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        for number, slide_id in enumerate(presentation.findall("p:sldIdLst/p:sldId", NS), 1):
            target = rels[slide_id.attrib[f"{{{NS['r']}}}id"]]
            filename = posixpath.normpath(posixpath.join("ppt", target))
            slide = ET.fromstring(archive.read(filename))
            lines += [f"## 第 {number} 页", ""]
            for paragraph in slide.findall(".//a:p", NS):
                content = "".join(t.text or "" for t in paragraph.findall(".//a:t", NS)).strip()
                if content:
                    lines.append(content)
            images = len(slide.findall(".//p:pic", NS))
            lines += ["", f"> 含 {images} 个图片对象。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for item in args.paths:
        sources = sorted(item.rglob("*.pptx")) if item.is_dir() else [item]
        for source in sources:
            output = source.with_suffix(".文字提取.md")
            if output.exists():
                print(f"跳过已有文字版：{output}")
                continue
            output.write_text(extract(source), encoding="utf-8")
            print(f"已提取：{output}")


if __name__ == "__main__":
    main()
