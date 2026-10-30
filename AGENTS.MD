# 真实版本当前入口

- 后续实现开工先读 `docs/stage13/实施进度与交接.md`、`docs/stage12/运行与验收.md`、`docs/stage7/实施进度与交接.md`、`docs/stage8/运行与验收.md` 和 `docs/后续功能待办.md`，再读各阶段设计与 API；仅以实际代码、测试与交接记录判定完成。stage5/6为先前阶段快照。
- 一期：文本分类、图像分类、Qwen LoRA、页面模型/数据维护及智能标注/参数/日志；Agent 和高级扩展入口后续做。
- 后端新增在 `backend`，控制平面 FastAPI 模块化单体，Worker 独立；现有 8765 原型不覆盖。架构、数据、API 和规范先更新再编码。
- 本机已批准 D 盘独立环境与基础依赖，SQLite 先联调、正式 PostgreSQL；运行目录 `D:/model-training-demo/backend-runtime`，不改系统 PATH、既有 Anaconda 或安装数据库服务。

# 一、开发环境

## 本机（当前对话使用）

- Windows 11 / PowerShell
- 本机资源暂停（2026-10-29，用户最新要求）：用户要自行使用本机CPU/GPU。已停止本任务8002验收API、独立operations和隔离Chrome进程树，核对没有平台相关本机Python进程，云端无未结束训练/服务。后续构建、测试和真实模型调用在云服务器执行；未经用户恢复授权，不再启动本机验收服务、浏览器、Worker或训练。可继续轻量代码编辑与SSH操作。GPU占用不推测、不停止用户自己的程序。
- 数据与标注B3（2026-10-29）：当前云端20261029-13b3，缓存stage13-3、schema0005_data；标注/复核/发布、样本/图像/下载、真实清洗划分增强与独立operations服务已上线。Windows94个后端用例分两批、Linux94项、前端100项、本地/公网各72项布局通过。独立“数据工作流示例”空间可演示；原数据保留，节点心跳正常但用户已暂停接收，禁止自动恢复。服务器备份pre-stage13-b3-20261029仅留服务器，兼容回退20261029-13b2-compat05已构建验证。B4设计已索引，尚未调用真实供应商；用户需在网页配置连接，密钥不进聊天。Windows读JSON显式encoding=utf-8；本机现有回环代理127.0.0.1:7897可仅给验收进程使用，不改全局设置。B3使用、证据及后续见stage13。
- 平台管理B2（2026-10-29）：当前云端20261029-13b2，缓存stage13-2、schema0004_admin；全局管理、设置、模型连接、内部邀请/密码/成员管理已上线。83项Windows与83项Linux后端、95项前端、本地/公网各51项布局通过，Worker在线、原数据保留。真实外部模型调用未验收。服务器备份pre-stage13-b2-20261029仅留服务器；兼容回滚目录20261029-13b1-compat04支持新表保留，禁止直接恢复旧库覆盖新增记录。B3～B6继续，当前API/交接在stage13。
- 完整界面恢复B1（2026-10-29）：stage13整体计划已确认，首批已上线20261029-13b1，缓存stage13-1、数据库0003_jobs。恢复工作台/目录、独立导入、四步训练、任务标签页与日志下载；70项Windows及70项Linux后端、91项前端、本地/云端各33项布局通过，Worker在线及历史CUDA训练保留。D:/model-training-demo/stage13-20261029含源码快照和隔离8002验收；服务器备份pre-stage13-b1-20261029仅留服务器。当前API见stage13/openapi.json，B2～B6仍需实施，勿把首批当作20菜单及智能辅助全部完成。
- 云服务器监控（2026-10-29）：47.93.115.188宿主已安装官方Komari Agent1.5.11，systemd服务komari-agent已启用；/opt/komari，连接用户指定监控端，Web SSH与远程命令执行禁用。凭据仅留服务器0600配置；自动注册、基础信息上报、WebSocket及重启身份保持通过。官方下载经本机现有代理和SSH传输，未改全局代理；D盘无密钥记录komari-agent-20261029，操作见docs/stage12/服务器监控.md。
- 云端部署（2026-10-29）：https://47.93.115.188:5488，SSH别名training-demo，已有id_ed25519公钥登录。宿主Debian13.4、4核/约15GiB/40GB；Docker26.1.5/Compose2.26.1/Buildx0.13.1，镜像Python3.12.16、PostgreSQL17.11，schema0003_jobs，current指向/srv/model-platform/releases/20261029-04。API仅回环18000、数据库不公开，网关HTTPS5488。IP证书至11月5日，每日两次续期检查且直连演练通过；临时本机CA代理与SSH通道已关闭。63项Windows及63项Linux后端、85项前端和12项浏览器检查通过。云端节点nod_0d8d563dfbaf44179badcf17b3848d54在D:/model-training-demo/server-deploy-prep-20261029/cloud-flow-01/worker，复用既有LLM环境；job_db847a8e9ad54ddfad8d1933938a3daa真实CUDA完成18训练/6验证/3epoch，GPU已释放。旧Worker35956/Qwen子进程35640已核实不存在，旧节点暂停、旧服务保留停止中和失联占用，不伪造回执或同时恢复旧Worker。云端账号lixu，密码仅在D盘private-admin-login.json和服务器私有文件；自助注册未实现，管理员可建号。按用户决定备份仅留服务器，不下载数据库/存储；缓存调度与OSS后做。详见stage12。
- 以下几项保留本机阶段历史快照；当前云端入口、Worker与旧服务状态以上一项stage12记录为准。
- Qwen推理约束（2026-10-29）：部署config.inference保存generate/label、instruction、labels；分类调用只发正文，由Worker按Token前缀树约束并由服务端复核。新Worker上报inference_contract_version=1，旧Worker不能领取契约任务。stage11含当前OpenAPI、设计与证据。62项后端、85项前端、真实Tokenizer/Transformers CPU检查和128条真实正文调用复测通过。部署切换只针对原Qwen服务，权重及历史训练不改；服务job_24866d2202e54a339cadb30cbeaf5bc2随后在stage12交接时进入停止中，失联占用保留。现有CPU演示服务已由用户停止，不能擅自恢复。D盘证据qwen-contract-rollout-20261029，操作PID以记录为准。
- 真实资源和训练部署（2026-10-29）：8000应用已迁移0003_jobs，原有数据保留；stage7/8/9包含资源、任务、执行、评估、服务和密钥。Worker源码在`worker/src/training_worker`，运行目录D:/model-training-demo/backend-runtime/local-worker。独立LLM环境D:/model-training-demo/worker-llm-runtime/.venv只读复用原Torch2.5.1+cu121；Transformers4.57.6、PEFT0.18.1、Accelerate1.15.0、safetensors0.8.0、Pillow12.0.0，后端Pillow12.3.0。权重缓存D盘，Qwen固定提交c1899de289a04d12100db370d81485cdf75e47ca。文本CPU、图像CUDA、Qwen LoRA真实训练/评估/推理通过，证据backend-runtime/training-flow-20261029-01。82项前端及27项浏览器页面检查通过。运行加`-EnableLocalWorker`；后台PID以backend-process.json核对。持续服务占用设备，不用时先停止服务再停止Worker。当前未实现智能辅助API、容器/Linux/多机/PostgreSQL验收；禁止凭已提供Dockerfile声明部署成功。Windows性能计数可能聚合其他GPU，显存是否够用以nvidia-smi与真实CUDA结果核实；不停止用户程序或改驱动。
- 真实前端联调（2026-10-28）：`frontend/live`，真实页面入口 `http://127.0.0.1:8000/`，旧 8765 原型保留。同源 Cookie/内存 CSRF；仅布局偏好落 localStorage，禁止退回原型数据。已接初始化、登录、空间/成员、用户/组、模型和数据版本/预览、审计。43 项后端、73 项前端及 14 类浏览器流程、30 项响应式检查通过，D 盘证据 `backend-runtime/web-qa-20261028-final`，实拍索引 `docs/stage6/previews`。首次网页设置显式用 `run_backend.ps1 -BackendAction serve -EnableBrowserSetup`，默认关闭，限定回环及本机 Host，初始化后不可重建。原 API 增量和机器契约见 stage5；训练、资源执行、推理、三项智能辅助待后续。无新增依赖，运行与备份均复用 D 盘；当前实现与继续入口以 stage6 为准。
- 真实后端 M1（2026-10-28）：`backend`，独立环境 `D:/model-training-demo/backend-runtime/.venv`，Python 3.12.14、FastAPI 0.162.0、SQLAlchemy 2.1.6、Alembic 1.20.1；完整依赖在 `backend/requirements.lock.txt`，pip check 通过。运行 `backend/scripts/run_backend.ps1 -BackendAction serve|migrate|test`；测试默认创建 D 盘随机目录。34 项后端测试与 63 项原有前端测试通过，后者在沙箱使用 `--test-isolation=none`。SQLite 已显式迁移至 `0001_m1`；8000 只监听回环，无默认管理员；初始化与 PostgreSQL/Linux 后续部署见 `docs/stage5/运行与部署.md`。现有 8765 原型未接入后端。禁止把三条训练器的登记模板当作执行实现，Worker、训练和智能辅助待后续批次。当前 Starlette/HTTPX 测试适配器有一项弃用提示，没有加装 HTTPX2。
- 已经安装的系统环境以及对应路径（避免重复检查，请每次检查完更新这里）：
  - PDF 文字提取：Codex 随附 Python `C:\Users\lixu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`，已验证包含 `pdfplumber`、`pypdf`；Poppler 的 `pdftoppm.exe`、`pdfinfo.exe` 位于 `C:\Users\lixu\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin`。项目复用脚本为 `scripts/pdf_to_markdown.py`，默认扫描 `docs`。未安装 OCR 工具，图片文字需查看原 PDF。
  - 前端测试：Codex 随附 Node.js `C:\Users\lixu\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`（2026-10-28 本轮实际运行 v24.22.1），本项目可直接运行 `node --test`，沙箱使用 `--test-isolation=none`，无需安装第三方包。
  - 前端浏览器验收：Chrome 位于 `C:\Program Files\Google\Chrome\Application\chrome.exe`；本次使用隔离的无界面浏览器和 `frontend/scripts/qa-browser.mjs` 检查。测试配置已移至 `D:\model-training-demo\qa-browser-profile`，未改系统环境变量或全局设置。
  - 前端视觉审查：`frontend/design-review` 为独立的四套视觉样例，8766 端口；浏览器实拍、响应式和交互记录位于其 `previews` 目录。随附 Node 已具备 Sharp，可运行 `scripts/build_design_review_contact_sheets.mjs` 生成对照图，无新增依赖。本机 Python 静态服务将 `.mjs` 识别为 `text/plain`，浏览器模块使用 `.js`；未修改系统 MIME 配置。
  - 完整原型模板迁移：8765 端口使用 `console-4` 统一缓存版本，云管控导航、深青绿主操作、蓝色详情入口、8/6/10px 圆角，所有文字样式至少 14px。完整原型 26 项测试、含视觉样例共 63 项测试通过；102 项浏览器页面检查和 11 类弹窗检查记录在 `docs/stage4/previews/browser-audit.json`。提示词、运行说明、参考图与两份调整前备份位于 `docs/stage4`。本轮没有安装依赖、创建额外 Chrome 配置或修改系统设置。
  - 云控制台组件审查：新样例位于 `frontend/design-review/cloud-v2`，复用 8766 静态服务；25 项样例测试、24 项响应式与本轮交互检查记录在其 `previews` 目录。对照图复用 `scripts/build_cloud_review_contact_sheets.mjs`，浏览器实测字号和尺寸随检查记录保存。截图拼接脚本可能返回运行中会话，须等待完成再读取图片。入口、样式与界面模块的版本标识须一致，当前为 `palette-3`；避免旧模块缓存造成部分更新。
  - PPT 制作：随附 Node 的 `@oai/artifact-tool` 可导入模板并生成原生可编辑表格/图表。复用代码位于 `scripts/presentations/`；构建和渲染放在 `D:\model-training-demo\defense-ppt-20261011`。校验子进程需要进程内 `RUNTIME_NODE_MODULES` 指向随附 `dependencies\node\node_modules`，不修改系统环境。当前沙箱下内容测试用 `node --test --test-isolation=none scripts/presentations/content.test.mjs`，避免子进程创建被拦截。
  - 参考材料阅读：旧 Word 可用本机 Word COM 只读导出，复用 `scripts/presentations/render-source-report.ps1`；PPT 按页提取复用 `extract-pptx-text.py`。本轮补充 demo 构建/渲染位于 `D:\model-training-demo\reference-review-20261012`。原生连线需置于模板背景之上；图片裁切须给出完整四边参数。未安装额外图像库。
  - 调研 PPT 二次修订：构建/预览位于 `D:\model-training-demo\research-ppt-update-20261012`，复用 `build-research-v3.mjs` 与 `verify-research-v3.py`。模板原方法页直接复制，保留其 Calibri/黑体字体；新增页使用微软雅黑。`artifact-tool` 的坐标属性对象需逐项读取，不用对象展开复制；若确需修改导入文字，先固定样式与位置，再用 `text.set` 写入段落。
  - 合并 PPT 建模优化：D 盘目录为 `D:\model-training-demo\modeling-ppt-update-20261012`；复用 `build-modeling-update.mjs`，原稿前部通过 `merge-modeling-deck.py` 保留。OOXML 关系兼容绝对/相对路径，新幻灯片使用标准 `ppt/slides/slideN.xml`；内容类型用默认命名空间。原稿正文还使用等线，字体校验清单须包含它。仅消除图表缓存与原工作簿之间小于 `1e-14` 的浮点字符串差异，实质数值差异必须停止核对。活动结束节点外圆用透明填充，避免遮住内圆。
  - PPT 原生兼容验收：使用 Windows PowerShell 5.1 `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` 和已安装的 PowerPoint 16.0 COM，复用 `scripts/presentations/verify-powerpoint-native.ps1`；以 UTF-8 读取脚本再执行，避免旧 PowerShell 对无 BOM 文件的编码误读。`Open2007` 最后一个参数必须为 `0`，关闭自动修复。只读打开、PNG 导出、保存测试副本后重开均已验证，记录位于上述 D 盘目录的 `native-*`。合并时只保留一个备注母版，新备注页复用原母版；导入版式和幻灯片母版需分配未占用编号。包检查通过仍须原生打开，不得退出或修改用户已有 Office 文稿。
  - Word 文档编辑与验收：随附 Python 包含 `python-docx`、`lxml`、`pdf2image`；本机 Word 16.0 COM 可禁用修复只读打开、更新目录、另存新副本及导出 PDF。复用 `scripts/update_research_compute_report.py`、`scripts/finalize_word_report.ps1` 和 `scripts/render_word_native.py`。运行时没有 LibreOffice，PNG 沿用 documents 技能的 `render_docx.rasterize`，由 Word 替换 PDF 转换步骤，140 DPI。工作、快照及预览位于 `D:\model-training-demo\research-compute-20261013`；不退出或修改用户已有 Word 文稿，不安装软件或改全局环境。
  - UML TikZ 图片：已有 MiKTeX 24.1，XeLaTeX 位于 `C:\Users\lixu\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe`；TikZ、standalone、fontspec 与微软雅黑已验证。当前 xeCJK 与 LaTeX 内核版本不匹配，使用 fontspec 和 XeTeX 原生中文断行，不升级环境。构建放在 `D:\model-training-demo\srs-uml-20261013`，禁用自动安装与 shell escape；输出目录参数通过 PowerShell 参数数组传入。完整源码在 `docs/需求调研+需求分析/初步提交材料/用例活动图/源码`；批量生成、插图与检查分别复用 `scripts/build_activity_diagrams.py`、`scripts/insert_activity_diagrams.py`、`scripts/test_activity_batch.py`，已确认样图另用 `scripts/test_activity_sample.py`。Word 原稿存在 VML 图片，不能只按 `w:drawing` 统计；保留 VML，替换单张旧图时同步清除该图 gfxdata 缓存。Word 保存可能重命名内部图片，用内容哈希核对，不依赖包内文件名。最终验收目录为 D 盘 `srs-uml-20261013\batch-20261013`。
  - SRS 文字修订与原图保留：复用 `scripts/srs_revision`，构建和预览位于 `D:\model-training-demo\srs-revision-20261020`。直接 Word 另存可能删除未引用图片并规范化 VML；要求图片完全原样时，保留局部 OOXML 修订包，仅合入 Word 更新的目录和书签，再只读导出 PDF。核对全部媒体哈希、DrawingML/VML 引用、显示尺寸和裁切。向新 ZIP 写入时须复制 `ZipInfo`，避免写入改变仍在读取的源目录偏移。当前 documents/PDF 技能版本为 `26.1015.12040`，渲染复用旧 helper 时仅在进程内指向此版本，不改全局环境。
- 当前 C 盘空间特别少；后端本地测试、打包、运行、缓存、临时日志等不要放在 C 盘，优先同步到 D 盘英文路径下的项目子目录。
- GPU接入复核（2026-10-20）：本机 `nvidia-smi` 实测 RTX 4060 Laptop GPU、8188 MiB、驱动566.24。`worker_agent.zip` 的中央服务与Worker可用随附Python运行标准库数据概况任务，无需安装PyTorch即可验证接入；15项检查和截图见 `docs/需求调研+需求建模/初步提交材料/支撑材料/原型验证_20261020`。运行、浏览器、日志与排版检查位于 `D:/model-training-demo/research-revision-20261020`，控制端只绑定127.0.0.1:8875。本轮未安装依赖或更改全局配置。
- 本机没有 Docker Compose 环境；后端日常本地测试不要依赖 Docker Compose。

## 本地路径约定

./docs：文档目录

（随时补充）

# 二、工作流程

全程中文对话。

1. **先查后动**：改代码前先找相关文档，不确定就调查清楚或直接问用户
2. **先说再做**：编码前描述方案等批准，需求不明先澄清
3. **用户决策**：尽可能对于任何不清楚的需求或者设计要求，都要询问用户，直到完全搞明白为止才允许继续，可以和用户多轮对话，一定要刨根问底，完全确认清楚之后才能动工
4. **拆大为小**：改动超 3 个文件的任务先分解
5. **参考先例**：实现功能优先去 GitHub 搜参考代码
6. **写完必跑**：代码完成后验证通过再交付，同时对照编码规范等完成前端、后端检查与测试。
7. **收尾检查**：完成后列出潜在问题；发现 bug 先写复现测试再修

## 确认机制

- **重大变更须确认**：文件结构增删、新功能、新页面UI、核心算法、新依赖、API 定义——先提方案问"您同意吗？"，批准后再动
- **局部优化可自主**：函数内部重构、命名优化等不影响外部调用的可以直接做，报告里说明即可

## 遇到问题必须停

命令报错、测试不过、发现逻辑漏洞——立即停止，报告：遇到了什么、原计划是什么、建议怎么办。

# 三、编码规范

如无必要，勿增实体（指不必要的复杂度和重复代码；可复用的公共组件应积极创建）。

遵循 KISS、YAGNI、DRY、SOLID。编码风格与代码库保持一致，优先复用已有函数。

前端界面必须遵循以下要求：

- 前端界面任何重要的设计、布局都要与用户讨论确认，如有必要可以新建临时目录用纯前端制作demo，可以多方案给用户对比，你多干一点活用户就能少让你返工几次
- 前端界面保持界面统一性，需要遵从用户的指令，不要任何炫彩、紫色等炫酷的颜色，我们做的系统不需要炸裂的视觉效果，尽可能方便使用。
- 前端设计时需要注意响应式布局等问题，不要在某些地方堆积过多文字，你需要自行检查前端界面在不同尺寸与环境下会不会出现文字被迫换行、模块挤压等等的前端严重问题。
- 前端要一个干净的界面，用户有独立自主使用系统的能力，不需要你写任何冗余的介绍、说明文字到系统上面，这点尤其要检查，不要把说明书写到系统上面，尤其注意这种多余的语句以及重复的话，只有极其必要的地方才加入大量的解释文字。
- 前端参照用户的要求，菜单与分类需要明确，不能过于冗余或过于简单。
- 用户实现的所有功能如果只是前端demo实现，必须在“待完成任务”文档中标明哪些部分哪些功能只有前端界面，并不完整，尽可能在设计的时候不要做这样的demo，除非用户强烈要求，比如想要参考前端界面时。
- 圆角不要过大，也不要过小，符合正常人类的编码习惯，参考apple官网、国内大厂类似系统的前端界面。
- 配色不要过于单一，也不要过于复杂。
- **后面用户经常提到的前端设计问题，你也要记录在这里！！！**
- 视觉方案需要先交付可浏览的多方案样例和真实页面截图供用户选择；不同方案应体现信息层级和业务布局的差异，避免仅更换配色、统一套用大圆角卡片。未经采纳，独立样例保留，不覆盖现有原型。
- 多方案审查必须同时设计主体组件：正文、标题、任务名称、表头、行高、按钮、选择框、表单、状态、图表与弹窗均需给出体系规则。参考真实云控制台和官方组件资料，记录项目方案值；每套内部统一，跨方案通过实际尺寸和页面截图核对差异。
- 用户偏好紧凑的云管控主体，不宜为了制造方案差异过度放大字号、行高和统计数字。主色应可快捷试选；状态避免默认套用彩色小圆点或胶囊。多区块页面按业务内容分区，标题、标签和筛选保持开放布局，相关内容共享局部面板，避免整页大边框和重复小卡片。
- 已采纳云管控型导航框架：完整原型使用深青绿主操作、8px 面板、6px 控件及 10px 弹窗圆角。侧栏隐藏可见长条滚动条但保留滚动；收窄后仅显示图标，彻底隐藏文字与二级列表，保留分组状态和滚动位置。列表状态使用圆形外圈与内部语义符号，默认仅显示图标，悬停或键盘聚焦查看中文状态。详情可保留状态文字。
- 主体采用中性色，主色集中用于主操作、导航选中、当前标签、焦点和少量关键曲线。正文、任务名、统计数字、分类标识与普通组件不统一染成主题色；成功、运行、等待、失败、停止使用独立语义色。复用规则见 `docs/stage4/云管控型前端模板提示词.md`。
- 参考用户提供的阿里云 PAI 界面：可进入详情的实体名称使用加粗蓝色，静态名称保持黑灰；独立项目、模型或资源可用白色内容区与浅灰底部区域的卡片。保留已确认菜单和状态交互，不引入参考图的橙色品牌、紫色装饰或冗余宣传文字。
- 所有位置取消解释小字，尤其禁止“大字加灰色小字”“名称下面再加小号说明”的模式。正文、表头、标签、菜单、表单与操作不低于 14px。配额合成说明、重复导语、卡片中的格式长描述写到文档；短任务类型、版本、训练方式可改为标签框。邮箱、模型等有效业务信息保留为独立表格列或明确字段。安全警示、必填限制和错误反馈用正常字号保留，不靠隐藏样式清理文案。

# 四、文档规范

所有文档放在`docs`文件夹下面，设计总体设计的部分放在该文件夹下。后续每一个步骤开发时，应该新建一个`docs/stage[x]`文件夹，并交付本阶段说明与部署说明markdown文档，文档均需保持索引放在docs/ReadMe.md。

对于需要交付的“软工”类文档，一个是需要满足当前系统真实的设计或者实现，另外要按照真实系统的文档制作，不要引用本地任何的中间文档，不要有任何“课程要求”、“软件分析”、“用户的输入要求”等等的口径。同时需要满足软件工程的规范。这类文档还有一些语言的要求：

- 禁止大量使用反驳式语句，比如“xxx不是xxx，而是xxx”，有话直接用正常的语气讲明白即可，不要靠这个显得很有逻辑，每次完成文档务必检查。
- 不要大量使用相同的markdown格式，比如连着好几个章节都是列表或者表格，满足规范的条件下不要那么像ai
- 段落间减少重复的结构，章节间不要每个章节都是同样的段落数量以及长度，仅可能有变化，最好不同章节分开思考、交给不同的agents去做
- 语言使用正常人的词汇，不要把两个不相关的字凑到一起组成新的词，这一点在每次软工类文档完成后必须仔细检查
- **后面用户经常提到的软工文档写作问题，你也要记录在这里！！！**
- 答辩 PPT 先完成逐页内容与要求覆盖设计，再按用户模板制作。平台调研逐一说明具体发现、借鉴和限制，问卷回到原始计数核算。成员与实际 AI 使用情况可留填写页；按用户要求预留 CodeArts 插图框，不编造人员、采访、硬件实测或训练结果。文字减少重复的否定式总结，检查图表坐标范围、中文标点和英文名称换行。
- PPT 必须有清晰的章节组织，按内容选用不同版式，避免连续大量页面套用“标题、导语、表格、底部总结”同一种结构。删除口号、重复结论及制作过程说明；操作提示与提交待办放到使用说明，正文保留具体研究发现、数据、业务规则及必要限制。统一模板的品牌元素，章节过渡与正文排版分别设计。
- 调研 PPT 适当加入团队资料中的真实平台截图和问卷统计图片，保留可辨认的关键字段。来源记录放在制作核对文档；PPT 正文与备注不写本地材料文件名、页码、图片编号、提取过程、统计纠错过程和“不能据此声称”等制作提醒。原始统计报告、问卷网页截图和重新绘制的统计图要准确区分；图片中的选项名称、人数必须与文字和图表逐项核对，不用演示截图冒充调研证据。
- 平台调研以 BML 业务流程为主展开，其他平台保留有依据的差异。答辩 PPT 设置任务书目标与平台需求、需求模型/规约与验收的对应位置，不只罗列功能；ModelArts 的任务书指定调研范围仍需覆盖。成员分工和实际 AI 使用情况留真实填写字段。
- 需求调研开篇详细说明调研方式，可复用原方法页；团队分工与时间规划放在内容后面。正文删除所有灰色辅助小字，页标题按调查的业务主题命名，BML 与其他平台的发现放在具体内容中，适当使用团队已有的华为真实界面图。问卷先说明样本与调查范围，精选关键数据并解释采用决定；所有页面使用直接陈述，避免反驳式语句。
- 对明确可以复用的现有 PPT 页面，优先整页复制，保留原文与原排版；未经要求，不重复改写和重排。
- 第二阶段为需求建模，主线是总体需求分解、用例/活动/状态模型与核心 SPEC、非功能需求。业务类图和关键用例时序图属于第三阶段需求分析，不能混入第二阶段主讲范围。需求建模 PPT 同样删除灰色辅助小字、重复章名、空泛导语和页底总结，保留可读的业务条件及验收目标。
- UML 模型图片使用黑白论文风格，白底黑线，不使用彩色填充、阴影或装饰。动作、判定、合并、守卫条件、责任泳道与结束节点按 UML 2.5.1 核对；节点、标签和连线保持足够间距。先编译并逐张视觉验收，再插入文档检查分页与最终字号。

> 以上只针对软工类文档，即课程要求提交的文档（不确定是不是可以检查课程要求或者问用户，这种文档一定仔细对待），其他的中间文档、设计、计划等等可以不用那么复杂。

所有文档引用的图片等资源使用相对路径。

# 五、项目其他要求

- 开工前必读：`docs/ReadMe.md`，里面包含项目介绍和已有文档索引，若没创建则新创建，尤其是根据课程要求补上项目介绍以及进度
- 新增前端/后端/功能设计需要写到文档里，需要通过文件夹分类文档，并添加到索引中
- 遇到问题多查文档库，解决后也往文档库里记录
- 任何接下来需要用户自己做的事情都要写好完整文档，包括编译、后端部署等，尽可能完成你可以完成的所有功能。
- 用户明确说"之后再做"的功能不要只留在对话里，必须记录到 `docs/后续功能待办.md`，不要写散在某个 stage 文档里。
- 所有代码新的设计都要服从高内聚低耦合的设计理念，严禁形成单个代码文件上千行，严格遵守项目结构，提高代码的可扩展性与简洁性、可维护性。
- 所有代码的必要位置请使用中文注释，不要太多，只在必要位置使用。
- 本机没有 Docker Compose 环境；后端日常本地测试不要依赖 Docker Compose。
- 其他的编程要求也参考课程要求pdf
- 如果用户给出一个pdf或者文字类的图片时，请在同目录下转为同样名字的markdown文件并索引，pdf工具也请记录到开发环境中

# 六、高风险操作（须确认）

以下操作执行前必须告知用户并获得确认：

| 类别     | 示例                                  |
| -------- | ------------------------------------- |
| 文件系统 | 删除文件/目录、批量修改、覆盖系统文件 |
| 版本控制 | git commit / push / reset --hard      |
| 系统配置 | 环境变量、全局配置、权限变更          |
| 数据操作 | 删数据、改表结构、批量更新            |
| 网络请求 | 含敏感数据的请求、调用生产环境 API    |
| 包管理   | 全局安装/卸载、更新核心依赖           |

补充要求：

- 凡是安装开发环境、修改环境变量、修改系统路径前，必须先展示将要修改的具体内容，征得用户同意。
- 执行前必须做好备份，并明确告诉用户备份位置或回滚方式。
- 优先采用影响范围最小的方式，避免破坏用户已有命令与环境。

确认格式：

> ⚠️ 危险操作：[操作内容]，影响范围：[说明]，风险：[后果]。确认执行？



# Other Requirement

若与上面有冲突，以上面为主。

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
