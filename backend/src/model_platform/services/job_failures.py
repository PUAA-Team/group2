"""训练作业失败原因分类与聚合。

失败原因只来自作业本身已有的数据：Worker 结案时写入的 ``Job.error``
自由文本与 ``Job.result`` 里的 ``failure_code``/``failure_stage``，不新增
表结构、不改写历史记录。分类口径固定如下，优先级从高到低：

1. ``result.failure_code``（Worker 明确上报的错误码）；
2. ``result.failure_stage``（失败阶段，如产物上传）；
3. ``error`` 文本关键字匹配；
4. 以上都没有且 ``error`` 为空：未记录原因（空错误兜底）；
5. 以上都没有但 ``error`` 非空：未分类。
"""
from sqlalchemy import func, or_, select

from ..database import aware
from ..job_models import Execution, Job

# Worker 结案时上报的 failure_code -> 错误类型。
CODE_TYPES = {
    "OUT_OF_MEMORY": ("out_of_memory", "显存不足"),
    "RUNTIME_ERROR": ("runtime_error", "运行异常"),
    "INPUT_ERROR": ("input_error", "输入数据错误"),
    "STORAGE_LIMIT": ("storage_limit", "存储空间不足"),
    "GROUP_STORAGE_LIMIT": ("storage_limit", "存储空间不足"),
    "FILE_TOO_LARGE": ("file_too_large", "文件过大"),
    "INVALID_ARTIFACT": ("invalid_artifact", "产物无效"),
    "FILE_NOT_READY": ("input_missing", "输入缺失"),
    "MODEL_NOT_READY": ("input_missing", "输入缺失"),
}

# Worker 结案时上报的 failure_stage -> 错误类型。
STAGE_TYPES = {
    "artifact_upload": ("artifact_upload", "产物上传失败"),
    "training": ("runtime_error", "运行异常"),
    "evaluation": ("runtime_error", "运行异常"),
}

# error 文本关键字（小写匹配）-> 错误类型，按顺序命中第一条。
TEXT_TYPES = [
    (("out of memory", "显存不足", "cuda out of memory"), ("out_of_memory", "显存不足")),
    (("cuda", "gpu"), ("gpu_error", "GPU 异常")),
    (("timeout", "timed out", "超时"), ("timeout", "执行超时")),
    (("connection", "连接失败", "连接超时", "连接被拒绝"), ("connection_error", "连接失败")),
    (("permission", "权限"), ("permission_error", "权限不足")),
    (("no space", "磁盘空间", "disk full", "磁盘已满"), ("disk_full", "磁盘空间不足")),
    (("子进程", "worker", "节点"), ("worker_error", "节点异常")),
    (("数据", "样本", "标签", "dataset"), ("input_error", "输入数据错误")),
]

EMPTY_TYPE = ("empty_error", "未记录原因")
UNKNOWN_TYPE = ("unclassified", "未分类")

# 全部已知错误类型代码：code/stage/文本关键字三路口径的并集 + 两个兜底类型。
# 作业列表 failure_type 与失败聚合 error_type 只接受这里的取值，未知取值 422。
KNOWN_ERROR_TYPES = frozenset(
    {code for code, _ in CODE_TYPES.values()}
    | {code for code, _ in STAGE_TYPES.values()}
    | {code for _, (code, _) in TEXT_TYPES}
    | {EMPTY_TYPE[0], UNKNOWN_TYPE[0]})


def is_known_error_type(error_type):
    """failure_type/error_type 取值是否在已知错误类型清单内。"""
    return isinstance(error_type, str) and error_type in KNOWN_ERROR_TYPES


def failure_code_prefilter(error_type):
    """failure_type 的 SQL 预筛条件：排除 failure_code 已明确映射到其他错误类型
    的作业。failure_code 在分类口径里优先级最高，这类作业不可能再归为目标类型；
    无 failure_code 或 code 未知的作业仍保留候选，由 Python 侧按固定口径精筛
    （stage/错误文本/空错误兜底），所以预筛结果与精筛结果一致，只是少加载行。
    返回 SQLAlchemy 条件；无可排除的 code 时返回 None。"""
    other_codes = [code for code, (code_type, _) in CODE_TYPES.items() if code_type != error_type]
    if not other_codes:
        return None
    code = Job.result["failure_code"].as_string()
    return or_(code.is_(None), ~code.in_(other_codes))

MAX_ERROR_LINE = 200


def latest_error_line(error):
    """最近日志行：错误文本的首个非空行，截断到 200 字符；无文本返回 None。"""
    if not error:
        return None
    for line in str(error).splitlines():
        line = line.strip()
        if line:
            return line[:MAX_ERROR_LINE]
    return None


def classify_failure(job):
    """按固定口径给一条失败作业分类，返回 (错误类型代码, 中文标签)。"""
    result = job.result or {}
    code = result.get("failure_code")
    if isinstance(code, str) and code in CODE_TYPES:
        return CODE_TYPES[code]
    stage = result.get("failure_stage")
    if isinstance(stage, str) and stage in STAGE_TYPES:
        return STAGE_TYPES[stage]
    error = job.error or ""
    if not error.strip():
        return EMPTY_TYPE
    text = error.lower()
    for keywords, failure_type in TEXT_TYPES:
        if any(keyword in text for keyword in keywords):
            return failure_type
    return UNKNOWN_TYPE


def _iso(value):
    return aware(value).isoformat() if value else None


def failure_detail(db, job):
    """单条失败作业的错误摘要：错误类型、失败时间、同类型首次出现时间、最近日志行。"""
    code, label = classify_failure(job)
    execution = db.scalar(select(Execution).where(Execution.job_id == job.id))
    failed_at = execution.finished_at if execution and execution.finished_at else job.created_at
    # 同类型首次出现：同空间内最早出现该错误类型的失败作业时间；没有可比对的
    # 历史时退化为本条作业自身的失败时间。
    # 先按 failure_code 在 SQL 层预筛候选：failure_code 已明确映射到其他错误
    # 类型的作业不可能归为本条类型，直接不加载；无 code 或未知 code 的作业仍
    # 保留候选，由 Python 侧按固定口径精筛，首次出现时间与原来一致。
    same_type_first = None
    query = select(Job).where(Job.workspace_id == job.workspace_id, Job.status == "failed")
    prefilter = failure_code_prefilter(code)
    if prefilter is not None:
        query = query.where(prefilter)
    for other in db.scalars(query.order_by(Job.created_at.asc(), Job.id.asc())).all():
        if classify_failure(other)[0] == code:
            same_type_first = other.created_at
            break
    return {"error_type": code, "error_label": label, "failed_at": _iso(failed_at),
            "first_seen_at": _iso(same_type_first or failed_at),
            "latest_error": latest_error_line(job.error)}


def _group_add(groups, code, label, created_at, job_id, job_name, error, count=1, first_at=None):
    """把一条（或一组）失败作业并入分组：计数累加，首次出现取最早时间，最新一
    条取 (created_at, id) 最大者；与旧的全量扫描口径一致（旧口径按时间升序遍历、
    最新一条以后到的为准，即 (created_at, id) 最大者）。"""
    group = groups.setdefault(code, {"error_type": code, "error_label": label, "count": 0,
                                     "first_seen_at": None, "last_seen_at": None,
                                     "latest_job_id": None, "latest_job_name": None,
                                     "latest_error": None, "_first_at": None,
                                     "_latest_at": None, "_latest_id": None})
    group["count"] += count
    first = first_at if first_at is not None else created_at
    if group["_first_at"] is None or first < group["_first_at"]:
        group["_first_at"] = first
        group["first_seen_at"] = _iso(first)
    if group["_latest_at"] is None or (created_at, job_id) >= (group["_latest_at"], group["_latest_id"]):
        group["_latest_at"] = created_at
        group["_latest_id"] = job_id
        group["last_seen_at"] = _iso(created_at)
        group["latest_job_id"] = job_id
        group["latest_job_name"] = job_name
        group["latest_error"] = latest_error_line(error)
    return group


def _known_code_latest_query(workspace_id, kind=None):
    """按 failure_code 分桶聚合一次取数：failure_code 已明确映射到已知错误类型
    的失败作业，每组只取最新一行，并附带组内计数与首次出现时间（窗口函数）。
    SQLite 与 PostgreSQL 均支持窗口函数；code 取值走与 26-4 同一 JSON 提取
    写法（SQLite 编译为 JSON_EXTRACT，PostgreSQL 编译为 ->>）。"""
    code = Job.result["failure_code"].as_string()
    conditions = [Job.workspace_id == workspace_id, Job.status == "failed",
                  code.is_not(None), code.in_(list(CODE_TYPES))]
    if kind:
        conditions.append(Job.kind == kind)
    ranked = select(
        Job.id, Job.name, Job.created_at, Job.error, code.label("code"),
        func.count().over(partition_by=code).label("code_count"),
        func.min(Job.created_at).over(partition_by=code).label("code_first"),
        func.row_number().over(
            partition_by=code, order_by=[Job.created_at.desc(), Job.id.desc()]).label("rn"),
    ).where(*conditions).subquery()
    return select(ranked).where(ranked.c.rn == 1)


def _ambiguous_failed_jobs_query(workspace_id, kind=None):
    """无 failure_code 或 code 未知的失败作业：仍需 Python 侧按固定口径分类。"""
    code = Job.result["failure_code"].as_string()
    query = select(Job).where(Job.workspace_id == workspace_id, Job.status == "failed",
                              or_(code.is_(None), ~code.in_(list(CODE_TYPES))))
    if kind:
        query = query.where(Job.kind == kind)
    return query.order_by(Job.created_at.asc(), Job.id.asc())


def failure_summary(db, workspace_id, kind=None, error_type=None):
    """失败作业按错误类型分组计数：每组含数量、首次/最近出现时间、最新一条作业与错误行。

    ``error_type`` 给定时只返回该类型一组，``total_failed`` 也只计该类型的
    失败作业数；该类型无失败作业时返回空分组。
    不带 ``error_type`` 时不再全量加载全部失败作业：failure_code 已明确映射
    到已知类型的作业按 code 分桶聚合一次取数（每组只取最新一行，附带组内计数
    与首次出现时间），无 code 或未知 code 的作业仍加载全行按固定口径在
    Python 侧分类后并入各组；两路结果与旧的全量扫描口径一致。
    """
    query = select(Job).where(Job.workspace_id == workspace_id, Job.status == "failed")
    if kind:
        query = query.where(Job.kind == kind)
    groups = {}
    if error_type:
        # 先按 failure_code 在 SQL 层预筛候选（code 已映射到其他类型的作业不可能
        # 归为该类型），再按固定口径在 Python 侧精筛，与列表 failure_type 同一口径。
        prefilter = failure_code_prefilter(error_type)
        if prefilter is not None:
            query = query.where(prefilter)
        jobs = db.scalars(query.order_by(Job.created_at.asc(), Job.id.asc())).all()
        for job in jobs:
            code, label = classify_failure(job)
            if code != error_type:
                continue
            _group_add(groups, code, label, job.created_at, job.id, job.name, job.error)
    else:
        # 已知 code 的作业：分桶聚合一次取数，每组只取最新一行。
        for row in db.execute(_known_code_latest_query(workspace_id, kind)).mappings().all():
            code, label = CODE_TYPES[row["code"]]
            _group_add(groups, code, label, row["created_at"], row["id"], row["name"],
                       row["error"], count=row["code_count"], first_at=row["code_first"])
        # 无 code / 未知 code 的作业：仍按固定口径分类后并入各组（含可能与已知
        # code 组同类型的文本/stage/空错误作业）。
        for job in db.scalars(_ambiguous_failed_jobs_query(workspace_id, kind)).all():
            code, label = classify_failure(job)
            _group_add(groups, code, label, job.created_at, job.id, job.name, job.error)
    ordered = sorted(groups.values(), key=lambda group: (-group["count"], group["last_seen_at"] or ""))
    for group in ordered:
        del group["_first_at"]
        del group["_latest_at"]
        del group["_latest_id"]
    return {"total_failed": sum(group["count"] for group in ordered), "groups": ordered}
