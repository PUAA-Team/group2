import { research } from './research-content.mjs';
import { analysis } from './analysis-content.mjs';

const chapter = (number, title, topics) => ({ kind: 'chapter', number, title, topics });
const table = (title, headers, rows, widths, extra = {}) => ({ kind: 'table', title, headers, rows, widths, ...extra });
const story = (title, sections, extra = {}) => ({ kind: 'story', title, sections, ...extra });
const originalTable = (source, index, title, extra = {}) => {
  const s = source.slides[index];
  return table(title, [...s.headers], s.rows.map(row => [...row]), [...s.widths], extra);
};
const image = (title, asset, sections, extra = {}) => ({ kind: 'image', title, asset, sections, ...extra });
const charts = (index, title) => ({ kind: 'charts', title, charts: research.slides[index].charts });
const frame = (title, frameTitle, layout, sections, extra = {}) => ({ kind: 'frame', title, frameTitle, layout, sections, ...extra });

export const taskMapping = [
  ['多模型训练与推理', '按任务选择模型、数据与超参数；保存产物并发布服务', 'BML 训练项目与版本；小型 Qwen 分类微调'],
  ['资源调度与管理', '指定 GPU 编号、任务类型与配额；自动和手动选择', '管理员授权 GPU 2/3；调度时再次校验'],
  ['实时监控与日志', '训练进度、loss、资源指标；日志查询与导出', 'BML 监控界面；状态、图表、日志分别展示'],
  ['数据管理与存储', '上传规范数据；需要时清洗、标注、划分并创建版本', 'BML 按数据类型选择模板；固定训练输入版本'],
  ['扩展与升级', '模型与运行时模板可扩展；增强功能按优先级排期', '优先训练与在线推理；调参搜索等作为增强功能'],
];

export const researchV2 = {
  key: 'research', label: '需求调研', filename: '大模型集成训练平台_需求调研答辩_修订版.pptx',
  chapters: ['项目背景与调研方案', '同类平台调研', '模型、框架、数据与资源', '用户调查与需求结论'],
  slides: [
    { kind: 'cover', title: '需求调研', main: true },
    { kind: 'contents', title: '汇报内容' },
    chapter(1, '项目背景与调研方案', '平台定位与任务目标\n调研对象、方法与两组分工'),
    story('团队分工与调研执行', [
      { heading: '第一小组', text: '成员：________________\n分工：________________\n汇报代表：____________' },
      { heading: '第二小组', text: '成员：________________\n分工：________________\n汇报代表：____________' },
      { heading: '已开展的工作', text: '六个商业平台与两个开源平台；两组报告及合并结论；67 份有效问卷；用户故事和 SRS。' },
      { heading: '调查方法', text: '背景资料研读、控制台流程体验、官方文档与源码阅读、用户问卷。访谈目前停留在提纲计划。' },
    ], { main: true }),
    table('任务书目标与平台需求', ['任务书目标', '平台需求', '设计与调研结果'], taskMapping, [0.19, 0.43, 0.38], { main: true, font: 20 }),
    story('平台定位与三类使用者', [
      { heading: '普通用户', text: '在 Web 页面选模型和数据，配置训练参数与算力；查看日志和指标，保存模型，发布并调用推理服务。' },
      { heading: '系统管理员', text: '决定每位用户可使用的显卡编号和任务类型；管理用户组、个人权限、并发与存储限额。' },
      { heading: '平台运营者', text: '维护节点、驱动、存储和网络；处理失联、异常作业、资源释放及审计记录。' },
      { heading: '研究重点', text: '配置流程是否易用，输入是否明确，执行是否可观察，资源分派是否符合授权。' },
    ]),
    story('调研方案与执行安排', [
      { heading: '第 2 周：背景资料', text: '明确训练、推理和管理三条业务线，列出用户、管理员与运营者的调查问题。' },
      { heading: '第 3 周：平台体验', text: 'BML 为主要业务案例；比较 ModelArts、PAI、TI-ONE、SageMaker、Azure ML 的差异。' },
      { heading: '第 4～5 周：技术与问卷', text: '研究模型、框架、数据和资源；统计用户对配置、监控、数据和管理功能的偏好。' },
      { heading: '第 6 周：汇总与规约', text: '形成三类角色诉求、核心功能与增强功能，转入用户故事、需求模型和 SRS。' },
    ], { caption: '原调研计划的周次安排' }),
    chapter(2, '同类平台调研', 'BML：数据、训练、评估与部署\n其他云平台与开源平台的补充能力'),
    image('BML：数据类型决定标注与导入方式', 'bml-extra/page-03-image-01.png', [
      { heading: '先选类型与任务', text: '图片、文本、音频、表格采用不同标注类型与模板；保存数据集版本。' },
      { heading: '处理形成新版本', text: '上传、导入、校验分别记录状态。清洗、划分、标注和增强保存参数与父版本。' },
      { heading: '对应数据管理需求', text: '规范数据可直接用于训练；格式错误定位到字段或样本，处理过程不覆盖历史输入。' },
    ], { imageLayout: 'portrait' }),
    image('BML：按任务组织模型、网络与训练配置', 'bml/page-07-image-01.png', [
      { heading: '预置模型与基础网络', text: '选择算法和网络；预训练权重微调与随机初始化分别配置。' },
      { heading: '一次训练保存一份配置', text: '固定数据版本、模型版本、BatchSize、Epoch、学习率、运行环境和 GPU。' },
      { heading: '我们的选择方式', text: '先选任务类型，再显示兼容模型；模型与数据模板可扩展，参数分常用和高级设置。' },
    ], { main: true, imageLayout: 'config', crop: { left: 0, top: 0, right: 0.4, bottom: 0.51 },
      bottom: '三种开发入口：预置模型调参、Notebook 建模、自定义作业。项目保留多次训练。' }),
    image('BML：实时指标与结果比较', 'bml/page-07-image-03.png', [
      { heading: '训练过程', text: 'batch loss、train loss、学习率、epoch 耗时和吞吐分别展示。' },
      { heading: '结果评估', text: '版本列表关联评估报告与错误样本；固定验证集后比较多次训练结果。' },
      { heading: '我们的任务详情', text: '状态摘要、指标、日志分区；保留原始指标和日志导出，平滑仅改变曲线显示。' },
    ], { main: true, imageLayout: 'wide', crop: { left: 0, top: 0, right: 0.15, bottom: 0.26 } }),
    image('BML：评估结果回到数据处理', 'bml/page-08-image-01.png', [
      { heading: '评估对象', text: '对应任务产出的模型版本，记录评估数据和指标。' },
      { heading: '比较条件', text: 'Accuracy、F1、precision、recall 使用相同数据版本和标签规则。' },
      { heading: '错误样本', text: '查看误分类样本，再修正标注或处理数据；重新训练使用新的数据版本。' },
    ], { imageLayout: 'wide', crop: { left: 0, top: 0, right: 0.32, bottom: 0.44 } }),
    story('BML：模型产物与部署方式', [
      { heading: '模型版本', text: '训练输出权重，版本列表关联来源任务与评估报告；保存后进入模型管理。' },
      { heading: '公有云服务', text: '模型保存在云端，经独立 REST API 调用；发布服务时单独配置计算资源。' },
      { heading: '其他部署方式', text: '端云协同、批量预测和纯离线服务。私有服务器支持私有 API 与服务器端 SDK。' },
      { heading: '一期采用', text: '在线发布、页面测试、API 调用与停止服务；固定模型版本，分别维护服务状态和资源占用。' },
    ]),
    table('其他云平台：补充能力与设计取舍', ['平台', '调查结果', '本系统采用的设计'], [
      ['ModelArts', '预置精调、自定义作业；资源池、模型版本与在线推理', '固定运行时与作业规格；保留云执行适配'],
      ['PAI', '按训练/部署能力筛选；SFT、LoRA、QLoRA；数据预览', '模型能力过滤；参数分层；上传字段校验'],
      ['TI-ONE', '按任务和硬件筛选；质量评估与服务性能评估分开', '显示模板兼容条件；效果与延迟分别展示'],
      ['SageMaker', '输入通道、输出与 checkpoint；用途和实例配额', '输入版本固定；运行时限、资源配额与恢复分开'],
      ['Azure ML', '数据/环境/模型版本；Endpoint 与 Deployment 分离', '配置快照、资产关联；服务入口独立于部署版本'],
    ], [0.17, 0.43, 0.40]),
    story('云平台的配置成本与可复现记录', [
      { heading: 'PAI：表单联动', text: 'Qwen3-0.6B 普通版和 Base 版支持训练，FP8 版仅部署/评测；配置表单带数据预览和默认 SFT + LoRA。' },
      { heading: 'SageMaker：用途与配额', text: '训练、推理、处理和 Notebook 用途限额分开。IAM、S3、镜像和网络字段由管理员配置。' },
      { heading: 'Azure ML：资产与服务', text: '任务固定数据和环境版本；部署更新模型时保留服务入口，运行记录关联输入与输出。' },
      { heading: 'TI-ONE：兼容与成本', text: '模型训练能力受任务、模式和硬件约束；提交前给出资源配置，模型质量与吞吐延迟分别评估。' },
    ]),
    story('ModelArts：分布式、续训与资源池边界', [
      { heading: '分布式训练', text: '调研记录支持 PyTorch、MindSpore，多实例配置由平台注入 rank 与 world_size；训练代码仍需兼容分布式执行。' },
      { heading: '断点续训', text: '平台提供存储挂载和失败重启；训练脚本负责 checkpoint 保存与重载，不能只增加一个续训开关。' },
      { heading: '在线推理', text: '训练产物进入模型版本管理后再部署服务；推理配置、运行状态与来源训练任务分别维护。' },
      { heading: '资源池与权限', text: '池、队列、规格、配额与作业类型共同限制资源。任务书的指定 GPU 编号授权由本平台管理端另行实现。' },
    ]),
    originalTable(research, 16, 'ModelArts：SDK、API 与 CLI 对接', { caption: '覆盖提交、查询、停止、日志、产物和资源；执行后端保留选择空间。' }),
    story('Crater 与 Kubeflow：资源与多用户管理', [
      { heading: 'Crater：准入后等待资源', text: '账户、队列和配额限制作业资格；有权限但没有空闲资源时排队，显示等待原因。' },
      { heading: 'Kubeflow：用户空间', text: 'Profile/namespace 配合 RBAC 与 ResourceQuota；训练、调参和服务组件分别承担职责。' },
      { heading: '采用的规则', text: '组与个人授权共同生效；任务类型、指定 GPU、并发和存储限额在提交及启动时检查。' },
      { heading: '后续扩展', text: '可信运行时、模型下载缓存和准备阶段分离；分布式、vGPU、回填等策略另行验证。' },
    ]),
    chapter(3, '模型、框架、数据与资源', '小型 Qwen 文本分类场景\n模型能力、数据规范和运行约束'),
    { kind: 'scenario', title: '技术方案：小型 Qwen 做文本分类', main: true,
      config: '任务：文本分类 SFT\n模型：Qwen2.5-0.5B-Instruct\n方法：LoRA\n数据：text + label\n标签：正面 / 负面\n产物：Adapter + 基础模型版本',
      sections: [
        { heading: '模型与框架', text: '已有 0.5B 模板继续保留；Qwen3-0.6B 为独立候选。PyTorch、Transformers、PEFT 形成首条执行方案。' },
        { heading: '数据与评估', text: '评论转换为分类指令，固定标签映射和验证集；记录 Accuracy、F1 与错误样本。' },
        { heading: '资源与适配', text: '显存同时受精度、序列长度、batch 与优化器影响。运行时和设备组合验证后开放训练。' },
      ] },
    originalTable(research, 17, '模型结构与训练框架'),
    originalTable(research, 18, '公开数据集与字段规范'),
    story('资源调研：显存之外还要检查什么', [
      { heading: '计算与环境', text: 'GPU 型号、UUID、显存、驱动、CUDA 和框架版本；CPU、内存承担预处理和轻量验证。' },
      { heading: '磁盘与网络', text: '模型下载、数据、checkpoint、日志和最终产物各有空间需求；固定版本缓存、校验下载完整性。' },
      { heading: '授权与占用', text: '按节点和 UUID 标识设备，页面展示本地 GPU 序号；训练与推理共享限额，启动前重查权限和空闲状态。' },
      { heading: '获得资源的条件', text: '个人、实验室、远程服务器和云资源分别确认账户、租期、费用、可用时段及管理权限。' },
    ]),
    chapter(4, '用户调查与需求结论', '67 份有效问卷\n三类角色的核心需求与优先级'),
    { kind: 'survey', title: '问卷：算力获取与资源选择各有 45 人', main: true,
      chart: research.slides[6].chart, asset: 'survey-page-02.png', crop: { left: 0.098, top: 0.188, right: 0.098, bottom: 0.505 } },
    charts(21, '资源选择与参数展示偏好'),
    charts(20, '用户需要的操作与监控指标'),
    charts(22, '数据集管理与模型保存需求'),
    charts(23, '失败处理与管理员场景'),
    story('需求边界与优先级', [
      { heading: '核心功能', text: '模型与数据选择、参数配置、GPU 和任务类型授权、训练状态、实时指标、日志导出、模型保存与在线推理。' },
      { heading: '增强功能', text: '训练项目比较、在线标注、数据增强、参数建议、用户组配额与资源使用统计。' },
      { heading: '后续功能', text: '复杂分布式训练、自动搜索、定时作业、批量预测、商业计量与高级调度策略。' },
      { heading: '当前阶段', text: '完成需求调研、需求规约与界面流程确认。真实训练、资源探测、监控采集和服务调用在实现阶段验证。' },
    ], { main: true }),
    story('问卷样本与解释范围', [
      { heading: '有效样本 67 份', text: '有一定使用经验 22 人；课程/实验使用 19 人；了解概念 15 人；经常使用 11 人。' },
      { heading: '15 道题', text: '6 道单选、9 道多选。多选题每项分别以 67 为分母，不能把比例相加成 100%。' },
      { heading: '界面偏好', text: 'Q13 常用参数优先或双模式：49 人，占 73.13%。\nQ14 标签页：27 人，占 40.30%，为最大单项。' },
      { heading: '管理场景', text: 'Q15 是“假设作为管理员”的回答。资源授权和角色职责还需结合任务书及平台调研确定。' },
    ]),
  ],
};

export const analysisV2 = {
  key: 'analysis', label: '需求分析', filename: '大模型集成训练平台_需求分析答辩_修订版.pptx',
  chapters: ['系统范围与用户需求', '核心业务规则', '需求模型', '规约与验证要求'],
  slides: [
    { kind: 'cover', title: '需求分析', main: true },
    { kind: 'contents', title: '汇报内容' },
    chapter(1, '系统范围与用户需求', '角色、用户故事与用例\n训练、数据、资源和在线服务'),
    frame('角色与核心用例', '系统用例图', 'usecase', [
      { heading: '普通用户', text: '管理数据；配置、提交和停止训练；查看指标并导出日志；保存模型与发布推理服务。' },
      { heading: '管理员与运营者', text: '管理用户组与权限、指定 GPU 和任务类型、节点、配额、全局作业和审计。' },
      { heading: '任务书覆盖', text: '登录认证；模型训练与推理；资源管理；监控和日志；数据集管理。' },
    ], { main: true }),
    originalTable(analysis, 7, '功能范围：用户端与管理端'),
    story('典型用户故事', [
      { heading: '训练用户', text: '我要按任务选择兼容模型，使用已校验的数据版本，以便配置一次可执行的训练。' },
      { heading: '排查失败', text: '我要查看失败阶段和完整日志，修改后创建新任务，以便保留原配置和失败记录。' },
      { heading: '资源管理员', text: '我要将用户 A 限制为 GPU 2/3 和大语言模型微调，以便控制共享资源及可运行任务。' },
      { heading: '服务使用者', text: '我要发布一个固定模型版本，使用受控 API KEY 调用，并在结束后停止服务释放资源。' },
    ]),
    chapter(2, '核心业务规则', '模型、数据与训练项目\n授权合成、GPU 接入与在线服务'),
    originalTable(analysis, 8, '任务、模型与数据匹配'),
    originalTable(analysis, 9, '训练项目与多次结果比较'),
    story('指定 GPU 与任务类型授权', [
      { heading: '允许范围', text: '用户 A：GPU 2、GPU 3；任务类型：大语言模型微调。自动与手动模式使用同一授权集合。' },
      { heading: '拒绝场景', text: '选择 GPU 0、视觉训练或无权访问的数据版本，提交校验拒绝；页面显示具体原因。' },
      { heading: '启动前重查', text: '权限已撤销、并发超限或节点被隔离时，不分配资源；仅没有空闲 GPU 时进入等待。' },
      { heading: '终态处理', text: '核对进程退出后释放 GPU。重复回调不重复启动或释放，管理干预记录操作者和原因。' },
    ]),
    originalTable(analysis, 10, '用户组与个人权限合成'),
    story('GPU 节点接入与准入', [
      { heading: '创建接入', text: '管理员生成有范围、有效期和使用次数限制的凭证；复制受控启动命令。' },
      { heading: '注册与探测', text: '代理验证身份，报告节点、GPU UUID、型号、显存、驱动和健康；重注册保持资源身份。' },
      { heading: '确认与授权', text: '新节点先待确认，再设置可用卡、用户组与个人权限、配额；确认前不参与调度。' },
      { heading: '持续维护', text: '心跳、上下线、占用核对和隔离；失联时保留异常状态，查明现有任务后再分配。' },
    ], { caption: '后端接入规则；当前界面演示发现、探测与确认流程。' }),
    originalTable(analysis, 12, '模型版本与在线服务生命周期'),
    chapter(3, '需求模型', '用例、活动与状态\n业务类与训练提交时序'),
    frame('训练任务：从提交到资源释放', '训练任务活动图', 'activity', [
      { heading: '执行前', text: '身份、对象权限、GPU 与任务类型、模型/数据/运行时、参数与容量校验；持久化快照后返回任务 ID。' },
      { heading: '执行后', text: '排队、分配、准备、训练、监控、保存产物；失败、停止和产物写入异常均进入释放处理。' },
    ], { main: true }),
    frame('训练任务状态与结束条件', '训练任务状态图', 'state', [
      { heading: '取消与停止', text: 'Queued 取消后为 Cancelled；运行停止经 Stopping 进入 Stopped，保留已有日志。' },
      { heading: '成功与失败', text: '进程正常退出且必要产物写入完成后为 Succeeded；异常记录为 Failed 并定位失败阶段。' },
      { heading: '重试与恢复', text: '重试创建新 ID；恢复固定 checkpoint 与兼容条件。所有终态核对进程后释放资源。' },
    ], { main: true }),
    frame('业务对象、属性与关联', '核心业务类图', 'class', [
      { heading: '核心关系', text: '项目包含多次任务；任务引用模型模板和数据版本，产出模型；节点包含 GPU；在线服务引用模型版本。' },
    ]),
    frame('训练提交关键用例的交互', '训练提交时序图', 'sequence', [
      { heading: '交互责任', text: '前端提交；任务服务鉴权并返回 ID；调度器重查授权；执行器启动；监控推送；产物保存后确认结果。' },
    ]),
    chapter(4, '规约与验证要求', 'SRS 与核心模块 SPEC\n非功能目标、需求追踪与 AI 使用'),
    originalTable(analysis, 4, '训练模块 SPEC：输入、执行与验收', { main: true, caption: 'SPEC-T01 · 训练提交、授权校验、异步执行、产物与资源释放' }),
    originalTable(analysis, 15, '数据模块 SPEC：导入与版本'),
    originalTable(analysis, 16, '资源模块 SPEC：准入与释放'),
    story('非功能需求与验收目标', [
      { heading: '性能目标', text: '普通查询 p95 ≤ 2 s；提交持久化后 ≤ 3 s 返回 ID；指标采集到页面 ≤ 5 s。测试明确并发和数据规模。' },
      { heading: '可靠性', text: '重启保留任务与快照；核对失联进程；产物写入失败保留错误；终态释放操作幂等。' },
      { heading: '安全与审计', text: '对象级鉴权、指定 GPU 与任务类型校验、密钥脱敏、上传防越界；关键操作记录用户、对象和原因。' },
      { heading: '可用性与扩展', text: '键盘可操作、响应式布局；缺失指标与零值区分；扩展任务、模型和运行时采用独立模板。' },
    ], { main: true, caption: '验收目标；负载、数据规模、心跳时限与调度周期在测试计划中细化。' }),
    table('任务书要求、需求模型与验收', ['任务书要求', '需求模型与规约', '验收场景'], [
      ['多模型训练与推理', '模型模板、训练/推理用例；训练 SPEC', '兼容模板可选；产物可保存并用于服务'],
      ['指定 GPU 与任务类型', '授权用例、训练活动、资源 SPEC', 'GPU 0 与视觉训练对示例用户被拒绝'],
      ['实时监控与日志导出', '训练活动/时序；监控需求', '状态、loss 与资源更新；原始日志可导出'],
      ['集中数据管理', '数据集/版本类；数据 SPEC', '错误行定位；处理生成新版本；历史引用保留'],
      ['需求建模与分析', '用例、活动、状态、业务类、提交时序', '状态流转、关系多重性、异常分支一致'],
      ['SRS 与核心模块规范', '训练、数据、权限和资源规则', '输入、前置条件、输出及失败场景可核对'],
    ], [0.24, 0.40, 0.36]),
    table('两组 AI 使用与人工验证', ['记录项', '第一小组', '第二小组'], [
      ['模型、版本与工具', '____________________', '____________________'],
      ['辅助环节', '____________________', '____________________'],
      ['采用的输出', '____________________', '____________________'],
      ['人工核对与修改', '____________________', '____________________'],
      ['效果与局限', '____________________', '____________________'],
    ], [0.24, 0.38, 0.38], { main: true }),
  ],
};

// 章节由位置确定，备查材料在本章内保留，课堂放映只播放明确选定的主讲页。
const modelRows = researchV2.slides.find(s => s.title === '模型结构与训练框架').rows;
modelRows[1][2] = '单独登记模型 revision、训练方法与运行环境';
modelRows[3][0] = 'DeepSeek R1\nDistill-Qwen\n1.5B';
modelRows[3][2] = '采用稠密蒸馏模板，保存基础模型与发行许可';
modelRows[5][2] = '按硬件、驱动与版本选择运行时。首个执行场景优先验证 PyTorch';
for (const deck of [researchV2, analysisV2]) {
  let number = 1;
  for (const s of deck.slides) {
    if (s.kind === 'chapter') number = s.number;
    s.chapter = number;
  }
}
