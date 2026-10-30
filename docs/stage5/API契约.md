# API 契约

版本 v1，当前基线 0.2。M1 表中原有 30 个操作保持；真实前端联调增加首次设置两个操作及成员列表，共 33 个 API 操作。字段、响应及 Cookie 认证定义见[OpenAPI](./openapi.json)。当前完成点见 [stage6 实施进度](../stage6/实施进度.md)；后续训练与辅助协议保持设计状态。

## 通用规则

业务路径以 `/api/v1` 开头。JSON 字段 snake_case，字符串 UTF-8。实体标识为服务端生成的字符串；时间为 UTC ISO 8601。参数拒绝未知字段。创建返回 201，读取和更新返回 200，后续长任务受理返回 202。

普通成功返回 `{"data": ..., "request_id": "..."}`。分页列表返回 `{"data": [...], "pagination": {"page": 1, "page_size": 20, "total": 0}, "request_id": "..."}`；page 至少 1，page_size 为 1 至 100。默认按创建时间和稳定标识排序。

错误返回 `{"error": {"code": "FORBIDDEN", "message": "无权执行此操作", "details": []}, "request_id": "..."}`。校验错误仅列字段位置、类型和说明，不回显原始密码或请求体。请求标识由服务端生成并在响应头 `X-Request-ID` 返回。

| HTTP | 业务代码示例 | 含义 |
| --- | --- | --- |
| 400 | INVALID_REQUEST | 不符合业务输入要求 |
| 401 | UNAUTHENTICATED、INVALID_CREDENTIALS | 无有效会话或登录失败 |
| 403 | FORBIDDEN、CSRF_FAILED | 无操作权限或状态修改缺少有效 CSRF |
| 404 | NOT_FOUND | 对象不存在或不在可见范围内 |
| 409 | CONFLICT | 重名、重复版本或业务状态冲突 |
| 412 | REVISION_MISMATCH | If-Match 与实际 revision 不符 |
| 413 | FILE_TOO_LARGE | 超出文件限制 |
| 415 | UNSUPPORTED_FORMAT | 当前解析器不支持的格式 |
| 422 | VALIDATION_ERROR | 字段或文件内容校验失败 |
| 428 | PRECONDITION_REQUIRED | 可变资产更新未提供 If-Match |
| 429 | RATE_LIMITED | 登录/后续外部模型调用受限 |
| 503 | NOT_READY | 数据库或所需服务尚未就绪 |

### 浏览器认证

登录 JSON 为 `account` 与 `password`。登录成功设置 HttpOnly `mt_session` Cookie，并返回用户信息和 `csrf_token`。GET session 返回当前用户及同会话 CSRF；所有已认证的 POST/PATCH/DELETE 必须携带 `X-CSRF-Token`。登录也校验 Origin 允许范围，不接收表单密码。

登录与 GET session 同时返回 access，包含当前主体的全局有效 actions 和 quota。空间角色仍以空间 access 接口为准；全局允许不能跳过查看者或非成员限制。浏览器只在内存保存凭据，导航时刷新会话和当前空间策略。

Cookie SameSite=Strict，生产 HTTPS 使用 Secure。客户端不把密码、会话凭据或外部模型密钥放入 localStorage。退出撤销数据库会话并清除 Cookie。禁用账号之后的请求立即失败。会话值与 CSRF 不写日志或审计。

可变资产输出 `revision`，更新时传 `If-Match: "1"`。缺失为 428，不匹配为 412，成功返回新 revision 和 ETag。版本内容保持不可变。

## M1 端点

| 方法 | 路径 | 权限或用途 |
| --- | --- | --- |
| GET | /healthz | 进程存活，不暴露秘密 |
| GET | /readyz | 数据库及 schema 就绪检查 |
| POST | /api/v1/auth/login | 登录，失败次数限制 |
| GET | /api/v1/auth/session | 当前会话与 CSRF |
| POST | /api/v1/auth/logout | 撤销当前会话 |
| GET、POST | /api/v1/admin/users | 管理员分页查询或创建用户 |
| PATCH | /api/v1/admin/users/{user_id} | 管理员启停、组与个人授权；并发控制 |
| GET、POST | /api/v1/admin/groups | 管理员分页查询或创建组 |
| PATCH | /api/v1/admin/groups/{group_id} | 管理组策略；并发控制 |
| GET、POST | /api/v1/workspaces | 查询可见空间、创建空间 |
| POST | /api/v1/workspaces/{workspace_id}/members | 空间管理者维护成员及角色 |
| GET | /api/v1/workspaces/{workspace_id}/access | 当前主体有效授权和配额 |
| GET | /api/v1/trainer-templates | 三类受控任务模板与执行能力状态 |
| GET、POST | /api/v1/workspaces/{workspace_id}/models | 查询或登记模型资产 |
| GET、PATCH | /api/v1/workspaces/{workspace_id}/models/{model_id} | 模型元信息；读取/写入分开授权 |
| GET、POST | /api/v1/workspaces/{workspace_id}/models/{model_id}/versions | 查询或登记不可变模型来源版本 |
| GET、POST | /api/v1/workspaces/{workspace_id}/datasets | 查询或登记数据集 |
| GET、PATCH | /api/v1/workspaces/{workspace_id}/datasets/{dataset_id} | 数据集元信息，文件内容不在此修改 |
| GET、POST | /api/v1/workspaces/{workspace_id}/datasets/{dataset_id}/versions | 查询或真实上传版本文件 |
| GET | /api/v1/workspaces/{workspace_id}/datasets/{dataset_id}/versions/{version_id}/preview | 获授权样本预览，数量有上限 |
| GET | /api/v1/workspaces/{workspace_id}/audit | 查询本空间关键操作审计 |

用户创建包含 account、display_name、password、group_id 和可选平台角色；角色及授权只允许管理员设置。组与个人权限使用登记过的动作名，拒绝通配符扩大和未知动作。空间成员角色限定 editor/viewer。

模型登记包含 name、task_type、trainer_id、source_ref 和可选 description。任务类型为 text_classification、image_classification、llm_sft；模板必须匹配。source_ref 在 M1 只登记，不访问远端、不下载权重；拒绝含用户名密码或明显凭据参数的 URL。模型版本包含 version、source_ref，状态由服务端确定。

数据集登记包含 name、task_type、description。版本上传使用 multipart 的 file 字段，服务端限制总大小、文件类型、编码、行数和字段。M1 首批实现文本分类 CSV 与指令微调 JSONL；图像数据归档与编辑器在对应里程碑接入，未实现格式明确返回 415。

当前默认每个文件最多 10 MiB、10000 个样本；请求总量还包含最多 64 KiB 的 multipart 外围空间。预览 limit 默认 10、范围 1 至 50。模型/数据元信息只可修改 name、description；任务、训练器与来源更换应登记新资产或新版本。用户和组的 PATCH 使用 exclude_unset 语义，未提供字段保留，空数组明确清空授权；group_id 可设为 null，其他可变字段拒绝显式 null。

文本 CSV 字段为 text、label，空标签可以进入待标注状态，空文本不通过。JSONL 字段为 instruction、input、output，input 可为空，instruction/output 必须有内容。所有行校验成功后才创建版本，返回实际 sha256、size_bytes、sample_count 和状态。数字由解析器计算，不接受客户端自报样本数量。

## 真实前端联调增量

| 方法 | 路径 | 规则 |
| --- | --- | --- |
| GET | /api/v1/setup | 只返回 initialized、enabled，不返回账号、凭据或初始化口令 |
| POST | /api/v1/setup | 默认关闭；须显式开启、本机 Host、回环客户端、允许的 Origin；创建首位管理员后再次调用返回 409 |
| GET | /api/v1/workspaces/{workspace_id}/members | 分页返回本空间成员的账号、姓名、角色及启用状态；仅有 members.manage 的所有者或管理员可读 |

首次设置 JSON 只接收 account、display_name、password。拒绝 is_admin、group_id 或授权注入；管理员角色由服务端固定。使用数据库锁串行完成“是否已设置”检查与创建。GUI 的工作空间名称由后续正常创建空间请求处理，两个请求分别提交；若创建空间失败，已创建账号可重新登录继续，不回滚账号或重置数据库。

POST members 兼容原有 user_id；也允许 account + role，用账号精确查找已启用用户。user_id 和 account 必须且只能提供一个。不能将所有者降为 viewer，非成员无法用接口枚举用户。

用户、用户组、模型和数据集列表增加 q，最多 100 字；用户匹配账号或姓名，其余匹配名称，忽略首尾空白与大小写。百分号和下划线按字面量搜索，保持分页总数和空间过滤。未提供 q 时与 M1 行为一致。

根路径 `/` 提供真实页面，live/styles/js 提供显式前端静态资源，未计入 API 操作数。后台、运行数据、日志和 docs 不作静态挂载。默认允许来源增加 8000 的精确回环 URL，不允许通配符；生产通过配置替换。部署与本机设置见 [stage6 运行说明](../stage6/运行与演示.md)。

## 后续训练与辅助端点

训练后续按 workspace 组织 projects、training-drafts、training-tasks、executions、events、artifacts、evaluations 和 inference-services。受理须携带幂等标识，固定快照后返回任务号，不等待训练结束。取消与停止使用独立业务动作，不由前端 PATCH status。

辅助后续按 connections、previews、authorizations、assistant-requests、results、adoptions 组织。调用前预览与授权绑定输入摘要及版本。采纳包含 result_id、选定项和期望输入版本，只允许创建新配置或新数据版本，不允许执行任意脚本。

Worker 使用独立 `/api/worker/v1` 协议和凭据，与浏览器会话及推理 API KEY 分开。完整消息要求见[协议](./Worker与智能辅助协议.md)。这些端点尚未由 M1 实现，不在 M1 OpenAPI 中声明为可用。
