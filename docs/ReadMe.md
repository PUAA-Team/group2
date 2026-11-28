# 大模型集成训练平台：项目资料索引

## 项目介绍

本项目拟建设面向企业和开发团队内部使用的大模型集成训练平台，帮助缺乏训练经验的成员完成数据准备、模型选择、训练配置、任务执行和结果判断，并为熟悉训练的成员保留高级配置。目标流程包括模型与数据集维护、参数与资源选择、训练监控、模型产物、评估和内部推理服务；管理侧负责资产、用户组与个人权限、资源和审计。

2026-10-28 已确认一期真实训练覆盖文本分类、图像分类、小型 Qwen LoRA 微调，并接入真实大模型 API，完成智能标注、智能参数推荐和智能日志解释。模型和数据集由管理员或获授权用户从页面维护；外发数据采用工作空间授权、用户选定内容、脱敏预览确认后调用的方式。Agents、记忆、工具调用、新任务类型、训练器插件及云平台高级扩展入口作为后续方向。已进入[真实版本一期工程](./stage5/ReadMe.md)，先形成设计及 API 基线，再实现基础后端；实际完成状态见[实施进度](./stage5/实施进度与交接.md)。

项目已接通真实数据、资源、训练、评估与内部推理流程，并完成云端控制、本机GPU执行的部署验证。8765纯前端原型保留用于对照；当前真实版本支持管理员建号、邀请注册及三项智能辅助。公共自由注册保持关闭，具体完成状态见当前进度。

## 当前进度

2026-11-28：在 `lx/stage29-1-invite-list-grace-days` 分支完成 **Stage 29-1（邀请列表接口返回当前生效的 grace_days）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已全部完成（27-1 至 27-5），28 方向已全部完成（28-1 至 28-5），本轮做 29 方向第一个阶段。核查发现 28-2 的邀请列表接口不返回当前生效的宽限期，前端选择器只按 URL 参数回显，URL 参数非法或缺失时回显与实际生效值可能错位：响应信封 `response()` 增加可选 `extra` 参数（`data` 形状不变），注册邀请列表与空间邀请列表响应顶层各回显当前生效的 `grace_days`（默认 7 天，显式传参时回显传入值）；前端新增共享 `graceDaysSelected()`，以后端返回为准（7 天对应默认空选项，0/30 对应预设值），接口未返回有效值时回落到 URL 参数，两处选择器改用该函数回显。`live/` 缓存版本统一为 stage29-1（104 处 `?v=` 与 `ASSET_VERSION` 一致）。本地验证通过：后端 `361 passed`（基线 358 项 + 新增 3 项），前端 `281 pass, 0 fail`（基线 278 项 + 新增 3 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 29-1 实施与验收](./stage29-1/实施与验收.md)与 [OpenAPI](./stage29-1/openapi.json)。

2026-11-28：在 `lx/stage28-5-sweep-failure-detail` 分支完成 **Stage 28-5（邀请清理失败原因码细化）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已全部完成（27-1 至 27-5），28 方向已完成 28-1、28-2、28-3、28-4，本轮做 28 方向第五个阶段。核查发现 27-4 的失败原因码只区分到异常类型一级，同为 `OperationalError` 的连接被拒与连接超时都记 `SWEEP_DB_UNAVAILABLE`，删除单行失败只在约束冲突时归为 `SWEEP_DELETE_FAILED`：`OperationalError` 按底层错误码（psycopg3 的 `sqlstate` / psycopg2 的 `pgcode`，57014 判超时）与消息关键字再区分，连接被拒记 `SWEEP_DB_CONN_REFUSED`、连接/语句超时记 `SWEEP_DB_TIMEOUT`、其余仍为 `SWEEP_DB_UNAVAILABLE`（鉴权失败不误判为被拒）；删除阶段异常打上 `sweep_stage="delete"` 标记，约束冲突以外的删除阶段异常也归为 `SWEEP_DELETE_FAILED`，删除阶段的连接错误仍优先按数据库原因码归类。前端无改动，`live/` 缓存版本不 bump。本地验证通过：后端 `358 passed`（基线 339 项 + 新增 19 项），前端 `278 pass, 0 fail`（本轮无前端改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 28-5 实施与验收](./stage28-5/实施与验收.md)与 [OpenAPI](./stage28-5/openapi.json)。

2026-11-28：在 `lx/stage28-4-storage-reconcile-paging` 分支完成 **Stage 28-4（存储对账孤儿表分页/分批清理）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已全部完成（27-1 至 27-5），28 方向已完成 28-1、28-2、28-3，本轮做 28 方向第四个阶段。核查发现对账接口一次返回全部孤儿文件、管理端页面只截取前 100 个展示且清理一次删全部孤儿：对账接口新增 `limit`/`offset`（默认每页 100，非法值 422），预览按页返回孤儿列表（总数与总占用仍为全量），清理只删排序后前 `limit` 个孤儿并返回剩余数，前端孤儿表改走通用翻页器、确认清理每批最多 100 个且提示如实报剩余数，刷新后可继续下一批。`live/` 缓存版本统一为 stage28-4（104 处 `?v=` 与 `ASSET_VERSION` 一致）。本地验证通过：后端 `339 passed`（基线 334 项 + 新增 5 项），前端 `278 pass, 0 fail`（基线 273 项 + 新增 5 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线路径一致（仅 `StorageReconcileInput` 新增 `limit`/`offset` 字段）。未合并 main，未部署，未推送。详见[Stage 28-4 实施与验收](./stage28-4/实施与验收.md)与 [OpenAPI](./stage28-4/openapi.json)。

2026-11-28：在 `lx/stage28-3-failure-summary-prefilter` 分支完成 **Stage 28-3（失败聚合与单条失败摘要预筛）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已全部完成（27-1 至 27-5），28 方向已完成 28-1、28-2，本轮做 28 方向第三个阶段。核查发现 26-4 只给带 `error_type` 的失败聚合与作业列表加了 `failure_code` 的 SQL 预筛，不带 `error_type` 的失败聚合与单条作业失败摘要仍全量扫描失败作业：无类型聚合改按 `failure_code` 分桶聚合一次取数（窗口函数每组只取最新一行，附带组内计数与首次出现时间），无码/未知码作业仍按固定口径在 Python 侧分类后并入各组；单条摘要的同类型首次出现扫描叠加 `failure_code` 预筛。预筛前后聚合与摘要结果一致（新测试含旧算法对照）。前端无改动，`live/` 缓存版本不 bump。本地验证通过：后端 `334 passed`（基线 328 项 + 新增 6 项），前端 `273 pass, 0 fail`（本轮无前端改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 28-3 实施与验收](./stage28-3/实施与验收.md)与 [OpenAPI](./stage28-3/openapi.json)。

2026-11-28：在 `lx/stage28-2-invite-list-grace-days` 分支完成 **Stage 28-2（邀请列表接口接受 grace_days 参数）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已全部完成（27-1 至 27-5），28 方向已完成 28-1，本轮做 28 方向第二个阶段。核查发现 27-3 的邀请列表“已过期”展示一律按默认 7 天宽限期算，手动触发清理接口可显式传 grace_days，两者不一致时展示与清理口径可能错位：注册邀请列表与空间邀请列表新增可选 grace_days 查询参数（0–365，默认 7 天），与清理口径共用同一校验与默认值，过期状态按传入宽限期算；前端两处邀请列表各加宽限期选择器（默认 7 天 / 无宽限期 / 30 天），经 URL 参数透传到列表请求。`live/` 缓存版本统一为 stage28-2（103 处 `?v=` 与 `ASSET_VERSION` 一致）。本地验证通过：后端 `328 passed`（基线 325 项 + 新增 3 项），前端 `273 pass, 0 fail`（基线 271 项 + 新增 2 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径（两处列表接口各新增 grace_days 查询参数）。未合并 main，未部署，未推送。详见[Stage 28-2 实施与验收](./stage28-2/实施与验收.md)与 [OpenAPI](./stage28-2/openapi.json)。

2026-11-28：在 `lx/stage28-1-admin-session-client-two-fields` 分支完成 **Stage 28-1（管理端踢出会话弹窗客户端双字段展示）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已全部完成（27-1 至 27-5），本轮做 28 方向第一个阶段。核查发现 27-5 只改了个人会话退出确认弹窗，管理端踢出会话确认弹窗仍沿用单字段写法 `client_ip || client_agent`，有 IP 时不展示 User-Agent，而管理端与个人会话页的客户端列早已是 IP 一行、User-Agent 一行的两行展示：前端 `session-revoke-confirm` 弹窗改为“客户端 IP”与“客户端标识”两行展示，缺失字段显示“—”，两字段均经转义，与个人会话弹窗（27-5）与管理端会话页客户端列口径一致。`live/` 缓存版本统一为 stage28-1（103 处 `?v=` 与 `ASSET_VERSION` 一致）。本地验证通过：后端 `325 passed`（本轮无后端改动，与基线一致），前端 `271 pass, 0 fail`（基线 268 项 + 新增 3 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 28-1 实施与验收](./stage28-1/实施与验收.md)与 [OpenAPI](./stage28-1/openapi.json)。

2026-11-28：在 `lx/stage27-5-personal-session-client-two-fields` 分支完成 **Stage 27-5（个人会话弹窗客户端双字段展示）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已完成 27-1、27-2、27-3、27-4，本轮做 27 方向第五阶段。核查发现 26-1 的个人会话退出确认弹窗客户端字段沿用管理端单字段写法 `client_ip || client_agent`，有 IP 时不展示 User-Agent，而管理端与个人会话页的客户端列早已是 IP 一行、User-Agent 一行的两行展示：前端 `session-revoke-own-confirm` 弹窗改为“客户端 IP”与“客户端标识”两行展示，缺失字段显示“—”，两字段均经转义，与管理端会话页客户端列口径一致。`live/` 缓存版本统一为 stage27-5（103 处 `?v=` 与 `ASSET_VERSION` 一致）。本地验证通过：后端 `325 passed`（本轮无后端改动，与基线一致），前端 `268 pass, 0 fail`（基线 265 项 + 新增 3 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 27-5 实施与验收](./stage27-5/实施与验收.md)与 [OpenAPI](./stage27-5/openapi.json)。

2026-11-28：在 `lx/stage27-4-sweep-failure-codes` 分支完成 **Stage 27-4（邀请清理失败审计区分失败原因）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已完成 27-1、27-2、27-3，本轮做 27 方向第四阶段。核查发现 26-3 的清理失败审计 `error_code` 一律固定为 `SWEEP_FAILED`，数据库不可用与清理中途异常同码、审计里无法按原因区分：后端新增 `classify_sweep_failure`（Problem 沿用业务码、OperationalError 为 `SWEEP_DB_UNAVAILABLE`、IntegrityError 为 `SWEEP_DELETE_FAILED`、其余数据库层错误为 `SWEEP_DB_ERROR`、其他异常为 `SWEEP_FAILED` 兜底），CLI 失败审计与 stderr 输出同步带上原因码，手动触发接口失败时通用失败审计仍只记一条、`error_code` 即原因码。前端无改动，`live/` 缓存版本不 bump。本地验证通过：后端 `325 passed`（基线 314 项 + 新增 11 项），前端 `265 pass, 0 fail`（本轮无前端改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 27-4 实施与验收](./stage27-4/实施与验收.md)与 [OpenAPI](./stage27-4/openapi.json)。

2026-11-28：在 `lx/stage27-3-invite-expired-grace` 分支完成 **Stage 27-3（邀请列表“已过期”状态区分宽限期内/外）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已完成 27-1、27-2，本轮做 27 方向第三阶段。核查发现 26-3 给过期邀请清理加了默认 7 天宽限期，但两处邀请列表的“已过期”展示不区分宽限期内/外：后端新增 `invite_expiry_state`（未过期返回 None，过期未满宽限期返回 `expired_grace`，过期超过宽限期返回 `expired`，与清理的宽限期口径一致），`invite_status` 与注册邀请列表共用该口径；宽限期内的过期邀请仍不可批准加入申请（`INVITE_EXPIRED`）；前端两处邀请状态文案同步为“已过期（宽限期内）”与“已过期（待清理）”，只有未使用/有效邀请可撤销。`live/` 缓存版本统一为 stage27-3（31 个文件 `?v=` 与 `ASSET_VERSION` 一致）。本地验证通过：后端 `314 passed`（基线 311 项 + 新增 3 项），前端 `265 pass, 0 fail`（基线 263 项 + 新增 2 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 27-3 实施与验收](./stage27-3/实施与验收.md)与 [OpenAPI](./stage27-3/openapi.json)。

2026-11-28：在 `lx/stage27-2-session-user-filter-search` 分支完成 **Stage 27-2（会话页用户筛选下拉改分页/搜索加载）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），27 方向已完成 27-1，本轮做 27 方向第二阶段。核查发现管理端会话页的用户筛选下拉取自全量用户（逐页拉取全部用户），用户量很大时下拉会很长、进页要拉全量；后端用户列表已有 `q` 搜索与分页参数可复用，但没有单查一条用户的接口：后端新增 `GET /api/v1/admin/users/{user_id}`（`users.manage` 权限，未知用户 404）供回显；前端会话页加载时不再拉用户全量，只取与 `user_q` 匹配的第一页用户（20 条），带 `user_id` 时单查该用户置顶回显（用户已被删时忽略回显、筛选仍按 `user_id` 生效）；筛选区改为搜索输入框（复用已有筛选变更处理）+ 下拉，已选中用户不在当前搜索页时置顶回显并保持选中，匹配超一页时提示继续输入缩小范围。`live/` 缓存版本统一为 stage27-2（31 个文件 `?v=` 与 `ASSET_VERSION` 一致）。本地验证通过：后端 `311 passed`（基线 309 项 + 新增 2 项），前端 `263 pass, 0 fail`（基线 260 项 + 新增 3 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增迁移，OpenAPI 仍 158 路径（`/api/v1/admin/users/{user_id}` 新增 GET 操作）。未合并 main，未部署，未推送。详见[Stage 27-2 实施与验收](./stage27-2/实施与验收.md)与 [OpenAPI](./stage27-2/openapi.json)。

2026-11-28：在 `lx/stage27-1-revoke-others-confirm` 分支完成 **Stage 27-1（个人会话“踢出其他设备”二次确认）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已全部完成（26-1 至 26-5），本轮做 27 方向第一阶段。核查发现个人会话页“踢出其他设备”按钮直接调 `POST /auth/sessions/revoke-others`，一次误点就会踢出全部其他会话，而管理端踢出（25-2）与个人退出该设备（26-1）都已是二次确认弹窗：`session-revoke-others` 单动作改为按当前会话数算出其他会话数并打开新弹窗 `session-revoke-others-confirm`（标题“踢出其他设备”，说明除当前会话外的全部会话将立即失效、其他设备需重新登录、当前会话不受影响，展示待踢出的其他会话数，必填勾选，提交“确认踢出”），确认后才调踢出接口并提示“已退出其他 N 个会话”；对话框路由表同步登记。`live/` 缓存版本统一为 stage27-1（31 个文件 `?v=` 与 `ASSET_VERSION` 一致）。本地验证通过：后端 `309 passed`（本轮无后端改动，与基线一致），前端 `260 pass, 0 fail`（基线 257 项 + 新增 3 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 27-1 实施与验收](./stage27-1/实施与验收.md)与 [OpenAPI](./stage27-1/openapi.json)。

2026-11-28：在 `lx/stage26-5-session-client-refresh` 分支完成 **Stage 26-5（客户端标识随活跃刷新更新）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已完成 26-1、26-2、26-3、26-4，本轮做 26 方向第五阶段，也是 26 方向最后一个阶段。核查发现 24-4 给会话加了 `client_ip`/`client_agent` 两列，但只在登录时写入；之后 `current_user` 每 60 秒节流刷新 `last_active_at` 时不碰客户端字段，用户换 IP 或换浏览器/设备后管理端会话页一直显示登录时的旧客户端：节流刷新分支里更新 `last_active_at` 的同时一并更新 `token.client_ip` 与 `token.client_agent`（口径与登录时一致：IP 取 `request.client.host`，User-Agent 截断 300 字符），同一次 `db.commit()` 写库；节流期内不写库，客户端标识也不更新，不增加写库次数。前端无改动（管理端与个人会话页已在 24-4 展示客户端字段），`live/` 缓存版本不 bump。本地验证通过：后端 `309 passed`（基线 306 项 + 新增 3 项），前端 `257 pass, 0 fail`（本轮无前端改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 26-5 实施与验收](./stage26-5/实施与验收.md)与 [OpenAPI](./stage26-5/openapi.json)。

2026-11-28：在 `lx/stage26-4-job-failure-sql-prefilter` 分支完成 **Stage 26-4（失败原因分类 SQL 预筛）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已完成 26-1、26-2、26-3，本轮做 26 方向第四阶段。核查发现 25-1 的 `GET /jobs?failure_type=…` 与 `GET /jobs/failure-summary?error_type=…` 分类全在 Python 侧，先把空间内全部失败作业一次加载进内存再逐条分类，失败作业量大时列表接口多一次全量加载：新增 `failure_code_prefilter(error_type)`，先按 `result.failure_code` 在 SQL 层排除已明确映射到其他错误类型的作业（`failure_code` 在分类口径里优先级最高，这类作业不可能再归为目标类型），无 code 或未知 code 的作业仍保留候选，由 Python 侧按固定口径（stage/错误文本/空错误兜底）精筛，预筛与精筛结果一致；SQL 用 `Job.result["failure_code"].as_string()` 取值，SQLite 编译为 `JSON_EXTRACT`、PostgreSQL 编译为 `->>`，均已核对，缺失时取值为 NULL 且条件含 `IS NULL` 分支，不误删候选行；列表 `failure_type` 与聚合 `error_type` 两处同时叠加该预筛条件。前端无改动，`live/` 缓存版本不 bump。本地验证通过：后端 `306 passed`（基线 303 项 + 新增 3 项），前端 `257 pass, 0 fail`（本轮无前端改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径且与基线逐字一致。未合并 main，未部署，未推送。详见[Stage 26-4 实施与验收](./stage26-4/实施与验收.md)与 [OpenAPI](./stage26-4/openapi.json)。

2026-11-28：在 `lx/stage26-3-invite-sweep-grace` 分支完成 **Stage 26-3（过期邀请清理保留宽限期与失败告警）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已完成 26-1、26-2，本轮做 26 方向第三阶段。核查发现 25-4 的过期邀请清理没有保留宽限期，邀请一过期下次定时任务就删掉，且定时任务失败时审计里没有任何记录：`sweep_expired_invites` 增加 `grace_days` 参数（默认 7 天），只删过期超过宽限期的邀请，宽限期内仍保留，返回结果新增 `grace_days` 字段；手动触发接口 `POST /api/v1/admin/invitations/sweep` 增加 `grace_days` 查询参数（0–365，默认 7 天），CLI `sweep-expired-invites` 增加 `--grace-days` 选项（负数拒绝）；清理失败时在独立会话里最佳努力记一条 `invitations.sweep_failed` 失败审计（操作人为触发清理的管理员，目标 `sweep`，无归属空间），向 stderr 输出错误 JSON 并以退出码 1 退出，systemd 定时器据此记录失败；`failure_audit.py` 映射新增 `sweep_invitations`，手动触发接口失败时同样记该失败审计；25-4 旧测试同步更新（默认宽限期下过期 1 天不再被清理）。前端无改动，`live/` 缓存版本不 bump。本地验证通过：后端 `303 passed`（基线 296 项 + 新增 7 项），前端 `257 pass, 0 fail`（本轮无前端改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 158 路径（sweep 接口仅新增 `grace_days` 查询参数）。未合并 main，未部署，未推送。详见[Stage 26-3 实施与验收](./stage26-3/实施与验收.md)与 [OpenAPI](./stage26-3/openapi.json)。

2026-11-28：在 `lx/stage26-2-audit-object-types` 分支完成 **Stage 26-2（审计对象类型下拉改由后端下发）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，26 方向已完成 26-1，本轮做 26 方向第二阶段。核查发现 24-3 的审计对象类型下拉是前端 `OBJECT_TYPES` 固定清单（25 个），后端新增操作代码首段时必须同步改前端：新增管理端接口 `GET /api/v1/admin/audit-object-types`（`audit.read` 权限），返回后端唯一的已知首段与中文名清单（25 个），并自动补上审计日志里已出现的新首段（标签为代码本身）；前端审计页进页时与审计列表并行取该接口，筛选弹窗优先用后端清单，加载失败或无效时回落内置清单，不阻塞审计列表加载；`live/` 缓存版本统一为 stage26-2。本地验证通过：后端 `296 passed`（基线 293 项 + 新增 3 项），前端 `257 pass, 0 fail`（基线 253 项 + 新增 4 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，新增接口 1 个，OpenAPI 157 → 158 路径。未合并 main，未部署，未推送。详见[Stage 26-2 实施与验收](./stage26-2/实施与验收.md)与 [OpenAPI](./stage26-2/openapi.json)。

2026-11-28：在 `lx/stage26-1-personal-session-logout-confirm` 分支完成 **Stage 26-1（个人会话退出二次确认）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已全部完成，本轮做 26 方向第一阶段。核查发现 25-2 只给管理端踢出会话加了二次确认，个人会话页（用户空间“登录会话管理”）的“退出该设备”仍是点下直接调 `DELETE /auth/sessions/{id}`，误点即退出该设备：`session-revoke` 单动作改为打开 `session-revoke-own-confirm` 确认弹窗（标题“退出该设备”，展示登录时间 / 最后活跃 / 客户端，必填勾选 `confirm_revoke`，提交按钮“确认退出”，点按钮本身不发请求），确认后才调 `DELETE /auth/sessions/{id}`；弹窗与提交逻辑仿照管理端 `session-revoke-confirm`；当前会话行仍只显示“当前会话”标签、不出现退出按钮；“踢出其他设备”不在本阶段范围内，仍为直接执行；`live/` 缓存版本统一为 stage26-1。本地验证通过：后端 `293 passed`（本轮无后端改动），前端 `253 pass, 0 fail`（基线 250 项 + 新增 3 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 157 路径（与基线逐字一致）。未合并 main，未部署，未推送。详见[Stage 26-1 实施与验收](./stage26-1/实施与验收.md)与 [OpenAPI](./stage26-1/openapi.json)。

2026-11-27：在 `lx/stage25-5-storage-reconcile-page` 分支完成 **Stage 25-5（存储对账管理页面）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已完成 25-1、25-2、25-3、25-4，本轮做 25 方向第五阶段。核查发现 24-1 的存储对账服务与接口已有（`POST /api/v1/admin/workspaces/{workspace_id}/storage/reconcile`，默认 `dry_run=true` 只预览，显式 `dry_run=false` 才删孤儿并记审计），但管理端一直没有页面，只能直接调接口：管理端新增“存储对账”页（`/admin/storage`，导航在“会话管理”之后，`resources.manage` 权限），进页即对当前空间自动 `dry_run` 预览，页面含工作空间下拉（切换即重新对账）、数字统计条（孤儿文件数 / 孤儿占用空间 / 缺失记账数 / 跳过暂存文件数）、孤儿文件表（大小用 `formatSize()` 分档，超 100 个只显示前 100 个并注明总数）、缺失记账分区（仅报告，不处理，超 20 条只显示前 20 条）、跳过暂存说明；有孤儿文件时才出现“确认清理”按钮，清理走二次确认弹窗（空间 / 孤儿数 / 占用空间 / 缺失记账 + 必填勾选，确认后才调 `dry_run=false`，提示如实报清理数与失败数）；`live/` 缓存版本统一为 stage25-5。本地验证通过：后端 `293 passed`（本轮无后端改动），前端 `250 pass, 0 fail`（基线 245 项 + 新增 5 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 157 路径。未合并 main，未部署，未推送。详见[Stage 25-5 实施与验收](./stage25-5/实施与验收.md)与 [OpenAPI](./stage25-5/openapi.json)。

2026-11-27：在 `lx/stage25-4-expired-invite-sweep` 分支完成 **Stage 25-4（过期邀请定时清理）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已完成 25-1、25-2、25-3，本轮做 25 方向第四阶段。核查发现邀请列表没有清理机制，已过期邀请永久堆积在列表里：新增 `sweep_expired_invites` 服务函数，只删过期后已永久失效的行（注册邀请未使用且未撤销、空间邀请未撤销，已使用/已撤销的保留作历史），空间邀请关联的加入申请一并删除（过期邀请无法再批准，且申请表外键指向邀请行）；有操作人时按空间各记一条审计（`invitations.sweep` / `workspaces.invite.sweep`），无操作人不伪造；新增管理端手动触发接口 `POST /api/v1/admin/invitations/sweep`、CLI 子命令 `sweep-expired-invites`（审计操作人取最早创建的管理员）与每日 04:00 的 systemd 定时器（只在下次部署后生效，需手动 enable）；entrypoint CLI 白名单同步放行；前端无改动，`live/` 缓存版本不 bump。本地验证通过：后端 `293 passed`（基线 290 项 + 新增 3 项），前端 `245 pass, 0 fail`（本轮无前端改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，新增接口 1 个，OpenAPI 156 → 157 路径。未合并 main，未部署，未推送。详见[Stage 25-4 实施与验收](./stage25-4/实施与验收.md)与 [OpenAPI](./stage25-4/openapi.json)。

2026-11-27：在 `lx/stage25-3-audit-export-streaming` 分支完成 **Stage 25-3（审计导出分页/异步）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已完成 25-1、25-2，本轮做 25 方向第三阶段。核查发现审计导出原先一次全量查询后截断，命中超过 10000 条直接 422 导不出来：后端导出改走分页流式（`StreamingResponse` + 每页 1000 条逐页取数编码输出，BOM 只在文件头一次，`audit.export` 在全部数据页输出完后再记、不导进文件里），删掉 10000 条上限与 422；前端导出是普通下载链接无需改动，`live/` 缓存版本不 bump。本地验证通过：后端 `290 passed`（基线 287 项 + 新增 3 项），前端 `245 pass, 0 fail`（本轮无前端改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 156 路径。未合并 main，未部署，未推送。详见[Stage 25-3 实施与验收](./stage25-3/实施与验收.md)与 [OpenAPI](./stage25-3/openapi.json)。

2026-11-27：在 `lx/stage25-2-session-management-polish` 分支完成 **Stage 25-2（会话管理完善）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已完成 25-1，本轮做 25 方向第二阶段。核查发现 24-4 的管理端会话列表只能整页浏览，不能按用户筛选也不能搜索，踢出操作无二次确认；另发现 24-4 遗留真 bug：管理端“踢出”按钮的单动作路由被 `administrationAction` 截获而从未执行，点下无反应：后端 `GET /api/v1/admin/sessions` 新增 `q`（按账号/姓名搜索）与 `user_id`（按用户精确筛选）查询参数，两者可组合，未知用户返回空页；前端会话页新增用户筛选下拉与账号/姓名搜索框，带筛选时空态区分；踢出改为二次确认弹窗（用户信息 + 必填勾选，确认后才调 `DELETE`），并修掉按钮无反应 bug；`live/` 缓存版本统一为 stage25-2。本地验证通过：后端 `287 passed`（基线 285 项 + 新增 2 项），前端 `245 pass, 0 fail`（基线 242 项 + 新增 3 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 156 路径。未合并 main，未部署，未推送。详见[Stage 25-2 实施与验收](./stage25-2/实施与验收.md)与 [OpenAPI](./stage25-2/openapi.json)。

2026-11-27：在 `lx/stage25-1-job-failure-type-filter` 分支完成 **Stage 25-1（失败原因按错误类型筛选）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已全部完成，25 方向已规划 25-1 至 25-5，本轮做 25 方向第一阶段。核查发现 24-5 的失败原因分组条点击只进失败状态筛选，看不到只看某一类错误的列表，失败聚合接口也不支持按错误类型过滤：后端 `GET /jobs` 新增 `failure_type` 查询参数（分类在 Python 侧按固定口径算，先按其余条件取失败作业候选再分类过滤、手动分页，与非失败状态求交为空页，未知类型 422），`GET /jobs/failure-summary` 新增 `error_type` 参数（只返回该类型一组，`total_failed` 只计该类型），新增 `KNOWN_ERROR_TYPES` 已知错误类型清单与校验；前端分组条链接改为 `#路径?status=failed&failure_type=<类型代码>`，已选中分组高亮（`is-active` + `aria-current`）再点一次取消该类型筛选，`failure_type` 贯通列表请求与空态判定；`live/` 缓存版本统一为 stage25-1。本地验证通过：后端 `285 passed`（基线 282 项 + 新增 3 项），前端 `242 pass, 0 fail`（基线 238 项 + 新增 4 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍 156 路径。未合并 main，未部署，未推送。详见[Stage 25-1 实施与验收](./stage25-1/实施与验收.md)与 [OpenAPI](./stage25-1/openapi.json)。

2026-11-27：在 `lx/stage24-5-job-failure-summary` 分支完成 **Stage 24-5（训练作业失败原因聚合）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已完成 24-1、24-2、24-3、24-4，本轮做 24 方向第五阶段。核查发现失败作业只有 `Job.error` 自由文本与 `result` 里的 `failure_code`/`failure_stage`，列表看不到共性失败分布，详情只有一行错误文本：新增失败分类与聚合服务（分类口径固定：`failure_code` 优先，其次 `failure_stage`，再按 `error` 文本关键字匹配，空错误兜底“未记录原因”，都不命中为“未分类”）；新增接口 `GET /api/v1/workspaces/{workspace_id}/jobs/failure-summary`（按错误类型分组计数，含数量、首次/最近出现时间、最新一条作业与最近错误行，可按任务类型筛选）；作业详情接口在失败作业上附加 `failure` 摘要（错误类型、失败时间、同类型首次出现时间、最近错误行）；前端作业列表顶部新增“失败原因”分组条（点击进失败筛选），训练与评估/服务详情页失败作业错误摘要置顶；`live/` 缓存版本统一为 stage24-5。本地验证通过：后端 `282 passed`（基线 276 项 + 新增 6 项），前端 `238 pass, 0 fail`（基线 233 项 + 新增 5 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，新增接口 1 个，OpenAPI 155 → 156 路径。未合并 main，未部署，未推送。详见[Stage 24-5 实施与验收](./stage24-5/实施与验收.md)与 [OpenAPI](./stage24-5/openapi.json)。

2026-11-27：在 `lx/stage24-4-session-management` 分支完成 **Stage 24-4（会话管理面）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已完成 24-1、24-2、24-3，本轮做 24 方向第四阶段。核查发现个人会话已有摘要机制，但管理员看不到全站在线会话、踢不了他人会话，且 `sessions` 表无最后活跃时间与客户端标识：迁移 0020 给 `sessions` 增加 `last_active_at`/`client_ip`/`client_agent`（历史行 `last_active_at` 按 `created_at` 回填），登录时记录客户端 IP 与 User-Agent，经鉴权的请求 60 秒节流刷新一次活跃时间；新增管理端接口 `GET /api/v1/admin/sessions`（只列未过期会话，用户/登录时间/最后活跃/客户端标识/是否当前会话，带分页）与 `DELETE /api/v1/admin/sessions/{session_id}`（踢出后立即失效，踢自己当前会话 409，记审计 `auth.session.admin_revoke`）；前端管理端新增会话页（统计条 + 表格，他人会话可踢出，当前会话不可踢），导航新增“会话管理”入口，个人会话表同步补最后活跃与客户端两列；`live/` 缓存版本统一为 stage24-4。本地验证通过：后端 `276 passed`（基线 271 项 + 新增 5 项），前端 `233 pass, 0 fail`（基线 229 项 + 新增 4 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。表结构变更 1 次（迁移 0020），新增接口 2 个，OpenAPI 153 → 155 路径。未合并 main，未部署，未推送。详见[Stage 24-4 实施与验收](./stage24-4/实施与验收.md)与 [OpenAPI](./stage24-4/openapi.json)。

2026-11-27：在 `lx/stage24-3-audit-object-type` 分支完成 **Stage 24-3（审计日志对象类型筛选与导出贯通）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已完成 24-1、24-2，本轮做 24 方向第三阶段。核查发现操作人/时间范围/操作代码筛选、CSV 导出接口、前端筛选栏与导出按钮、导出记审计在基线里已有，本轮只补唯一缺失的**对象类型**筛选：后端 `catalog_filters` 新增 `object_type` 参数，审计查询按操作代码首段精确匹配（`startswith` + `autoescape=True`，通配符按字面匹配、不完整首段不命中），列表与导出共用同一筛选；前端审计筛选弹窗新增对象类型下拉（24 个对象类型），筛选条件自动贯通到列表请求、导出链接与筛选标签；`live/` 缓存版本统一为 stage24-3。本地验证通过：后端 `271 passed`（基线 268 项 + 新增 3 项），前端 `229 pass, 0 fail`（基线 227 项 + 新增 2 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍为 153 路径。未合并 main，未部署，未推送。详见[Stage 24-3 实施与验收](./stage24-3/实施与验收.md)与 [OpenAPI](./stage24-3/openapi.json)。

2026-11-27：在 `lx/stage24-2-npm-audit` 分支完成 **Stage 24-2（npm 依赖安全审计）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，24 方向已完成 24-1，本轮做 24 方向第二阶段，收掉 23-5 的残留项。`npm audit` 仍被出口代理策略拦住（403 `policy_denied`），改走 lockfile 离线审计：`package-lock.json` 的 100 个包批量查 OSV，仅 minimatch@9.0.9 有 1 条漏洞 GHSA-g3hv-75wg-m249（CVE-2026-118764，glob 模式放大导致的拒绝服务，仅可用性低影响，无机密性与完整性影响）；引入链为 vue-tsc → @vue/language-core（声明 `^9.0.3`），9.x 无修复版，修复仅在 11.0.1+；`package.json` 增加 `overrides` 强制 minimatch `^11.0.1`（实际解析 11.0.9，brace-expansion 随之 2.1.8 → 5.1.0），language-core 仅用 `minimatch(str, pattern)` 双参调用，签名在 9→11 不变；复核新 lockfile 的 101 个包 0 漏洞。其余直接依赖均已是 range 内最新且干净（vue 3.5.46、vite 6.4.6、typescript 5.9.3）。本地验证通过：后端 `268 passed`（本轮无后端改动），前端 `227 pass, 0 fail`（本轮无 live/ 改动），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍为 153 路径。未合并 main，未部署，未推送。详见[Stage 24-2 实施与验收](./stage24-2/实施与验收.md)与 [OpenAPI](./stage24-2/openapi.json)。

2026-11-27：在 `lx/stage24-1-storage-reconcile` 分支完成 **Stage 24-1（孤儿文件对账清理）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23 方向已全部完成，本轮按“后续自规划”新开方向 24（持续维护与小功能）第一阶段，收掉 23-3 的残留项。新增存储对账服务：扫描空间存储目录与 `StoredObject` 记账比对，列出无记账孤儿文件（附大小）、缺失记账（只报告不删行）与跳过的进行中上传暂存文件；新增管理端接口 `POST /api/v1/admin/workspaces/{workspace_id}/storage/reconcile`，默认 `dry_run=true` 只预览，显式 `dry_run=false` 才删孤儿、剪空目录并记审计 `storage.reconcile`；空间标识含路径分隔符直接 422，资产删除仍只按记账 key 逐个删文件、不设目录兜底。本地验证通过：后端 `268 passed`（含新增 6 项），前端 `227 pass, 0 fail`，`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，新增接口 1 个，OpenAPI 152 → 153 路径。未合并 main，未部署，未推送。详见[Stage 24-1 实施与验收](./stage24-1/实施与验收.md)与 [OpenAPI](./stage24-1/openapi.json)。

2026-11-27：在 `lx/stage23-5-dependency-audit` 分支完成 **Stage 23-5（依赖升级与安全审计）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23-1 至 23-4 已完成，本轮做 23 方向第五阶段，23 方向至此全部完成。pip-audit 审计本地 venv 的 54 个包，发现 Pillow 12.3.0 有 41 个已知漏洞与 pip 24.0 自身 12 个漏洞：Pillow 升至 13.0.0（`requirements.txt` 范围放宽为 `>=12,<14`）、pip 升至 26.3、httpx 升至 0.29.0（唯一在声明范围内的次要版本升级），复核 `No known vulnerabilities found` 且 `pip check` 通过；`requirements.lock.txt` 按当前 venv 同步为 30 项（排除 pip-audit 专属依赖，去掉 stale 的 tzdata 与 colorama）。npm 侧 `npm audit` 被出口代理策略拦住未能运行，`npm outdated` 显示全部依赖已是 range 内最新，无次要版本可升，`package.json` 与 `package-lock.json` 无改动。本地验证通过：后端 `262 passed`，前端 `227 pass, 0 fail`，`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口，OpenAPI 仍为 152 路径。未合并 main，未部署，未推送。详见[Stage 23-5 实施与验收](./stage23-5/实施与验收.md)与 [OpenAPI](./stage23-5/openapi.json)。

2026-11-27：在 `lx/stage23-4-auto-refresh` 分支完成 **Stage 23-4（长耗时任务轻量自动刷新）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23-1、23-2、23-3 已完成，本轮做 23 方向第四阶段。补齐三处缺口：原有 3 秒轮询只覆盖计算/训练/智能辅助与 `/data-operations`，标注页不在范围，现新增共享判定 `hasRunningTask`（作业运行中、数据处理排队/运行中、标注批次进行中、智能辅助排队/进行中、计算节点已预留执行、服务调用待回包才轮询，已结束任务停止轮询），标注页随数据页一并纳入；训练/评估/服务/数据处理/标注四个详情页新增“自动刷新”开关（仅运行中任务时出现，状态记入偏好默认开启，关闭后整站停轮）；轮询失败静默跳过，不覆盖页面数据、不弹错。无表结构变更，无新增接口，OpenAPI 仍为 152 路径；`live/` 缓存版本统一为 `stage23-4`（102 处 `?v=`）。本地验证通过：后端 `262 passed`（本轮无后端改动），前端 `227 pass, 0 fail`（含新增 6 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。未合并 main，未部署，未推送。详见[Stage 23-4 实施与验收](./stage23-4/实施与验收.md)与 [OpenAPI](./stage23-4/openapi.json)。

2026-11-27：在 `lx/stage23-3-physical-delete` 分支完成 **Stage 23-3（资产/项目物理删除与工作空间清空后删除）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23-1、23-2 已完成，本轮做 23 方向第三阶段。补齐三处缺口：工作空间删除此前只删存储记账行不删磁盘文件（且函数签名里没有 `settings`），现删除时先取走全部记账文件的 storage_key 再删行，提交后按 key 清理文件并整体移除空间存储目录，兜底清理中断上传的临时文件；资产删除在版本文件之外显式清理记账文件；资产/项目删除弹窗新增二次确认（待删版本数/任务数、不可恢复提示与必填确认勾选框，未勾选不调用删除接口），工作空间删除弹窗明确磁盘文件一并清除。未归档报 `ARCHIVE_REQUIRED`、版本被引用报 `ASSET_IN_USE`、项目有关联任务报 `PROJECT_IN_USE`、空间未清空报 `WORKSPACE_NOT_EMPTY` 的前置校验与审计记录均不变；无表结构变更，无新增接口，OpenAPI 仍为 152 路径；`live/` 缓存版本统一为 `stage23-3`（102 处 `?v=`）。本地验证通过：后端 `262 passed`（含新增 4 项），前端 `221 pass, 0 fail`（含新增 3 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。未合并 main，未部署，未推送。详见[Stage 23-3 实施与验收](./stage23-3/实施与验收.md)与 [OpenAPI](./stage23-3/openapi.json)。

2026-11-27：在 `lx/stage23-2-workspace-invites` 分支完成 **Stage 23-2（工作空间邀请链接/邀请码闭环）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，23-1 已完成，本轮做 23 方向第二阶段。补齐三处缺口：空间邀请列表按撤销/过期/使用次数算出真实状态（有效/已过期/已用完/已撤销），仅有效邀请可撤销；注册邀请新增管理面（列表含状态、工作空间名与使用人，管理员可主动作废，撤销后注册拒绝并堵住撤销与注册间的竞态）；审核批准时关联邀请已失效返回区分错误码（已撤销/已过期/已用完），申请保持待处理可再拒绝或重新签发；通过邀请码加入时需审核的申请提交后明确提示等待审核。新增迁移 0019（`user_invitations.revoked_at`，升降级往返已测）；新增接口 2 个（注册邀请列表与撤销），OpenAPI 路径 151 → 152；`live/` 缓存版本统一为 `stage23-2`（102 处 `?v=`）。本地验证通过：后端 `258 passed`（含新增 6 项），前端 `218 pass, 0 fail`（含新增 4 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。未合并 main，未部署，未推送。详见[Stage 23-2 实施与验收](./stage23-2/实施与验收.md)与 [OpenAPI](./stage23-2/openapi.json)。

2026-11-27：在 `lx/stage23-1-csp-no-unsafe-inline` 分支完成 **Stage 23-1（CSP 去掉 style-src 'unsafe-inline'）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向已全部完成，本轮按“后续自规划”新开方向 23（功能完善与持续维护）第一阶段，收掉 20B-1 起挂在待办里的 CSP 收紧项。`live/` 原有 10 处行内样式（6 个文件）全部迁走：七处动态进度条改由共享 `progressBar()` 输出 `data-progress`、渲染后经 CSSOM 统一赋值宽度，图表图例颜色改 `data-palette/data-line` 的 CSS 规则（颜色值与 SVG 折线完全一致），节点接入页静态间距改 CSS 类；两个 nginx 模板的 CSP 由 `style-src 'self' 'unsafe-inline'` 收紧为 `style-src 'self'`；新增后端与前端回归测试（`live/` 全量扫描无行内样式、`web/src` 无样式绑定、两模板 CSP 均已收紧）；`live/` 缓存版本统一为 `stage23-1`（102 处 `?v=`）。本地验证通过：后端 `252 passed`（含新增 5 项），前端 `214 pass, 0 fail`（含新增 8 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 23-1 实施与验收](./stage23-1/实施与验收.md)与 [OpenAPI](./stage23-1/openapi.json)。

2026-11-27：在 `lx/stage22-8-settings-keys-audit` 分支完成 **Stage 22-8（设置、密钥、审计与治理页面视觉收尾 + 全站空态与窄屏复核）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），22 方向至此收尾。系统设置用量限制与大模型连接改为数字统计条（连接总数 / 已启用 / 连接成功 / 连接失败），连接名超长省略悬停查看；API 密钥新增按状态计数的统计条（总数 / 启用中 / 已过期 / 已撤销），标识与未关联服务省略悬停查看；审计日志空态按筛选区分，目标列补悬停全文；治理页面空间预算改为数字统计条（已用 / 上限），成员账单姓名账号省略悬停查看；全站其余通用“暂无记录”表格全部改为按页面区分的空态文案（用户 / 用户组、管理端资产与作业目录、数据处理与智能请求、智能辅助请求、计算节点、调用记录、项目实验、参数模板、训练项目与数据集/模型目录），带筛选时显示“没有符合筛选条件的…”；修窄屏真 bug：表格滚动容器补横向滚动规则，三列统计条 700px 以下改两列、数字缩小到 21px；`live/` 缓存版本统一为 `stage22-8`（102 处 `?v=`）。本地验证通过：后端 `247 passed`（无后端改动），前端 `206 pass, 0 fail`（含新增 8 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 22-8 实施与验收](./stage22-8/实施与验收.md)与 [OpenAPI](./stage22-8/openapi.json)。

2026-11-27：在 `lx/stage22-7-data-import-processing` 分支完成 **Stage 22-7（数据导入、数据处理与标注批次列表视觉重做）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），继续自规划方向第七阶段。导入向导新增四步步骤条（基本信息 / 上传文件 / 字段映射 / 样本预览，随草稿状态推进），校验结果改为数字统计条（样本数 / 格式 / 预览条数），样本预览单元格悬停查看全文，字段映射区新增“已映射 X/Y”计数；数据处理与标注批次列表任务名超长省略悬停查看，“已处理”与“已审核”由纯文本改为进度条 + 数值（总数缺失显示“—”不冒充 0%），空态按页面区分（暂无数据处理任务 / 暂无数据增强任务 / 暂无标注批次），带筛选时显示“没有符合筛选条件的任务”；处理详情新增数字统计条（已处理附进度条 / 候选分区 / 已发布版本），处理进度字段追加百分比；样本浏览页新增数字统计条（样本总数 / 标签种类 / 当前页样本数），图像文件名超长省略悬停查看；标注详情标题给出“样本 N / 共 M 个”，队列项悬停显示状态与当前标签，图像样本下方显示源文件名；`live/` 缓存版本统一为 `stage22-7`（101 处 `?v=`）。本地验证通过：后端 `247 passed`（无后端改动），前端 `198 pass, 0 fail`（含新增 7 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 22-7 实施与验收](./stage22-7/实施与验收.md)与 [OpenAPI](./stage22-7/openapi.json)。

2026-11-27：在 `lx/stage22-6-assistant-eval-result` 分支完成 **Stage 22-6（智能辅助、评估对比与结果详情视觉重做）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），继续自规划方向第六阶段。智能辅助列表对象列超长省略悬停查看，模型连接列显示 `名称 · 模型`，过期预览打标记；详情页 Token 用量改为中文数字统计条；日志类结果可能原因改为编号卡片（原因正文 + 日志序号 chips + 排查步骤有序列表，缺失字段有兜底）；参数建议表标签统一为中文（与评估对比页及向导核对页一致）；评估对比表最佳值按方向高亮（准确率/Macro F1 取最高、Loss 类取最低，单模型或无差异时不标注），混淆矩阵对角线加深青绿底纹（抽出共享渲染函数）；评估报告顶部新增总体指标统计条，逐类表 F1 最低类别加琥珀标注并给出最弱类别提示，报告内新增混淆矩阵；`live/` 缓存版本统一为 `stage22-6`（30 个文件 `?v=`）。本地验证通过：后端 `247 passed`（无后端改动），前端 `191 pass, 0 fail`（含新增 5 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 22-6 实施与验收](./stage22-6/实施与验收.md)与 [OpenAPI](./stage22-6/openapi.json)。

2026-11-27：在 `lx/stage22-5-training-list-wizard` 分支完成 **Stage 22-5（训练列表、向导与作业筛选视觉重做）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），继续自规划方向第五阶段。训练列表新增数据集与耗时两列（与工作台最近训练表一致：数据集显示 `名称 / vN`，耗时已结束显示总耗时、运行中显示“进行中 X”），名称列超长省略悬停查看，耗时单元格不换行；空态文案按类型区分（暂无训练任务 / 暂无评估任务 / 暂无在线服务），带筛选条件时显示“没有符合筛选条件的任务”；筛选工具栏在任务类型与状态之外新增设备、训练项目与排序三项（复用后端 `/jobs` 已有参数，无后端改动）；训练向导步骤条已完成步骤显示对勾，核对页参数改用中文标签（修了直接裸露 `epochs` 等配置键的问题），数据集行补样本数；`live/` 缓存版本统一为 `stage22-5`（101 处 `?v=`）。本地验证通过：后端 `247 passed`（含新增 1 项项目/排序筛选测试），前端 `186 pass, 0 fail`（含新增 6 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 22-5 实施与验收](./stage22-5/实施与验收.md)与 [OpenAPI](./stage22-5/openapi.json)。

2026-11-27：在 `lx/stage22-4-data-model-catalog` 分支完成 **Stage 22-4（数据与模型目录视觉重做）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），继续自规划方向第四阶段。数据集目录由纯表格改为与模型一致的默认卡片视图（最新版本 / 样本数 / 格式 / 状态，卡片底部“查看详情”+“导入版本”），并新增与模型同款的卡片/列表视图切换（修了模型切换链接硬编码 `#/models` 的问题，现按 kind 生成）；空目录文案区分（“暂无数据集”/“暂无模型”），模型卡片补“已归档”徽标；资产详情新增三列大数字汇总条（数据集：最新版本 / 样本总数 / 文件总大小；模型：版本数 / 最新版本 / 最新状态），新增 `formatSize()`（B/KiB/MiB 分档，缺失返回“—”），并修了数据集版本表两处缺失字段问题（`format` 为 null 时 `toUpperCase()` 崩溃、`size_bytes` 为 null 算出 NaN KiB）与超长文件名撑宽表格（改省略 + 悬停查看）；管理端数据集列表“内容”列由静态“版本管理”改为有最新版本时显示 `vN · M 样本`；标注工作台队列状态由被 CSS 隐藏的徽标改为状态圆点（草稿灰 / 待审核琥珀 / 已通过深青绿 / 已退回红 / 未标注空心，悬停显示中文状态），表头“已审核 X/Y”改为带进度条，另修 `result` 无 `state` 的样本输出 `undefined` 的问题；`live/` 缓存版本统一为 `stage22-4`（102 处 `?v=`）。本地验证通过：后端 `246 passed`（无后端改动），前端 `180 pass, 0 fail`（含新增 9 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 22-4 实施与验收](./stage22-4/实施与验收.md)与 [OpenAPI](./stage22-4/openapi.json)。

2026-11-27：在 `lx/stage22-3-resource-admin-visual` 分支完成 **Stage 22-3（资源监控与管理端视觉重做）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），继续自规划方向第三阶段。资源监控“设备”页与节点详情“设备清单”由表格改为三列设备卡片网格（1100px 以下两列，700px 以下一列），每张卡片含设备名与状态徽标、类型/用途/运行时标签、硬件标识、利用率数值与进度条、显存/内存用量（已用 / 总量 MiB）与进度条，未上报时显示“—”不冒充 0%；统计面板“文件与执行”由字段表改为四列大数字统计条（文件存储、GPU 预留时长、已确认智能请求、已报告 Token），失败阶段明细保留；用户表“用户”与“账号”合并为一列（姓名加粗一行、账号灰色小字第二行），5 个操作按钮全部保留；700px 以下工具栏改为纵向排布，筛选下拉框两两一行均匀分布，刷新按钮不再拉满整行；`live/` 缓存版本统一为 `stage22-3`（102 处 `?v=`）。本地验证通过：后端 `246 passed`（无后端改动），前端 `171 pass, 0 fail`（含新增 5 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 22-3 实施与验收](./stage22-3/实施与验收.md)与 [OpenAPI](./stage22-3/openapi.json)。

2026-11-27：在 `lx/stage22-2-dashboard-job-detail` 分支完成 **Stage 22-2（工作台与训练详情视觉重做）**：21-1 仍被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），继续自规划方向第二阶段。工作台指标区运行中/排队中数量大于 0 时数值以主色强调，最近训练表新增数据集与耗时列（已结束显示总耗时如“1小时0分”，运行中显示“进行中 1分30秒”）；训练详情修了执行信息卡头状态徽标后重复一段纯文本状态的问题，执行信息新增已用时长与当前进度（第 3 / 10 轮，附进度条），执行结果改用三列大数字统计条（准确率 / Macro F1 / Loss），指标图头下方给出最新一轮各曲线数值，日志页增加行数统计（共 N 行，搜索后附匹配数）；后端只为耗时列补数据——`job_summary` 增加 `started_at` / `finished_at`，无表结构变更，无新增接口；`live/` 缓存版本统一为 `stage22-2`（101 处 `?v=`）。本地验证通过：后端 `246 passed`（基线 245 项 + 新增 1 项），前端 `166 pass, 0 fail`（含新增 6 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。未合并 main，未部署，未推送。详见[Stage 22-2 实施与验收](./stage22-2/实施与验收.md)与 [OpenAPI](./stage22-2/openapi.json)。

2026-11-27：在 `lx/stage22-1-frontend-display-walk` 分支完成 **Stage 22-1（前端显示走查：全页面渲染器对抗数据回归）**：21-1 本轮被阻塞（本机无 GPU/torch/Qwen 权重缓存、无视觉供应商连接，用户本机 CPU/GPU 暂停），改做自规划方向第一阶段。新增走查测试 10 项，用注入字符、200 字符无断行串、缺失可选字段渲染 live/ 全部页面渲染器与 24 种弹窗，断言不抛错、不泄露 `undefined`/`NaN`、不输出未转义标记；走查发现并修复 4 处真问题——训练详情无标签混淆矩阵崩溃、资源监控未上报指标设备与未探测节点崩溃、智能辅助日志原因缺失字段崩溃及预览上限缺失、数据集目录格式缺失崩溃（均为防御性兜底，后端当前写入路径均保证字段存在）；`live/` 缓存版本统一为 `stage22-1`（102 处 `?v=`）。本地验证通过：后端 `245 passed`（无后端改动），前端 `160 pass, 0 fail`（含新增 10 项），`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 22-1 实施与验收](./stage22-1/实施与验收.md)与 [OpenAPI](./stage22-1/openapi.json)。

2026-11-27：在 `lx/stage20b-2-rewrite-stats-pg-concurrency` 分支完成 **Stage 20B-2 重写（资源统计精细化与 PostgreSQL 并发/多物理机验收）**：按 Smith 2026-11-26 决定丢弃原版（b063614）后在 21a/22a 基线（e16a7cf）上重写，内容与原版等价。`executions` 新增 `started_at`（迁移 0018，原 0017 号已被 21a 占用，历史行用 `created_at` 回填，Worker 上报 started 事件时记录），GPU 预留时长改为 `min(now, finished_at) - started_at` 动态累加，运行中执行也计入，统计面板标签由「已结束 GPU 预留」改为「GPU 预留时长」；创建人/起止日期筛选穿透到资源汇总面板（GPU 预留、文件存储、智能请求三块都按同一口径收窄）；Worker 探针优先读 cgroup v2（`memory.max`/`memory.current`、`cpu.max`），`full_probe()` 新增 `memory_limit_mb`/`memory_used_mb`/`cpu_quota`，区分容器配额与宿主机总量；CI 新增 `Backend PostgreSQL Tests` 工作流（`postgres:17` 服务跑全量 pytest）；`live/` 缓存版本统一为 `stage20b-2-rewrite`（101 处 `?v=`）；另修原版测试一处时区 bug（`date.today()` 在 UTC 测试机 00:00–08:00 CST 会算错“明天”，改为按业务时区算）。本地验证通过：后端 `245 passed`（含新增 10 项），前端 `150 pass, 0 fail`（含新增 1 项）。新增迁移 0018，无新增接口。未合并 main，未部署。详见[Stage 20B-2 重写实施与验收](./stage20b-2-rewrite/实施与验收.md)与 [OpenAPI](./stage20b-2-rewrite/openapi.json)。

2026-11-26：在 `lx/stage20b-3-repo-governance-docs` 分支完成 **Stage 20B-3（仓库治理与文档整理）**：`scripts/` 只保留 29 个核心运维与验证脚本，移出 64 个历史答辩 PPT / Word / SRS / 用例活动图 / 设计评审对照图一次性脚本（7862 行），完整内容归档在本地分支 `archive/scripts-defense-docs-2026-11-26`（以 Stage 22A 基线 `e16a7cf` 建分支）；补齐仓库根 `README.md`（快速启动、环境变量、测试命令、线上部署架构图、文档索引、脚本治理与开发约定）。本地验证通过：后端 `235 passed`，前端 `149 pass, 0 fail`，`frontend/web` 的 `npm run build`（vue-tsc + vite）通过。无表结构变更，无新增接口。未合并 main，未部署，未推送。详见[Stage 20B-3 实施与验收](./stage20b-3/实施与验收.md)与 [OpenAPI](./stage20b-3/openapi.json)。

2026-11-26：在 `lx/stage22a-vue3-vite-migration` 分支完成 **Stage 22A（前端 Vue 3 + TypeScript + Vite 工程化迁移）**：新建 `frontend/web/`（Vue 3.5 + TypeScript 5.7 + Vite 6），完整复用既有 `frontend/styles/*` 与 `frontend/live/*.css` 保持界面视觉与交互零改动，接入强类型 `ApiClient`、Vue 3 `reactive` 状态管理与 `AppShell`/`AuthView`/`ModalHost`/`ToastHost`/`WorkspaceContent` SFC 外壳，同时保留 `frontend/live/` 支持 5 人团队按页面渐进替换为纯 Vue SFC；后端 `web.py` 优先提供 `frontend/web/dist/` 并自动回退 `frontend/live/`，Docker 升级为 `node:22-alpine` + Python 多阶段构建。详见 [frontend/web/README.md](../frontend/web/README.md)。

2026-11-26：在 `lx/stage21a-workspace-governance` 分支完成 **Stage 21A（空间自治与团队治理）**：落地 4 级空间角色（`admin`/`editor`/`annotator`/`viewer`）、空间所有权转让、本空间已归属设备策略自治、空间总预算与成员子配额三层收敛及空间成员用量账单（schema `0017_workspace_governance`）。本地验证通过：后端 `234 passed, 1 skipped`，前端 `149 pass, 0 fail`。详见[Stage 21A 实施与验收](./stage21/实施与验收.md) 与 [OpenAPI](./stage21/openapi.json)。

2026-11-26：在 `lx/stage20b-1-deploy-hardening` 分支完成 **Stage 20B-1（网关、数据库与容器运行时安全加固）**：db/gateway 加 `cap_drop: [ALL]` + `no-new-privileges`（按需保留 CHOWN/DAC_OVERRIDE/SETGID/SETUID 最小能力），网关加 healthcheck（wget 探 `/readyz`），网关镜像固定 `nginx:1.30.8-alpine`；nginx 配置改为 `.template` 并经 envsubst 渲染，统一加 HSTS（仅 HTTPS）、nosniff、`X-Frame-Options: DENY`、Referrer-Policy 与同源 CSP，证书路径改读 `${TLS_IP}`；旧 IP `47.93.115.188` 从现网配置与脚本中清除，改为 `.env` 的 `PUBLIC_HOST`/`TLS_IP`；certbot 镜像固定 `v5.10.0`；修了 `backup.sh` 备份错库的 bug（原先实际备份的是 postgres 维护库，现改为应用库 `model_platform`），备份新增 `tables.txt`/`backup.json` 清单，新建 `restore.sh`（摘要校验、停服务恢复、逐表行数与存储文件数校验、通过后才重启）与每日 03:00 备份 systemd 定时器；本地桩演练备份→恢复全流程通过，真实 PostgreSQL 演练待预发环境。本地验证通过：后端 `233 passed`（含新增 18 项部署加固回归测试），前端 `147 pass, 0 fail`。无表结构变更，无新增接口。未合并 main，未部署。详见[Stage 20B-1 实施与验收](./stage20b-1/实施与验收.md)与 [OpenAPI](./stage20b-1/openapi.json)。

2026-11-26：在 `lx/stage20a-2-live-decoupling` 分支完成 **Stage 20A-2（前端 live/ 结构解耦与安全升级）**：live 所需通用原语（shell、NAV_GROUPS、ADMIN_NAV、badge、icon 等）与状态提示内聚迁移到 `frontend/live/ui/`，live/ 不再引用原型目录 `frontend/js/`；缓存版本标识统一为单一构建常量 `ASSET_VERSION = "stage20a-2"`（live/ 内 101 处 `?v=` 全一致，测试逐文件校验）；events.js 点击分发改为 `clickPipeline` + `Map<action, handler>`（25 个单动作）、dialogs.js 的 `||` 串联改为 `DIALOG_RENDERERS`（50 个 kind 到 10 个渲染函数）；`table()` 默认转义单元格、`raw()` 标记受信任片段，17 个调用点同步迁移。纯前端，无后端改动、无表结构变更、无新增接口。本地验证通过：后端 `215 passed`，前端 `147 pass, 0 fail`（含新增 5 项）。未合并 main，未部署。详见[Stage 20A-2 实施与验收](./stage20a-2/实施与验收.md)与 [OpenAPI](./stage20a-2/openapi.json)。

2026-11-26：在 `lx/stage20a-1-password-reset` 分支完成 **Stage 20A-1（用户自助找回/重置密码）**：管理员签发一次性密码重置码（8 位无歧义字符，库里只存 HMAC-SHA-256 摘要，15 分钟过期、一次有效，签发新码作废旧码），用户在登录页“忘记密码”入口凭码自助重置并自动踢出全部历史会话；猜码失败计入账号维度限流桶（15 次锁定 15 分钟），已锁定账号仍可凭有效码重置解锁；迁移 `0016_password_reset_codes`（新建 `password_reset_codes` 表）。本地验证通过：后端 `215 passed`（含新增 8 项），前端 `142 pass, 0 fail`（含新增 2 项）。新增 2 个接口（OpenAPI 146 路径）。未合并 main，未部署。详见[Stage 20A-1 实施与验收](./stage20a-1/实施与验收.md)与 [OpenAPI](./stage20a-1/openapi.json)。

2026-11-26：在 `lx/stage19b-3-login-rate-limit` 分支完成 **Stage 19B-3（登录限流与上传产物并发保护）**：登录在原有“账号+IP”单桶之外新增纯账号维度全局滑动计数（15 分钟窗口内累计 15 次失败锁定账号 15 分钟，轮换 IP 无法绕过）；`store_artifact()` 写盘前用条件更新抢占式声明产物槽位，并发双传只有一个成功、另一个按幂等/冲突处理不覆盖已落盘产物，写盘改用唯一临时文件名 `{execution.id}.{uuid}.zip`；迁移 `0015_login_account_rate_limit`（`login_attempts` 新增 `window_started_at`）。本地验证通过：后端 `207 passed`（含新增 4 项），前端 `140 pass, 0 fail`。无新增接口。未合并 main，未部署。详见[Stage 19B-3 实施与验收](./stage19b-3/实施与验收.md)与 [OpenAPI](./stage19b-3/openapi.json)。

2026-11-26：在 `lx/stage19b-2-streaming-data` 分支完成 **Stage 19B-2（训练数据流式读取与单样本/空验证集零分母防护）**：新增 `iter_rows()` 生成器按行流式读 CSV/JSONL、图像只存原始字节并按需解码像素；单样本非分类任务全进训练集、空数据集明确报错、`scores()` 空标签/空验证集不再除零；`Classifier.train()` 空验证集跳过验证前向、`val_loss` 置 0。本地验证通过：后端 `203 passed`（含新增 12 项），前端 `140 pass, 0 fail`。无表结构变更，无新增接口。未合并 main，未部署。详见[Stage 19B-2 实施与验收](./stage19b-2/实施与验收.md)与 [OpenAPI](./stage19b-2/openapi.json)。

2026-11-26：在 `lx/stage19b-1-credential-rotation` 分支完成 **Stage 19B-1（Worker 凭据轮换与已撤销节点防复活）**：已撤销节点重新接入时新建独立节点、旧记录保留，`machine_id` / `installation_id` 改为仅未撤销节点部分唯一；新增 `POST /api/worker/v1/rotate-credential` 与 `credential_expires_at`（默认 90 天），Worker 临期自动轮换并原子写入 `node-state.json`；迁移 `0014_worker_credential`。本地验证通过：后端 `191 passed`，前端 `140 pass, 0 fail`。未合并 main，未部署。详见[Stage 19B-1 实施与验收](./stage19/实施与验收.md)与 [OpenAPI](./stage19/openapi.json)。

2026-11-26：在 `lx/stage19a-worker-deploy-hardening` 分支完成 **Stage 19A（SSRF IP 钉扎、CSRF 服务端密钥分离、Worker 异常处理与超时清理、部署备份加固）**。本地验证通过：后端 `187 passed, 1 skipped`，前端 `140 pass, 0 fail`。详见[Stage 19A 实施与验收](./stage19/实施与验收.md)。

2026-11-26：在 `lx/stage18b-hardening-sessions` 分支完成 **Stage 18B（状态机/租约/并发加固、多端会话管理与管理端作业行内操作）**：新增过期租约自动回收、执行结案源状态白名单、`lock_batch`/`publish_operation` 乐观锁条件更新、`retry` 幂等、多端会话查看与踢出、管理端作业列表行内停止/重跑。本地验证通过：后端 `184 passed, 1 skipped`，前端 `140 pass, 0 fail`。详见[Stage 18B 实施与验收](./stage18/实施与验收.md) 与 [OpenAPI](./stage18/openapi.json)。

2026-11-26：在 `lx/stage17a-storage-weights` 分支完成 **Stage 17A（统一默认文件存储与受控权重上传）** 与 **Stage 18A（控制台补齐与 `/assistants` 导航修复）**：新增模型受控权重上传（schema `0013_model_storage`）、工作台待处理事项、用户空间个人任务、数据集校验报告与标签分布、统计面板创建人/时间筛选。本地验证通过：后端 `181 passed, 1 skipped`，前端 `138 pass, 0 fail`。详见[Stage 17A/18A 实施与验收](./stage17/实施与验收.md) 与 [OpenAPI](./stage17/openapi.json)。

2026-11-01：[项目、筛选与报告](./stage15/运行与验收.md)已发布20261101-15a，缓存stage15-1、schema0011_console。项目维护和归档、资产及管理组合筛选、密钥调用统计和期限、审计/评估导出均接入页面。164项镜像后端、126项前端、132项布局、5项PG迁移与并发检查通过；云端CPU真实训练/评估/服务和公网12项认证查询通过。[实拍与记录](./stage15/previews/ReadMe.md)、[继续入口](./stage15/实施进度与交接.md)。原记录保留，本机CPU/GPU继续暂停。

2026-10-31：[一期补齐](./stage14/运行与验收.md)已发布20261031-14a1，缓存stage14-2、schema0010_templates。数据字段映射、共享参数模板接入真实页面，157项后端、120项前端及125项布局/状态检查通过；云端CPU完成页面提交训练、成员标注清洗协作、断网恢复，服务器内备份恢复通过。[截图与结果](./stage14/previews/ReadMe.md)、[20菜单未完成细项](./stage14/功能复核与后续批次.md)。本机CPU/GPU继续暂停。

2026-10-31：[B5b资源治理](./stage13/B5b运行与验收.md)已上线20261031-13b5b，schema0009_audit、缓存stage13-5b。设备授权、历史监控、组共享预算、真实文件计量、归档、执行核查、管理作业标签和失败审计均接入页面。145项后端、115项前端、105项三视口布局、5项PostgreSQL迁移及竞争检查通过；[实拍](./stage13/previews/b5b/ReadMe.md)。本机GPU继续暂停，Qwen本轮回归和其他剩余事项已明确列出。[Claude Code排查](./stage13/ClaudeCode调用排查.md)完成可用路由和Read/Write核验。

2026-10-31：[B5a结果与服务](./stage13/B5a运行与验收.md)已上线20261031-13b5a，schema0007_results、缓存stage13-5a。121项镜像内后端、109项云端前端、24项浏览器布局及双容器CPU真实闭环通过。[实拍](./stage13/previews/b5a/ReadMe.md)。B5b资源治理仍在实现，本机资源暂停不变；当前OpenAPI对应线上版本。

2026-10-31：[B4智能辅助复核与验收](./stage13/B4代码复核与验收.md)已发布至20261031-13b4，schema0006_assist，缓存stage13-4。支持空间授权、固定外发预览、智能标注/参数/日志及人工采纳；111项后端、104项前端、24项云端浏览器布局和三项真实合成调用通过。[页面实拍](./stage13/previews/b4/ReadMe.md)。本机保持暂停；各空间外发默认关闭，B5/B6仍在后续范围。

2026-10-29：[B3数据与人工标注](./stage13/B3运行与验收.md)已上线20261029-13b3，缓存stage13-3、schema0005_data。完成人工标注复核发布、真实清洗/划分/增强、样本图像浏览下载和版本来源；Windows94个后端用例、Linux94项、前端100项及本地/公网各72项布局通过。“数据工作流示例”空间可演示；节点心跳正常，保持用户的暂停接收设置。[实拍](./stage13/previews/b3/ReadMe.md)。三项智能辅助按[B4设计](./stage13/B4智能辅助设计.md)继续实现。

2026-10-29：[B2管理与模型连接](./stage13/实施进度与交接.md)已上线20261029-13b2，数据库0004_admin。全平台管理、真实系统设置、模型连接、内部邀请注册、密码/成员管理完成；83项Windows及83项Linux后端、95项前端、本地/公网各51项布局检查通过。Worker在线及旧记录保留；[实拍](./stage13/previews/b2/ReadMe.md)。实际外部模型调用与数据/智能流程继续实施。

2026-10-29：[基础功能与完整界面恢复](./stage13/ReadMe.md)计划已确认，B1已上线：工作台、模型/项目目录、数据导入、四步训练、任务标签页和日志下载。70项Windows及70项Linux后端、91项前端、本地和云端各33项布局检查通过；[实施与剩余工作](./stage13/实施进度与交接.md)、[页面实拍](./stage13/previews/ReadMe.md)。当前发布为20261029-13b1，数据结构保持0003_jobs；其余20菜单补齐与三项智能辅助继续实施。

2026-10-29：[Linux 部署与本机 GPU 联调](./stage12/ReadMe.md)已完成。入口 `https://47.93.115.188:5488`，Docker Compose与PostgreSQL17.11已运行，RTX4060完成一次真实图像分类CUDA训练及产物回传。63项Windows及63项Linux后端、85项前端、12项浏览器检查通过。[运行与账号说明](./stage12/运行与验收.md)。云端Worker在线，旧本机失联占用保留；备份按用户决定仅留服务器。缓存调度及OSS优化后续再做。

2026-10-29：[Qwen推理任务约束修复](./stage11/ReadMe.md)已生效。部署保存指令和标签，Worker解码只允许指定标签，服务端再次校验；普通生成保留。原问题输入已返回spam，128条正文调用复测正确126条，历史实验结果不改。当前完整API见[stage11 OpenAPI](./stage11/openapi.json)。

2026-10-29：[公开数据真实实验](./stage10/ReadMe.md)已完成。SMS去重5159条、Fashion-MNIST开发6000/测试2000张、Qwen开发512/测试128条；五次训练、五次独立评估和128条实际生成均完成。结果、基线、混淆矩阵、来源摘要与44条曲线记录见[实验结果](./stage10/实验结果.md)。全部记录已进入原空间“公开数据实验”项目。

2026-10-29：[资源接入](./stage7/ReadMe.md)、[训练执行](./stage8/ReadMe.md)、[评估与部署](./stage9/ReadMe.md)已接入真实界面。文本CPU、图像GPU、Qwen3-0.6B LoRA均通过训练、评估与推理验证；分类API KEY调用与撤销通过。27项浏览器页面检查和页面提交训练、部署、调用通过。应用8000已迁移并保留原数据，预置资产和本机Worker已在“北航跳动”空间准备，当前使用见[运行与验收](./stage8/运行与验收.md)，剩余功能见[待办](./后续功能待办.md)。

2026-10-28，真实前端已接入已完成后端，入口 `http://127.0.0.1:8000/`。支持页面首次设置、登录、空间/成员、用户/组、权限、模型、数据上传/版本/预览及审计；43 项后端、73 项前端测试和浏览器验收通过。[使用与演示](./stage6/运行与演示.md)、[实际进度](./stage6/实施进度.md)、[界面实拍](./stage6/previews/ReadMe.md)。8765 原型独立保留，训练和三项智能辅助待后续接入。

2026-10-28：真实版本 M1 基础后端已实现，包含身份、工作空间、用户组与个人权限、模型登记、数据集及真实 CSV/JSONL 版本上传，共 30 个操作；34 项后端测试和 63 项原有前端测试通过。后端 8000 与原型 8765 独立运行，尚未联调页面；训练、推理和智能辅助仍在后续批次。设计、API、测试、运行及交接统一见[stage5 索引](./stage5/ReadMe.md)。以下保留前期阶段材料进展。

截至 2026 年 10 月 13 日，仓库已有调研计划、两组及合并报告、67 份问卷统计、用户故事、SRS 和核心模块 SPEC。当前合并答辩稿采用[建模优化兼容修正版](<./需求调研+需求分析/ppt/大模型集成训练平台_需求调研与建模答辩_建模优化版_兼容修正版.pptx>)，沿用北航模板，保留原合并稿的调研部分，已通过本机 PowerPoint 关闭自动修复的打开检查。第二阶段明确为需求建模，按“总体需求分解、核心模型成果、非功能需求”组织，建模为 7 页主讲、1 页 AI 填写和 3 页隐藏原图。类图、时序图留给第三阶段需求分析；原 SRS、SPEC 和模型源文件仍需同步。完整资料与使用方法见[阶段资料索引](<./需求调研+需求分析/ReadMe.md>)。

第二阶段纯前端演示版已完成登录注册、二级导航、用户端十二个主要页面及管理端八个页面，支持 Qwen2.5-0.5B-Instruct 微调配置、用户组与个人权限、GPU 节点模拟接入等流程。前端尚未连接真实后端。团队已确认独立训练 Demo 使用 Qwen3-0.6B、PyTorch、Transformers、LoRA 和小规模指令数据；多来源资源统一接入尚待实现。算力方案按本次确认的 4 张 RTX 4060、1 张 RTX 4070 笔记本 GPU，以及 CPU、实验室服务器和云平台展开。现有需求文档与模型仍需同版同步，未实现功能集中记录在[后续功能待办](./后续功能待办.md)。

## 文档索引

### 真实版本开发规划

- [Stage 21A 空间自治与团队治理设计](./stage21/空间自治与团队治理设计.md)：4 级空间角色、所有权转让、空间总预算与成员子配额、本空间设备自治及空间用量账单（规划中）。
- [真实版本开发路线图](./真实版本开发路线图.md)：模块化控制端下的分批任务、依赖、一期验收和后续扩展。
- [Stage 16 索引](./stage16/ReadMe.md) · [16A 本地验收](./stage16/运行与验收.md) · [16B 本地验收](./stage16/16B本地验收.md)：设备用途、队列筛选、资源汇总和排队原因。旧云服务器已停止。
- [项目维护、筛选与报告](./stage15/ReadMe.md)：项目资料/归档、管理筛选、密钥使用与期限、审计/评估导出；已完成云端验收并发布。
- [一期补齐与完整流程验收](./stage14/ReadMe.md)：列映射、可复用参数模板、真实业务链及原型差异复核；先设计后实现，当前进度见该阶段交接。
- [基础功能补齐与完整界面恢复](./stage13/ReadMe.md)：20个菜单逐项范围、原型差异、三项智能辅助、界面/API/数据与验收；B1～B3已发布，B4～B6继续实施。
- [Linux 部署与本机 GPU 联调](./stage12/ReadMe.md)：部署包、远端环境、文件归属、独立节点身份和一次真实 GPU 训练验收。
- [服务器监控](./stage12/服务器监控.md)：云服务器Komari Agent、自动注册、禁用远程控制与停用恢复。

- [资源接入与训练部署建设](./stage7/ReadMe.md)：本轮连续实施资源接入、文件传输、真实训练、评估及推理，含总体计划、先行协议和实施交接。

- [真实前端联调](./stage6/ReadMe.md)：已接入可操作页面，包含初始化、登录、工作空间/成员、用户/组、模型和数据版本、样本与审计；含设计、运行、验收、实拍及交接。

- [一期工程总索引](./stage5/ReadMe.md)：架构与决策、数据模型、API、Worker/辅助协议、开发规范、验收、运行与实施交接；开始后续实现前先读本页及当前进度。
- [真实版本建设计划与后续 Agents 设计](./后续功能待办.md#2026-10-28-真实版本建设计划)：2026-10-28，内部团队定位、当前代码差异、一期三项智能辅助、页面资产维护、模型连接与外发规则、模块化后端/Worker、开发里程碑，以及工具、记忆、授权、编排和评估边界。正式 SRS、程序和界面本轮未修改。

### 需求调研最新修订

- [需求调研报告完整修订版](<./需求调研+需求建模/初步提交材料/需求调研报告_完整修订版_20261020.docx>)：2026-10-20，按完整业务流程组织原型验证，新增GPU接入与计算执行可行性分析；保留原平台调查和67份问卷统计。
- [原型验证截图与实测记录](<./需求调研+需求建模/初步提交材料/支撑材料/原型验证_20261020/ReadMe.md>)：16张原业务截图、6张计算执行程序实拍、15项真实接入检查，附原ZIP校验、验证范围和复用方法。

### 最终提交配套表单

2026-10-20，调研与建模成果各保留版本记录和 AI 使用声明两份 Word。版本记录原样提取相应正式 Word 中的非空记录；AI 声明采用简洁正文，不设置提示词摘录或填写栏。两份自查表已按要求删除，可从 D 盘 `model-training-demo/submission-forms-simplify-20261020/backup` 恢复；现有 ZIP 尚未更新。

- 需求调研：[版本记录](<./需求调研+需求建模/最终提交材料/5组-王者灵宝的coding能力也不是不行-需求调研成果/5组-王者灵宝的coding能力也不是不行-需求调研成果/01-修改说明与版本记录表-5组-王者灵宝的coding能力也不是不行.docx>)、[AI 使用声明](<./需求调研+需求建模/最终提交材料/5组-王者灵宝的coding能力也不是不行-需求调研成果/5组-王者灵宝的coding能力也不是不行-需求调研成果/01-AI使用声明-5组-王者灵宝的coding能力也不是不行.docx>)。
- 需求建模：[版本记录](<./需求调研+需求建模/最终提交材料/5组-王者灵宝的coding能力也不是不行-需求建模成果/5组-王者灵宝的coding能力也不是不行-需求建模成果/02-修改说明与版本记录表-5组-王者灵宝的coding能力也不是不行.docx>)、[AI 使用声明](<./需求调研+需求建模/最终提交材料/5组-王者灵宝的coding能力也不是不行-需求建模成果/5组-王者灵宝的coding能力也不是不行-需求建模成果/02-AI使用声明-5组-王者灵宝的coding能力也不是不行.docx>)。

### 需求分析阶段协作

- [需求分析课堂展示与提交要求](<./需求分析/《软件系统分析与设计》课程实践作业课堂展示与提交要求（需求分析).pdf>)、[同名 Markdown 阅读版](<./需求分析/《软件系统分析与设计》课程实践作业课堂展示与提交要求（需求分析).md>)：2026-10-21 新增。文件列明 10 月 28 日研讨、课前一天预提交、12 分钟汇报与 3 分钟问答，终稿建议于 11 月 3 日 24:00 前提交，具体以教学平台通知为准；业务示例为学术成果分享平台，本项目业务范围结合平台任务书核对。现有分工本轮未改。
- [成员 C 业务对象与核心类模型交付](./需求分析/成员C_业务对象与类模型/ReadMe.md)：二十个核心对象、十九个辅助对象、MB01 单张黑白类图及二十七条关系说明；交付十页 Word、Markdown、400 DPI PNG、矢量 PDF、TikZ/PlantUML 和完整模型数据。[可转发交付包](./需求分析/成员C_交付包_20261019.zip)。已完成原生 Word 与逐页检查；CodeArts 原生工程尚未生成，成员人工评审记录待补。
- [需求分析分工与时间安排](./需求分析/分工.md)：2026-10-19 更新。沿用 A、B、C、D、E、F、H、I、J、K 十人代号，分 Part 1 前序修订和 Part 2 需求分析；明确前两阶段拆分材料、1 张核心类图及 18 张顺序图、两组及合并报告、PPT、汇报和中间交接节点。
- [业务模型与用例交互模型统一约定](./需求分析/业务模型与用例交互模型统一约定.md)：共同对象与类关系、权限和配额、状态与消息、各图内容、故障处理、45 个原用例追踪及新增条目；C/D/E/F 与报告作者共用。当前为协作约定，正式图与报告尚待制作。
- [旧分工与统一口径](<./需求调研+需求建模/需求分析阶段分工与统一口径.md>)：历史 V0.2，保留数字编号和旧图目供追溯；本轮不再采用。

### 架构调研与设计阶段协作

- [阶段入口](./架构调研和设计/ReadMe.md)：课堂要求、课件、项目任务书和阅读版索引。
- [系统架构设计说明书](./架构调研和设计/系统架构设计说明书.md) · [PDF](./架构调研和设计/系统架构设计说明书.pdf)：四层逻辑、模块化控制端、Worker、文件存储、部署拓扑、质量目标与 ADR。
- [阶段任务与十人分工](./架构调研和设计/阶段任务与十人分工.md)列出必做事项、共用图、两组文字稿及提交安排。
- [架构调研执行提纲](./架构调研和设计/架构调研执行提纲.md)说明四类调研的对象、负责人和报告产出。
- [两组架构统一口径与方案草案](./架构调研和设计/两组架构统一口径与方案草案.md)说明模块化控制端、微服务对照、四层职责、部署、需求追踪与质量场景。
- [作业 4 要求覆盖核对](./架构调研和设计/作业4要求覆盖核对.md)列出已补设计、正式提交物和待验证事项。

### 前端视觉方案审查

- [完整前端原型压缩包](../大模型集成训练平台_前端原型_20261019.zip)：仅包含当前原型入口、JavaScript、样式和 README；不包含调研文档、测试或历史样例。[包内启动说明源稿](./stage4/原型打包README.md)。
- [已采用的云管控型模板提示词](./stage4/云管控型前端模板提示词.md)：完整原型采用深青绿主操作、中性色主体、蓝色详情入口及 8/6/10px 圆角；页面按内容分区，列表状态使用圆形图标。
- [完整原型迁移与运行说明](./stage4/前端迁移与运行说明.md)：2026-10-15 已迁移用户端、管理端、登录注册、详情、训练向导和配置弹窗；完整入口使用 8765 端口。
- [主体样式参考图片](./stage4/参考图片/ReadMe.md)：用户提供的三张 PAI/DSW 图片、同名阅读说明与本轮采用的组件规则。
- [云控制台组件设计方案](./stage3/云控制台组件设计方案.md)：以紧凑云管控为主，提供六组主色、自选色、三种状态和三档边角；主面板分区，并定义字体、控件、表格、弹窗及现有页面迁移规则。
- [云控制台样例与实拍图片](./stage3/云控制台样例运行说明.md)：八个审查页面、组件与弹窗对照、启动方法及浏览器检查记录；入口为 8766 端口下的 `cloud-v2`。
- [四套视觉样例设计](./stage3/前端样例设计.md)：A 精密工作台、B 实验室、C 资源控制台、D 轻量工作室，共十二个独立页面。
- [运行、图片与审查说明](./stage3/运行与审查说明.md)：选择入口、三张对照图、浏览器检查记录与启动方法；现有原型保留，样例单独使用 8766 端口。

### 任务书

- [《大模型集成训练平台》实践任务书（Markdown）](<./题目要求/《软件系统分析与设计》实践任务书（二）大模型集成训练平台-v1.md>)；[原 PDF](<./题目要求/《软件系统分析与设计》实践任务书（二）大模型集成训练平台-v1.pdf>)

### 平台调研

- [华为云 ModelArts](<./调研结果/华为云ModelArts调研.md>)；[原 PDF](<./调研结果/华为云ModelArts调研.pdf>)
- [阿里云 PAI](<./调研结果/阿里云PAI平台调研.md>)；[原 PDF](<./调研结果/阿里云PAI平台调研.pdf>)
- [腾讯云 TI-ONE](<./调研结果/腾讯云大模型集成训练平台调研报告(1).md>)；[原 PDF](<./调研结果/腾讯云大模型集成训练平台调研报告(1).pdf>)
- [百度智能云飞桨 BML 报告](<./调研结果/飞帆BML 全功能AI开发平台调研报告.md>)；[原 PDF](<./调研结果/飞帆BML 全功能AI开发平台调研报告.pdf>)
- [百度智能云 BML 补充笔记](<./调研结果/调研(2).md>)
- [Amazon SageMaker AI](<./调研结果/Amazon_SageMaker_AI_调研报告.md>)；[原 PDF](<./调研结果/Amazon_SageMaker_AI_调研报告.pdf>)
- [Azure Machine Learning](<./调研结果/Azure调研报告.md>)；[原 PDF](<./调研结果/Azure调研报告.pdf>)
- [Kubeflow](<./调研结果/Kubeflow 调研.md>)
- [Crater](<./调研结果/Crater.md>)

- [八个平台／项目标识合成图](<./需求调研+需求分析/图片/平台标识/ReadMe.md>)：3200 × 1800 横屏白底与透明底 PNG，保留八份原始标识与官方来源记录。

### 前端布局参考

- [固定侧边栏设计要求](<./前端设计要求/前端提示词.txt>)
- [离线示例说明](<./前端设计要求/sidebar-fixed-showcase/README.md>)、[离线示例页面](<./前端设计要求/sidebar-fixed-showcase/index.html>)、[原始压缩包](<./前端设计要求/sidebar-fixed-showcase.zip>)

前端参考资料描述了固定侧边栏、移动端抽屉、导航状态等布局规则。当前完整原型采用云管控型框架、深青绿主操作和中性色主体，早期视觉方案保留供对照。

### 需求调研与需求建模

- [需求规格说明书文字修订版](<./需求调研+需求建模/初步提交材料/系统需求规格说明书_修订版_20261020.docx>)、[同版 PDF](<./需求调研+需求建模/初步提交材料/系统需求规格说明书_修订版_20261020.pdf>)：2026-10-20 修订，保留全部图片及49个用例编号，补齐权限、状态、16类故障、智能辅助和验收对应关系。[修改清单及保留图片的限制](<./需求调研+需求建模/初步提交材料/系统需求规格说明书_修订说明_20261020.md>)。调研报告、SPEC、PPT 本轮未同步。
- [需求规格说明书紧凑排版竖向版](<./需求调研+需求分析/初步提交材料/系统需求规格说明书_紧凑排版_竖向版.docx>)：历史交付，端到端活动图页改为竖向 A4，全部 93 页均为竖向。文字表格行可跨页，45 张用例活动图显示尺寸缩小 10%，取消用例强制另起页；正文、图片内容与目录层级保持不变，已通过 Word 和渲染对比检查。[上一版](<./需求调研+需求分析/初步提交材料/系统需求规格说明书_紧凑排版版.docx>)保留。
- [用例活动图源码与图片索引](<./需求调研+需求分析/初步提交材料/用例活动图/ReadMe.md>)：45 张用例活动图及训练任务状态图的独立 TikZ 源码、300 DPI PNG、矢量 PDF、Markdown 阅读版与复用说明。
- [需求调研报告：算力资源补充版](<./需求调研+需求分析/初步提交材料/需求调研报告_算力资源补充版.docx>)：第五部分新增 5.6 算力资源可行性分析，覆盖资源、平台接入、统一接口、运行流程、安全和验证安排；原稿保留。
- [算力补充说明与核对记录](<./需求调研+需求分析/初步提交材料/算力资源补充说明.md>)：三份原文档核对、实施状态、官方来源及重建方法。
- 初步提交材料原稿：[需求调研报告](<./需求调研+需求分析/初步提交材料/需求调研报告.docx>)、[系统需求规格说明书](<./需求调研+需求分析/初步提交材料/系统需求规格说明书.docx>)、[核心模块开发规范](<./需求调研+需求分析/初步提交材料/核心模块开发规范.docx>)。
- [当前合并答辩稿：建模优化兼容修正版](<./需求调研+需求分析/ppt/大模型集成训练平台_需求调研与建模答辩_建模优化版_兼容修正版.pptx>)：保留原稿第 1～29 页，第二阶段正文为第 30～36 页，AI 填写在第 37 页，原始模型图在第 38～40 页。旧优化版保留用于问题追踪。
- [建模优化设计与使用说明](<./需求调研+需求分析/ppt/需求建模优化设计与使用说明.md>)：阶段纠正、逐页设计、图片问题、规则依据、使用与验收记录。

- [参考对照补充样稿](<./需求调研+需求分析/参考对照补充样稿/ReadMe.md>)：前两阶段全部参考材料对照、调研补充、13 个详细用例、3 个独立 SPEC、追踪/评审记录及可编辑 PPT demo；保留原稿，不把草案认定为已批准基线。
- [参考材料完整索引](./参考/ReadMe.md)：正确提取的前两阶段 Word/PDF/问卷/CSV/原型/PPT 及阅读版。
- [阶段资料与答辩使用说明](<./需求调研+需求分析/ReadMe.md>)：任务要求、两组报告、问卷、技术调研、用户故事、SRS 及各 PDF 文字版的完整索引。
- [两份 PPT 内容设计与核对记录](<./需求调研+需求分析/答辩PPT内容设计.md>)：逐页安排、资料覆盖、统计修正和待补证据。
- [调研二次修订内容设计](<./需求调研+需求分析/需求调研二次修订内容设计.md>)：逐页安排、展示要求核对、图片与统计记录。
- [旧需求分析答辩修订版](<./需求调研+需求分析/大模型集成训练平台_需求分析答辩_修订版.pptx>)：历史版本，曾混用第二、三阶段内容，保留供对照，不作为当前第二阶段汇报稿。
- [版式样张](<./需求调研+需求分析/答辩PPT版式样张_修订版.pptx>)、[上一轮调研修订稿](<./需求调研+需求分析/大模型集成训练平台_需求调研答辩_修订版.pptx>)与[旧调研稿](<./需求调研+需求分析/大模型集成训练平台_需求调研答辩.pptx>)、[旧分析稿](<./需求调研+需求分析/大模型集成训练平台_需求分析答辩.pptx>)保留供版本比较。

成员分工和两组 AI 使用记录需要按实际情况填入。当前用例、活动、状态图可在 PPT 中编辑，正式提交需同步并保存模型源文件。目录沿用已有名称“需求调研+需求分析”，不批量改名；阶段名称按任务书第二阶段“需求建模”使用。待同步事项见使用说明和后续待办。

### 第一阶段交付

- [前端设计说明](./stage1/前端设计说明.md)：信息架构、任务与模型组织、视觉规则。
- [阶段说明](./stage1/阶段说明.md)：已完成范围与验证记录。
- [运行说明](./stage1/部署说明.md)：本地打开、启动服务和运行测试。
- [后续功能待办](./后续功能待办.md)：所有仅有前端界面或模拟行为的功能，以及下一步实现事项。

### 第二阶段交付

- [前端设计说明](./stage2/前端设计说明.md)：分级菜单、页面规划、Qwen 微调、权限合成与 GPU 接入流程。
- [阶段说明](./stage2/阶段说明.md)：本阶段范围和测试结果。
- [运行说明](./stage2/运行说明.md)：演示账号、本地启动与数据重置。

前端入口位于 [`frontend/index.html`](../frontend/index.html)。当前不需要安装依赖，可按运行说明直接启动。

## PDF 转 Markdown 工具

项目脚本位于 [`scripts/pdf_to_markdown.py`](<../scripts/pdf_to_markdown.py>)。在仓库根目录运行：

```powershell
& 'C:\Users\lixu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\pdf_to_markdown.py --check
& 'C:\Users\lixu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\pdf_to_markdown.py
```

脚本默认递归扫描 `docs`，为缺失的 PDF 创建同目录同名 Markdown；也可以传入单个 PDF 或目录。先用 `--check` 比较 PDF 与 Markdown 的修改时间。PDF 较新时，可用 `--refresh` 更新由此脚本生成的 Markdown，更新前会在同目录保存带时间戳的备份。普通运行不会覆盖现有文件。转换保留页码和可提取文字；截图、图表和扫描页中的文字不会自动识别，Markdown 逐页提供原 PDF 链接供核对。
