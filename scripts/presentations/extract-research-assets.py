"""提取 PDF 原图及来源记录；不重绘或修改调研图片。"""
import argparse
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader


def extract(source, output, pages):
    source = source.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(source)
    records = []
    for page_number in pages:
        for index, image in enumerate(reader.pages[page_number - 1].images, 1):
            target = output / f"page-{page_number:02d}-image-{index:02d}{Path(image.name).suffix}"
            # 已提取的相同内容可以复用，不同内容禁止静默覆盖。
            if target.exists() and target.read_bytes() != image.data:
                raise FileExistsError(target)
            if not target.exists():
                target.write_bytes(image.data)
            records.append({
                "source": str(source), "page": page_number, "image": index,
                "original_name": image.name, "path": str(target),
                "sha256": hashlib.sha256(image.data).hexdigest(),
                "size": list(image.image.size),
            })
    manifest = output / "manifest.json"
    manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pages", type=int, nargs="+", required=True)
    args = parser.parse_args()
    extract(args.source, args.output, args.pages)
