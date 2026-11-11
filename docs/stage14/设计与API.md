# 数据导入与参数模板

## 数据导入

CSV文本分类、JSONL指令数据及图像ZIP内的labels.csv支持字段选择。上传后先识别字段，再选择“目标字段 → 原字段”的映射；canonical名称相同的字段可预选，其余由使用者选择。未选择的原字段不导入，页面以正常字号标签列出。修改文件、任务或映射会清除此前预览，避免提交与预览不一致。

文本必选text；label可留空表示待标注。指令数据必选instruction、output，input可省略。图像必选filename；label可留空表示待标注。原字段不可重复指派，空缺必需字段、未知目标或原字段、重复表头、过多字段和非法值明确拒绝。不执行表达式或嵌套路径提取。图像压缩包继续校验路径、图片、数量与解压上限。

预览和正式上传调用同一个标准化函数。服务端生成标准CSV/JSONL/ZIP，再走已有严格解析、实际字节配额和不可变版本保存；Worker不需要适配任意列名。版本provenance保留原文件名、原SHA256、原字节数、映射及忽略列；版本SHA256和存储字节始终对应实际保存的标准文件。原上传文件只用于本次转换，不额外持久化副本。旧标准上传不传映射时保持原行为。

均需要所属空间datasets.write：

| 接口 | 请求 | 返回 |
| --- | --- | --- |
| POST `/api/v1/workspaces/{id}/dataset-column-inspection` | multipart：file、task_type | columns、targets、suggested_mapping、原摘要 |
| POST `/api/v1/workspaces/{id}/dataset-previews` | 原multipart，新增可选column_mapping JSON字符串 | 标准样本、标准文件摘要、来源和映射信息 |
| POST `/api/v1/workspaces/{id}/datasets/{id}/versions` | 原multipart，新增可选column_mapping JSON字符串 | 原版本结构，provenance包含转换来源 |

参考[Hugging Face字段重命名设计](https://github.com/huggingface/datasets/blob/main/docs/source/process.mdx)的显式映射，按平台三种标准格式实现，不引入该依赖。文件与映射通过multipart传递，遵循[FastAPI文件及表单约定](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/)。

## 参数模板

模板属于工作空间，绑定任务类型和训练器ID，不绑定某次训练、模型版本、数据版本、节点、优先级或凭据。共有参数为epochs、batch_size、learning_rate、validation_ratio、seed；Qwen增加max_length、lora_rank。不保存服务推理配置，所有值使用原TrainConfig范围校验。三种受支持训练器与任务必须匹配。

具有training.read的成员读取本空间模板；training.write的成员维护共享模板和应用到当前草稿。名称在空间内唯一，使用revision与If-Match防止覆盖并发修改。提供归档与恢复，归档模板仍可管理，不能应用。历史任务已经复制的参数不随模板变化。

训练向导第三步使用紧凑的模板选择及应用、另存、管理按钮。新建和编辑为弹窗，管理弹窗列出任务、模板状态及操作。应用前由服务端核对版本、当前模型所属空间、归档状态与训练器兼容，只返回参数副本；前端只替换参数字段，保留草稿上下文，不自动提交训练。智能建议采纳后可使用同一另存入口。

迁移0010_templates新增training_parameter_templates：id、workspace_id、name、task_type、trainer_id、config JSON、created_by、archived、revision、created_at；唯一约束workspace_id/name。归档字段非空，默认false。无删除接口，不更改既有资产或任务表。

接口根路径`/api/v1/workspaces/{id}/training-parameter-templates`：GET分页列表（task_type、trainer_id、status、q）；POST创建；PATCH `/{id}`完整更新名称及参数；POST `/{id}/archive`修改归档；POST `/{id}/resolve`带model_version_id和If-Match返回兼容参数。写入与应用记录审计，跨空间ID不返回资源信息。

## 实施与验收

1. 建立设计索引、云端只读基线和服务器源码快照。
2. 实现标准化与模板服务、迁移、API及针对格式、权限、并发、额度的测试。
3. 接入导入页和向导，补交互测试，三种视口实拍核查，保留已确认样式及14px最低字号。
4. 隔离PostgreSQL验证schema9升级及模板竞争；云端CPU完成“非标准数据导入 → 模板 → 训练 → 评估/部署”的真实流程。智能建议部分复用已有预览确认，不擅自启用生产外发策略。
5. 最终镜像全量测试通过，备份仅留服务器，再迁移、发布并复查原记录及本机暂停状态。

之后继续完整业务链和原型差异复核，单独记录仍缺的功能。Qwen CUDA、视觉供应商调用、多物理机与长期恢复按原待办的条件推进。
