"""合入 Word 更新的目录，正文和所有原始图片继续使用局部修订包。"""

import argparse
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as E

from build import NS, q, text, write_package


def toc_region(root):
    body = root.find(q("body"))
    field = next(n for n in root.xpath("//w:instrText", namespaces=NS) if (n.text or "").strip().startswith("TOC "))
    first = field
    while first.getparent() is not body:
        first = first.getparent()
    intro = next(n for n in body if n.tag == q("p") and text(n) == "引言")
    last = list(body).index(intro)
    if body[last - 1].xpath(".//w:sectPr", namespaces=NS):
        last -= 1
    return body, list(body).index(first), last


def style_map(data):
    root = E.fromstring(data)
    return {n.get(q("styleId")): n.find(q("name")).get(q("val")) for n in root if n.tag == q("style") and n.find(q("name")) is not None}


def finalize(raw, native, output):
    if output.exists():
        raise ValueError(f"不覆盖输出：{output}")
    with ZipFile(raw) as original, ZipFile(native) as updated:
        root = E.fromstring(original.read("word/document.xml"))
        native_root = E.fromstring(updated.read("word/document.xml"))
        body, first, last = toc_region(root)
        native_body, native_first, native_last = toc_region(native_root)
        old_styles = {name.casefold(): uid for uid, name in style_map(original.read("word/styles.xml")).items()}
        new_styles = style_map(updated.read("word/styles.xml"))
        replacements = [deepcopy(p) for p in list(native_body)[native_first:native_last]]
        if any(p.xpath(".//w:drawing|.//w:pict|.//w:sectPr", namespaces=NS) for p in replacements):
            raise ValueError("目录区域包含图片或节信息，停止合并")
        for p in replacements:
            for style in p.xpath(".//w:pStyle|.//w:rStyle", namespaces=NS):
                name = new_styles[style.get(q("val"))].casefold()
                if name not in old_styles:
                    raise ValueError(f"原模板缺少目录样式：{name}")
                style.set(q("val"), old_styles[name])
        targets = set()
        for p in replacements:
            targets.update(p.xpath(".//w:hyperlink/@w:anchor", namespaces=NS))
        existing = set(root.xpath("//w:bookmarkStart/@w:name", namespaces=NS))
        next_id = max(map(int, root.xpath("//w:bookmarkStart/@w:id", namespaces=NS)), default=0) + 1
        for name in sorted(targets - existing):
            marks = native_root.xpath("//w:bookmarkStart[@w:name=$name]", namespaces=NS, name=name)
            if len(marks) != 1:
                raise ValueError(f"原生目录目标不唯一：{name}")
            heading_text = text(marks[0].getparent())
            candidates = [p for p in list(body)[last:] if p.tag == q("p") and text(p) == heading_text]
            if len(candidates) != 1:
                raise ValueError(f"无法匹配目录标题：{heading_text}")
            p = candidates[0]
            start = E.Element(q("bookmarkStart")); start.set(q("id"), str(next_id)); start.set(q("name"), name)
            end = E.Element(q("bookmarkEnd")); end.set(q("id"), str(next_id)); next_id += 1
            p.insert(1 if p.find(q("pPr")) is not None else 0, start)
            p.append(end)
        for p in list(body)[first:last]:
            body.remove(p)
        for offset, p in enumerate(replacements):
            body.insert(first + offset, p)
        write_package(original, root, output)
        print(f"已合入{len(replacements)}段目录，{len(targets)}个目录目标；图片和正文包保留")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["raw", "native", "output"]:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    finalize(args.raw, args.native, args.output)
