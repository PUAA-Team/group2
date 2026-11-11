"""严格校验外部模型返回的辅助结果。

未知字段、重复或越界的样本序号、范围外的训练参数和不存在的日志证据一律拒绝，
不尝试猜测或修补模型输出。
"""
import json

from pydantic import ValidationError

from ..assistant_schemas import AnnotationOutput, LogOutput, ParameterOutput
from ..errors import Problem
from ..job_schemas import TrainConfig


def _object(text):
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        value = "\n".join(lines)
    try:
        data = json.loads(value)
    except (json.JSONDecodeError, RecursionError):
        raise Problem(502, "INVALID_OUTPUT", "模型输出不是有效JSON，请重新生成") from None
    if not isinstance(data, dict):
        raise Problem(502, "INVALID_OUTPUT", "模型输出不是JSON对象，请重新生成")
    return data


def _range_check(pairs, config):
    try:
        TrainConfig(**{**config, **dict(pairs)})
    except (ValidationError, TypeError):
        raise Problem(502, "INVALID_OUTPUT", "模型给出的参数超出允许范围，请重新生成") from None


def _annotation(output, binding):
    allowed = set(binding["sample_indices"])
    codes = binding["label_codes"]
    seen, samples = set(), []
    for sample in output.samples:
        if sample.index in seen or sample.index not in allowed:
            raise Problem(502, "INVALID_OUTPUT", "模型返回的样本序号无效，请重新生成")
        seen.add(sample.index)
        if binding["task_type"] == "llm_sft":
            value = sample.value
        elif sample.value in codes:
            value = codes[sample.value]
        else:
            raise Problem(502, "INVALID_OUTPUT", "模型返回的标签不在标注范围内，请重新生成")
        samples.append({"index": sample.index, "value": value, "reason": sample.reason})
    return {"samples": samples}


def _parameters(output, config):
    seen, suggestions = set(), []
    for suggestion in output.suggestions:
        if suggestion.field in seen:
            raise Problem(502, "INVALID_OUTPUT", "模型重复给出了同一参数，请重新生成")
        seen.add(suggestion.field)
        suggestions.append({"field": suggestion.field, "value": suggestion.value, "reason": suggestion.reason})
    _range_check([(item["field"], item["value"]) for item in suggestions], config)
    return {"suggestions": suggestions}


def _logs(output, binding):
    evidence = set(binding["evidence"])
    causes = []
    for cause in output.causes:
        if set(cause.evidence) - evidence:
            raise Problem(502, "INVALID_OUTPUT", "模型引用了不存在的日志证据，请重新生成")
        causes.append({"reason": cause.reason, "evidence": cause.evidence, "steps": cause.steps})
    suggestions = []
    if output.suggestions:
        data = {"suggestions": [item.model_dump() for item in output.suggestions]}
        suggestions = _parameters(ParameterOutput.model_validate(data), binding["job"]["config"])["suggestions"]
    return {"summary": output.summary, "causes": causes, "suggestions": suggestions}


def normalize(purpose, text, binding):
    data = _object(text)
    schemas = {"annotation": (AnnotationOutput, _annotation), "parameters": (ParameterOutput, None),
               "logs": (LogOutput, _logs)}
    schema, resolve = schemas[purpose]
    try:
        output = schema.model_validate(data)
    except ValidationError:
        raise Problem(502, "INVALID_OUTPUT", "模型输出不符合约定结构，请重新生成") from None
    if purpose == "parameters":
        return _parameters(output, binding["job"]["config"])
    return resolve(output, binding)
