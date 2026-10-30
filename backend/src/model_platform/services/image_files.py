import csv
import io
from pathlib import PurePosixPath
import warnings
import zipfile

from PIL import Image, UnidentifiedImageError

from ..errors import Problem


def image_rows(content, max_samples):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > max_samples + 20:
                raise ValueError("文件数量超过限制")
            names = set()
            total = 0
            for item in infos:
                name = item.filename
                path = PurePosixPath(name)
                if name in names or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("压缩包路径无效")
                names.add(name)
                total += item.file_size
                if item.file_size > 8 * 1024 * 1024 or total > 64 * 1024 * 1024 or item.file_size > max(1024 * 1024, item.compress_size * 200):
                    raise ValueError("图片或解压大小超过限制")
            reader = csv.DictReader(io.StringIO(archive.read("labels.csv").decode("utf-8-sig")), strict=True)
            if reader.fieldnames != ["filename", "label"]:
                raise ValueError("labels.csv 需要 filename,label 两列")
            rows, seen = [], set()
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError("标签行无效")
                    filename, label = row["filename"], row["label"].strip()
                    if filename in seen or filename not in names or PurePosixPath(filename).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                        raise ValueError("图片引用无效或重复")
                    seen.add(filename)
                    with Image.open(io.BytesIO(archive.read(filename))) as image:
                        if image.format not in {"PNG", "JPEG"} or image.width * image.height > 4096 * 4096:
                            raise ValueError("图片格式或尺寸超限")
                        image.verify()
                    rows.append({"filename": filename, "label": label})
                    if len(rows) > max_samples:
                        raise ValueError("样本数量超过限制")
            if not rows:
                raise ValueError("没有图片样本")
            return rows
    except (ValueError, KeyError, zipfile.BadZipFile, UnicodeError, csv.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise Problem(422, "INVALID_IMAGE_DATASET", "图像数据包无效，请检查 labels.csv、图片和大小限制") from None
