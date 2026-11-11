"""有界元数据报告；不把原样本、凭据和日志正文带入导出。"""
import csv
import io
import math

from ..errors import Problem
from ..database import aware
from ..models import Dataset, DatasetVersion, ModelAsset, ModelVersion
from .administration_queries import global_catalog
from .common import audit, commit
from .jobs import get_job

MAX_AUDIT_ROWS = 10000
METRICS = ('accuracy', 'macro_f1', 'loss', 'validation_loss', 'perplexity', 'samples', 'response_tokens')


def safe_cell(value):
    if value is None:
        return ''
    if isinstance(value, str) and value.lstrip(' \t\r\n\ufeff').startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def csv_bytes(rows):
    output = io.StringIO(newline='')
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerows([[safe_cell(value) for value in row] for row in rows])
    return output.getvalue().encode('utf-8-sig')


def audit_csv(db, actor, q, space, status, filters):
    rows, pagination = global_catalog(db, 'audit', q, space, status, None, 1, MAX_AUDIT_ROWS + 1, [], filters)
    if pagination['total'] > MAX_AUDIT_ROWS:
        raise Problem(422, 'EXPORT_TOO_LARGE', '导出超过10000条，请缩小筛选范围')
    header = ['时间', '操作', '操作者', '工作空间', '目标', '结果', '错误码', '请求编号']
    columns = ('created_at', 'action', 'actor_name', 'workspace_name', 'target_id', 'result', 'error_code', 'request_id')
    content = csv_bytes([header, *[[row.get(key) for key in columns] for row in rows]])
    audit(db, actor, 'audit.export', 'audit', space or None); commit(db)
    return content


def classification_metrics(labels, matrix):
    if not isinstance(labels, list) or not 2 <= len(labels) <= 32 or any(not isinstance(label, str) for label in labels):
        return None
    if not isinstance(matrix, list) or len(matrix) != len(labels) or any(not isinstance(row, list)
            or len(row) != len(labels) or any(type(value) is not int or value < 0 for value in row) for row in matrix):
        return None
    values = []
    for index, label in enumerate(labels):
        actual, predicted, tp = sum(matrix[index]), sum(row[index] for row in matrix), matrix[index][index]
        values.append({'label': label, 'precision': tp / predicted if predicted else None,
            'recall': tp / actual if actual else None, 'f1': 2 * tp / (actual + predicted) if actual + predicted else None,
            'support': actual})
    return values


def evaluation_summary(db, actor, workspace_id, job_id):
    job = get_job(db, actor, workspace_id, job_id)
    if job.kind != 'evaluate' or job.status != 'succeeded':
        raise Problem(409, 'EVALUATION_NOT_READY', '请选择已完成的评估')
    version = db.get(ModelVersion, job.model_version_id)
    model = db.get(ModelAsset, version.model_id) if version else None
    data = db.get(DatasetVersion, job.dataset_version_id)
    dataset = db.get(Dataset, data.dataset_id) if data else None
    if not model or not dataset or model.workspace_id != workspace_id or dataset.workspace_id != workspace_id:
        raise Problem(409, 'INVALID_SOURCE', '评估版本无法核对')
    if job.snapshot.get('dataset_sha256') != data.sha256:
        raise Problem(409, 'INVALID_SOURCE', '评估数据摘要与快照不一致')
    result = job.result
    metrics = {key: result[key] for key in METRICS if type(result.get(key)) in (int, float) and math.isfinite(result[key])}
    classes = classification_metrics(result.get('labels'), result.get('confusion_matrix')) if model.task_type != 'llm_sft' else None
    return {'job_id': job.id, 'name': job.name, 'task_type': model.task_type, 'created_at': aware(job.created_at).isoformat(),
        'model': {'id': model.id, 'name': model.name, 'version_id': version.id, 'version': version.version},
        'dataset': {'id': dataset.id, 'name': dataset.name, 'version_id': data.id, 'number': data.number, 'sha256': data.sha256},
        'config': job.config, 'metrics': metrics, 'per_class': classes,
        'labels': result.get('labels') if classes is not None else None,
        'confusion_matrix': result.get('confusion_matrix') if classes is not None else None}


def evaluation_csv(report):
    rows = [['类型', '名称', '指标', '值'], ['版本', '模型', '名称', report['model']['name']],
        ['版本', '模型', '版本', report['model']['version']], ['版本', '数据', '名称', report['dataset']['name']],
        ['版本', '数据', '版本', report['dataset']['number']], ['版本', '数据', 'SHA256', report['dataset']['sha256']]]
    rows += [['总体', '评估', name, value] for name, value in report['metrics'].items()]
    rows += [['配置', '训练', name, value] for name, value in report['config'].items() if value is not None and not isinstance(value, (dict, list))]
    for item in report['per_class'] or []:
        rows += [['类别', item['label'], key, item[key]] for key in ('precision', 'recall', 'f1', 'support')]
    for index, line in enumerate(report['confusion_matrix'] or []):
        rows += [['混淆矩阵', report['labels'][index] + ' / ' + report['labels'][column], '数量', value] for column, value in enumerate(line)]
    return csv_bytes(rows)
