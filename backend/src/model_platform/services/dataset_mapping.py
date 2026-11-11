"""上传字段显式转换；保存与预览共用同一条严格验证路径。"""
import csv
from copy import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

from ..errors import Problem
from .dataset_files import parse_samples, validate_filename
from .image_files import validate_archive

TARGETS = {
    'text_classification': [('text', True), ('label', False)],
    'llm_sft': [('instruction', True), ('input', False), ('output', True)],
    'image_classification': [('filename', True), ('label', False)],
}
SUFFIX = {'text_classification': '.csv', 'llm_sft': '.jsonl', 'image_classification': '.zip'}


def mapping_error():
    return Problem(422, 'INVALID_COLUMN_MAPPING', '请检查文件字段、映射、必填值及样本数量')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate fields')
        result[key] = value
    return result


def decode_mapping(value):
    if value is None:
        return None
    try:
        result = json.loads(value, object_pairs_hook=unique_object)
        if not isinstance(result, dict):
            raise ValueError('mapping')
        return result
    except (ValueError, RecursionError):
        raise mapping_error() from None


def source_rows(content, task, filename, max_samples):
    validate_filename(filename)
    if task not in TARGETS or Path(filename).suffix.lower() != SUFFIX[task]:
        raise Problem(415, 'UNSUPPORTED_FORMAT', '当前任务不支持此文件格式')
    try:
        if task == 'image_classification':
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                validate_archive(archive, max_samples)
                text = archive.read('labels.csv').decode('utf-8-sig')
        else:
            text = content.decode('utf-8-sig')
        if task == 'llm_sft':
            rows, columns = [], []
            for line in text.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line, object_pairs_hook=unique_object)
                if not isinstance(row, dict):
                    raise ValueError('row')
                rows.append(row)
                for key in row:
                    if key not in columns:
                        columns.append(key)
                if len(rows) > max_samples or len(columns) > 64:
                    raise ValueError('limit')
        else:
            reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
            columns, rows = reader.fieldnames or [], []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError('row')
                rows.append(row)
                if len(rows) > max_samples:
                    raise ValueError('limit')
        if not rows or not columns or len(columns) > 64 or len(set(columns)) != len(columns):
            raise ValueError('columns')
        if any(not isinstance(key, str) or not key.strip() or len(key) > 128 or any(ord(c) < 32 for c in key) for key in columns):
            raise ValueError('field')
        return columns, rows
    except (ValueError, UnicodeError, csv.Error, KeyError, zipfile.BadZipFile, OSError, RuntimeError, RecursionError):
        raise mapping_error() from None


def inspect_columns(content, task, filename, max_samples):
    columns, rows = source_rows(content, task, filename, max_samples)
    return {'columns': columns, 'sample_count': len(rows),
        'targets': [{'name': name, 'required': required} for name, required in TARGETS[task]],
        'suggested_mapping': {name: name if name in columns else None for name, _ in TARGETS[task]},
        'source_sha256': hashlib.sha256(content).hexdigest(), 'source_size_bytes': len(content)}


def normalize_upload(content, task, filename, max_samples, mapping=None):
    if mapping is None:
        rows, metadata = parse_samples(content, task, filename, max_samples)
        return filename, content, {}, rows, metadata
    columns, original = source_rows(content, task, filename, max_samples)
    targets = dict(TARGETS[task])
    if not isinstance(mapping, dict) or set(mapping) - targets.keys():
        raise mapping_error()
    selected = []
    for key, required in targets.items():
        source = mapping.get(key)
        if source is not None and not isinstance(source, str):
            raise mapping_error()
        if required and not source or source and source not in columns:
            raise mapping_error()
        if source:
            selected.append(source)
    if len(set(selected)) != len(selected):
        raise mapping_error()
    rows = []
    for row in original:
        transformed = {}
        for key in targets:
            value = row.get(mapping[key], '') if mapping.get(key) else ''
            if not isinstance(value, str):
                raise mapping_error()
            transformed[key] = value
        rows.append(transformed)
    if task == 'llm_sft':
        normalized = ('\n'.join(json.dumps(row, ensure_ascii=False) for row in rows) + '\n').encode()
    else:
        text = io.StringIO(newline='')
        writer = csv.DictWriter(text, fieldnames=list(targets)); writer.writeheader(); writer.writerows(rows)
        normalized = text.getvalue().encode()
        if task == 'image_classification':
            output = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as target:
                for info in source.infolist():
                    # 保留条目时间和压缩方式，预览与正式上传产生相同字节；不修改正在读取的ZipInfo。
                    target.writestr(copy(info), normalized if info.filename == 'labels.csv' else source.read(info))
            normalized = output.getvalue()
    output_name = 'mapped' + SUFFIX[task]
    parsed, metadata = parse_samples(normalized, task, output_name, max_samples)
    provenance = {'operation': 'column_mapping', 'source': {'filename': filename,
        'sha256': hashlib.sha256(content).hexdigest(), 'size_bytes': len(content)},
        'columns': {key: mapping.get(key) or None for key in targets},
        'ignored_columns': [key for key in columns if key not in selected]}
    return output_name, normalized, provenance, parsed, metadata
