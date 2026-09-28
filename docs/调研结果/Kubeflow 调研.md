## Kubeflow 调研

官方入口：[项目介绍](https://www.kubeflow.org/docs/started/introduction/)｜[GitHub](https://github.com/kubeflow/kubeflow)｜[Profiles](https://www.kubeflow.org/docs/components/central-dash/profiles/)｜[Trainer](https://trainer.kubeflow.org/en/latest/)｜[Pipelines](https://www.kubeflow.org/docs/components/pipelines/)｜[KServe](https://www.kubeflow.org/docs/ecosystem/kserve/)｜[Kubeflow Hub](https://www.kubeflow.org/docs/components/hub/)

### 3.1 产品边界

Kubeflow 是 Kubernetes 上的 AI 平台组件集合，不是单体产品。

| 子系统                    | 主要职责                                                    |
| ------------------------- | ----------------------------------------------------------- |
| Central Dashboard         | 统一入口、当前 Profile/Namespace 选择、子应用导航           |
| Profile Controller / KFAM | 多租户 Namespace、成员、RBAC、Istio 访问策略、ResourceQuota |
| Notebooks                 | Jupyter 等交互式开发环境                                    |
| Trainer                   | 单机/分布式训练、LLM 微调、训练运行时与生命周期             |
| Pipelines                 | 数据处理、训练、评估、注册、部署的 DAG 编排与可复现运行     |
| Katib                     | 超参数搜索与早停                                            |
| Kubeflow Hub              | 模型发现、注册、版本、产物元数据和生命周期管理              |
| KServe                    | 推理服务、自动伸缩、缩容到零、灰度发布、预/后处理           |

### 3.2 用户完整流程

#### 流程 A：一次训练

1. **进入 Profile/Namespace**
   - Dashboard 顶部选择当前 Profile。
   - 用户只能看到自己是 owner、edit 或 view 成员的空间。
2. **准备开发环境**
   - 创建 Notebook，选择镜像、CPU/内存/GPU 和存储卷。
   - 在 Notebook 中准备训练函数、Pipeline 或 TrainJob 配置。
3. **选择训练运行时**
   - 平台管理员预置 `ClusterTrainingRuntime`，如 PyTorch、DeepSpeed、TorchTune Qwen。
   - 团队可在 Namespace 内定义 `TrainingRuntime`。
4. **创建 TrainJob**
   - 引用运行时。
   - 配置数据/模型 URI、节点数、每节点 CPU/内存/GPU、进程数和训练代码。
   - 可配置 suspend、active deadline 和有限的 runtime patch。
5. **初始化资产**
   - Dataset Initializer 和 Model Initializer 先下载/准备数据。
   - 初始化完成后才启动 GPU 训练节点，避免 GPU 等待下载。
6. **调度执行**
   - Controller 将 TrainJob 展开为 JobSet 和多个 Pod。
   - 可接入 Kueue、Volcano、KAI、Coscheduling 或 Slurm Bridge。
7. **查看状态**
   - TrainJob 条件至少包含 Suspended、Complete、Failed。
   - 具体运行状态由底层 JobSet/Pod 汇总；事件和日志用于诊断。
8. **保存结果**
   - 输出到对象存储/PVC；通过 Pipeline Artifact 或 Kubeflow Hub 注册模型版本。

Kubeflow Trainer 的资产初始化设计值得直接吸收：数据/模型准备由 CPU 任务完成，GPU 训练节点只在资产 Ready 后启动。

![Kubeflow 资产初始化与缓存](C:/Users/lixu/OneDrive/%25E6%25A1%258C%25E9%259D%25A2/%25E5%25A4%25A7%25E4%25B8%2589%25E4%25B8%258A/%25E8%25BD%25AF%25E5%2588%2586/research_repos/kubeflow_subprojects/trainer/docs/images/data-cache-init.png)

#### 流程 B：可复现流水线

1. 把数据预处理、训练、评估、注册和部署封装为 Component。
2. 使用 Python SDK 组合有向无环图，定义参数、产物和依赖关系。
3. 编译为 IR YAML。
4. 在 Pipelines UI 上传版本。
5. 建立 Experiment，填写参数并创建 Run。
6. 运行中查看 Graph、每个节点状态、输入输出、日志和产物。
7. 比较同一 Experiment 下多个 Run。
8. 可配置 Recurring Run，设置周期和最大并发数。

#### 流程 C：模型发布

1. 在 Kubeflow Hub 注册模型、版本、格式、产物 URI、指标和元数据。
2. 用模型版本创建 KServe `InferenceService`。
3. 选择 ServingRuntime、CPU/GPU、实例和伸缩策略。
4. Controller 创建推理工作负载、网络和健康检查。
5. 获取推理地址并调用。
6. 后续可做缩容到零、自动伸缩、预处理/后处理和 Canary 灰度。

### 3.3 管理员与运营方需求

#### 租户和权限

`Profile` 是 Kubeflow 的租户边界。代码中一个 Profile 会协调创建：

- 同名 Kubernetes Namespace。
- Owner 的 `kubeflow-admin` RoleBinding。
- Contributor 的 `kubeflow-edit` 或 `kubeflow-view` RoleBinding。
- `default-editor`、`default-viewer` ServiceAccount。
- Istio AuthorizationPolicy。
- 可选 ResourceQuota。

管理员需求：

- 创建、查看、删除 Profile。
- 指定 Owner，添加/移除 edit、view 成员。
- 配置 Namespace 级 CPU、内存、GPU、对象数和存储配额。
- 控制是否允许首次登录自动创建 Profile。
- 删除 Profile 前明确提示其 Namespace 和内部资源会被一并删除。

#### 多租户后台真实页面证据

**Profile/Namespace 自动创建**

![Kubeflow Profile 创建页面](C:/Users/lixu/OneDrive/%25E6%25A1%258C%25E9%259D%25A2/%25E5%25A4%25A7%25E4%25B8%2589%25E4%25B8%258A/%25E8%25BD%25AF%25E5%2588%2586/research_repos/kubeflow_website_assets/content/en/docs/images/dashboard/auto-profile-step-2.png)

需求与设计：首次进入时创建工作空间，系统把展示名称映射为 Namespace；本项目应由管理员预建团队或审批创建，避免任何用户自动成为 Owner。

**成员管理入口与当前租户上下文**

![Kubeflow Manage Contributors 入口](C:/Users/lixu/OneDrive/%25E6%25A1%258C%25E9%259D%25A2/%25E5%25A4%25A7%25E4%25B8%2589%25E4%25B8%258A/%25E8%25BD%25AF%25E5%2588%2586/research_repos/kubeflow_website_assets/content/en/docs/images/dashboard/homepage-manage-contributors.png)

需求与设计：顶部持续显示当前工作空间与当前角色，所有任务、资产和统计均受该上下文过滤；只有 Owner/管理员显示成员管理入口。

**成员与角色管理页面**

![Kubeflow Manage Contributors 页面](C:/Users/lixu/OneDrive/%25E6%25A1%258C%25E9%259D%25A2/%25E5%25A4%25A7%25E4%25B8%2589%25E4%25B8%258A/%25E8%25BD%25AF%25E5%2588%2586/research_repos/kubeflow_website_assets/content/en/docs/images/dashboard/manage-contributors.png)

需求与设计：后台必须显示账号、本人角色、所属工作空间和每个工作空间的成员；新增成员时同时指定角色。Kubeflow 页面只支持通过邮箱维护 Contributor，课程平台应补齐 Viewer、Operator、Admin 和邀请/禁用状态。

**跨任务运行管理页面**

![Kubeflow Pipeline Runs 管理页面](C:/Users/lixu/OneDrive/%25E6%25A1%258C%25E9%259D%25A2/%25E5%25A4%25A7%25E4%25B8%2589%25E4%25B8%258A/%25E8%25BD%25AF%25E5%2588%2586/research_repos/kubeflow_website_assets/content/en/docs/images/dashboard/pipelines-runs.png)

需求与设计：运行列表应区分 Active/Archived，提供名称、状态、持续时间、所属实验、版本、是否周期运行和开始时间；管理员视角还要增加创建人、团队、GPU 占用、队列等待、失败原因、停止和导出操作。

#### 训练运行时治理

- 管理 `ClusterTrainingRuntime`，统一框架、基础镜像、分布式策略、初始化器、存储和安全配置。
- 允许团队在 Namespace 内维护受限 `TrainingRuntime`。
- 运行时版本升级、弃用和兼容性提示。
- Webhook 校验自定义运行时；只有社区已验证的可信运行时可跳过校验。
- 限制用户可覆盖字段，防止通过任意 patch 绕过安全和资源策略。

#### 调度与资源

- Kueue：队列、配额准入、优先级。
- Volcano：Gang Scheduling、队列、优先级、网络拓扑感知。
- Gang Scheduling 保证分布式任务所需 Pod 同时获得资源，避免部分节点占卡等待。
- `activeDeadlineSeconds` 到期后自动删除 JobSet 并把 TrainJob 标记为 Failed/DeadlineExceeded。
- Suspend 会释放 Pod，但保留 TrainJob 配置；Resume 后重新运行。

#### 平台运维

- 认证提供方、证书、网关、网络策略和 Secret 管理。
- Notebook、Pipeline、Trainer、Hub、KServe 等组件的安装、版本、升级和故障处理。
- 对象存储、PVC、元数据数据库和镜像仓库运维。
- 组件级指标、日志、事件和告警。
- 备份/恢复 Pipeline 元数据、模型元数据和持久存储。

#### 运营能力缺口

Kubeflow 的管理员操作多依赖 Kubernetes CRD、YAML 和发行版配置。社区版没有像 Crater 那样统一的：

- 用户/账户计量和余额。
- GPU 卡时统计与运营报表。
- 工单审批。
- 统一操作审计页面。
- 面向非 Kubernetes 管理员的资源池控制台。

这些能力需要目标平台自行建设，不能把 Kubeflow 当作完整运营后台。

### 3.4 特色功能及可学习内容

| 功能                | 价值                             | 本项目采用方式                               |
| ------------------- | -------------------------------- | -------------------------------------------- |
| Profile + Namespace | 团队资源和权限隔离               | P0 用“工作空间/团队”包装，不暴露 Namespace   |
| TrainingRuntime     | 管理员维护安全、可复用的训练蓝图 | P0：模型模板关联运行环境模板                 |
| TrainJob 统一接口   | 不同框架共享任务模型             | P0：统一任务实体 + 可插拔执行器              |
| 资产初始化步骤      | 下载数据/模型不占 GPU            | P1 创新，适合大模型场景                      |
| Pipeline DAG        | 可复现、可重试、可比较           | P2；一期可做固定“预处理→训练→评估”三阶段流程 |
| Immutable Run       | 保存配置和结果快照               | P0：任务提交后配置不可直接修改，只能克隆重跑 |
| Katib               | 自动超参搜索与早停               | P2 创新                                      |
| Model Registry/Hub  | 模型版本、指标、元数据、血缘     | P1                                           |
| KServe              | 自动伸缩、缩容到零、灰度         | P2；一期只做单版本服务发布                   |
| Gang Scheduling     | 避免分布式任务部分占卡死等       | P1，使用 Volcano 时实现                      |

### 3.5 不应照搬的部分

- 不让普通用户编写 CRD/YAML、选择 Namespace、配置 Istio。
- 不在一期集成全部 Kubeflow 子项目；部署和运维成本过高。
- 不把 Pipeline 编译、对象存储、元数据服务等内部对象直接作为主流程。
- Kubeflow 的 TrainJob 状态条件过于粗，需要补充本平台的准入、排队、启动、取消、停止和失败阶段。