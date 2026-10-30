# 资源 API 与模型

继续复用 /api/v1 的 Cookie、CSRF、错误和分页规则。Worker 使用独立 Bearer，前缀 /api/worker/v1；用户会话不能替代节点凭据。

## 对象

Enrollment 保存创建人、空间、名称、短期码摘要、到期时间、准入设置、消费节点与消费时间。ComputeNode 保存安装标识、机器指纹、空间、名称、凭据摘要、审核/启停状态、协议版本、运行时、心跳及探测请求。ComputeDevice 保存节点、稳定硬件标识、类型、显存、使用统计和当前预留。注册报文不能设置审核、空间外授权或后台角色。

新增资源对象独立于既有用户/模型表。所有改名、审核、暂停和分配保留 revision，操作及主体进入审计。失联为按心跳时间计算的健康状态，不能自动清空设备占用。

## 资源页面端点

| 方法与路径 | 功能 |
| --- | --- |
| GET /api/v1/admin/nodes | 管理员跨空间资源列表 |
| POST /api/v1/admin/enrollments | 为指定空间生成短期接入及部署命令 |
| GET /api/v1/workspaces/{id}/resources | 当前空间可见节点/设备 |
| POST /api/v1/workspaces/{id}/enrollments | 获授权成员申请节点，默认等待审核 |
| GET/PATCH /api/v1/resources/nodes/{id} | 详情、名称、分配、审核与暂停 |
| POST /api/v1/resources/nodes/{id}/probe | 持久化探测请求，由心跳消息送达 |
| POST /api/v1/resources/nodes/{id}/revoke | 仅空闲节点可撤销凭据 |
| POST /api/v1/admin/local-worker | 显式本机开发开关下启动独立 Worker |
| GET /api/v1/admin/worker-runtimes | 本机配置的训练解释器及能力，供快捷接入选择 |

资源动作登记 resources.read/resources.manage，空间查看者不能执行新增/变更；管理员的个人/组禁用仍优先。节点只能管理其所属空间，跨空间标识替换返回 404。

## Worker 协议

| 方法与路径 | 功能 |
| --- | --- |
| GET /api/worker/v1/bundle | 下载公开、无秘密的 Worker zipapp 及对应摘要头 |
| POST /api/worker/v1/register | 使用一次性申请注册/重试，传本地生成的凭据摘要和硬件清单 |
| POST /api/worker/v1/heartbeat | 节点身份、序号、当前执行与统计；返回探测请求及控制意图 |
| POST /api/worker/v1/inventory | 按请求标识回传完整硬件及运行时探测结果 |

协议版本、序号、能力和大小设边界；返回不含秘密的节点身份。注册的重复响应不下发明文长期凭据，因为 Worker 早已在私密文件保存原始凭据。任务派发和文件/事件协议在 stage8 细化后加入，不在本阶段伪造成功。
