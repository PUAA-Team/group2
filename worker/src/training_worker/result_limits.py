import json

MAX_RESULT_BYTES = 65536


def result_bytes(value):
    # 与控制平面的JSON校验保持相同转义规则。
    return len(json.dumps(value, allow_nan=False).encode('utf-8'))


def evaluation_result(metrics, errors):
    reported = errors[:100]
    result = {**metrics, 'error_samples': reported, 'error_sample_count': len(errors), 'errors_truncated': len(reported) < len(errors)}
    while result_bytes(result) > MAX_RESULT_BYTES:
        if not reported:
            raise ValueError('评估指标超过结果上限')
        reported.pop()
        result['errors_truncated'] = True
    return result
