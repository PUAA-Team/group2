# 项目与控制台补齐

## 项目

项目新增description及archived。列表支持归档状态，点击名称进入独立详情，查看项目资料、真实训练统计和关联任务。修改资料、归档与恢复使用弹窗，写入校验revision。归档保留任务与结果，禁止新任务登记、草稿提交和排队领取；已经运行的执行继续使用原快照。领取与归档通过项目行锁串行核验。归档项目不能出现在新建训练的项目选择中，编辑历史草稿保留原关联并提示先恢复。

接口根为`/api/v1/workspaces/{workspace_id}`，需要training.read读取、training.write修改：GET `/projects/{id}`返回项目、统计及最近任务；PATCH `/projects/{id}`修改名称/说明；POST `/projects/{id}/archive`传archived并带If-Match。原POST `/projects`兼容原名称载荷，新增可选说明；原GET `/projects`及`/project-catalog`增加status=all/active/archived，缺省all保持历史列表行为。

## 查询筛选

普通模型/数据目录增加归档状态；数据目录另有version_status=available/needs_annotation/unversioned，按最新版本判断。管理数据和模型增加task_type与creator；作业和操作记录增加creator、created_from、created_to，操作记录再支持精确action。creator按创建人显示名关键词匹配，资产创建人使用最早创建审计，不用空间所有者代替未知人。日期按北京时间自然日，起止均包含；起晚于止拒绝。

筛选通过服务端执行，分页、导出共用查询条件。前端复用现有选择框及筛选弹窗，不新增菜单，不使用小号说明。用户输入通过SQL参数绑定，名称包含符号时按文本搜索。

## 密钥

只向当前创建者展示本空间密钥。新增job_id、status=all/active/expired/revoked筛选，保留原数组响应。每行显示非秘密ID标识、实际关联调用数及最近提交时间；从迁移起记录，不推测历史密钥归属。浏览器调用没有key_id，保持未知来源，不计入某个密钥。调用结果轮询不累计调用数。

service_calls增加nullable service_key_id；service_keys增加revision及usage_started_at。实际API预测入队时锁定密钥并再次核验撤销和到期，保存密钥ID与请求在同一事务提交。使用记录只包含计数、时间和状态，无请求/响应正文。轮换保留原期限；撤销、轮换和有效期调整更新revision，避免并发覆盖。

PATCH `/service-keys/{id}`需要services.write、创建者及If-Match，提交带时区的expires_at；允许调整过期密钥为未来时间，撤销密钥保持不可恢复。上限为当前时间后365天。有效期调整与调用示例均为弹窗。接入示例使用环境变量占位，不在网页持久化或导出密钥正文。模板仅针对当前支持的输入类型，调用结果仍通过原轮询接口读取。

## 导出

GET `/api/v1/admin/audit-export`需要管理员audit.read，支持与全局审计列表相同的q/space/status/creator/action/created_from/created_to；导出最多10000条，超出明确要求缩小范围。列固定为时间、动作、操作者、空间、目标、结果、错误码与请求号，排除密码、凭据、正文和错误详情。CSV使用UTF-8 BOM，用户文本防公式注入，并记录导出审计。

GET `/workspaces/{id}/jobs/{id}/evaluation-summary`需要training.read，只接受已完成评估，返回版本、配置、原始总体指标、混淆矩阵和由矩阵计算的每类precision/recall/F1/support。没有矩阵时保持缺失；分母为零的指标保留null。Qwen报告实际loss、困惑度和Token，不生成分类结果。GET同根`/evaluation-report?format=json|csv`下载相同信息，不包含原始样本。评估详情提供分类表及下载，已有比较规则保持不变。

指标定义参考[scikit-learn分类报告](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/metrics/_classification.py)，用现有Python实现，不增加依赖。CSV检查参考[OWASP公式注入指南](https://owasp.github.io/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Injection/21-CSV_Injection)。

## 迁移、发布与验证

0011_console在项目增加说明/归档，在密钥增加revision/统计起点，在调用记录增加密钥关联及索引。旧调用关联保持null；旧密钥统计起点为迁移时刻。SQLite表重建保留原行，PostgreSQL使用显式ALTER，迁移另在真实PG验证。

覆盖跨空间/成员、归档领取竞争、密钥撤销/轮换/有效期与调用竞争、未知历史来源、日期边界、CSV公式与输出脱敏、分类零分母。界面与导出内容逐项核对，三种尺寸检查。最终镜像通过后备份、迁移并发布，本机节点不恢复。旧控制端不了解项目归档，兼容回退仅开放读取和登录退出，停止operations后使用，不回退数据库。
