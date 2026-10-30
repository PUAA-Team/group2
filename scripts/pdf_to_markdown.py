"""将 docs 中的 PDF 转成同目录、同名的 Markdown 文本。

默认只创建缺失的 Markdown；已存在的文件不覆盖。使用 --check 查看 PDF 与
Markdown 的修改时间，使用 --refresh 更新 PDF 较新的自动生成文件。
"""

from __future__ import annotations

import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pdfplumber


GENERATOR_MARK = "<!-- 由 scripts/pdf_to_markdown.py 自动生成；请勿直接编辑，修订请另建文档。 -->"


def pdf_paths(inputs: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for item in inputs:
        if item.is_dir():
            found.update(item.rglob("*.pdf"))
        elif item.is_file() and item.suffix.lower() == ".pdf":
            found.add(item)
        else:
            raise ValueError(f"找不到 PDF 文件或目录：{item}")
    return sorted(found)


def status(pdf: Path) -> str:
    markdown = pdf.with_suffix(".md")
    if not markdown.exists():
        return "待转换"
    if pdf.stat().st_mtime > markdown.stat().st_mtime:
        return "PDF 较新"
    return "Markdown 已是最新"


def convert(pdf: Path) -> str:
    source_link = quote(pdf.name, safe="")
    lines = [
        f"# {pdf.stem}",
        "",
        GENERATOR_MARK,
        "",
        f"> 来源：[原 PDF](<{source_link}>)。本文件保留可提取文字与原页码；图片中的文字未经过 OCR。",
        "",
    ]
    with pdfplumber.open(pdf) as document:
        for number, page in enumerate(document.pages, 1):
            lines.extend((f"## 第 {number} 页", "", f"[查看原 PDF 第 {number} 页](<{source_link}#page={number}>)", ""))
            text = (page.extract_text() or "").strip()
            if text:
                lines.extend((text, ""))
            else:
                lines.extend(("> 本页没有可提取文字，请查看原 PDF 页面。", ""))
            if page.images:
                lines.extend((f"> 本页含 {len(page.images)} 幅图片；图表和界面截图请参见原 PDF。", ""))
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("docs")], help="PDF 文件或目录，默认 docs")
    parser.add_argument("--check", action="store_true", help="只检查转换状态，不写文件")
    parser.add_argument("--refresh", action="store_true", help="仅当 PDF 较新且 Markdown 是本工具生成时更新")
    args = parser.parse_args()
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    try:
        sources = pdf_paths(args.paths)
    except ValueError as exc:
        parser.error(str(exc))
    if not sources:
        print("未找到 PDF 文件。")
        return 0

    for pdf in sources:
        target = pdf.with_suffix(".md")
        current = status(pdf)
        if args.check:
            print(f"{current}: {pdf} -> {target}")
            continue
        if target.exists():
            if current != "PDF 较新" or not args.refresh:
                print(f"跳过（{current}）：{target}")
                continue
            if GENERATOR_MARK not in target.read_text(encoding="utf-8"):
                print(f"跳过（不是自动生成文件）：{target}")
                continue
        rendered = convert(pdf)
        if target.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup = target.with_name(f"{target.name}.bak-{timestamp}")
            shutil.copy2(target, backup)
            print(f"已备份：{target} -> {backup}")
        target.write_text(rendered, encoding="utf-8")
        print(f"已转换：{pdf} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
