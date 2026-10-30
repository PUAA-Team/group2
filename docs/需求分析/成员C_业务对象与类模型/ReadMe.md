# 成员 C 交付说明

日期：2026-10-19　模型：MB01　版本：1.0

本目录交付成员 C 的核心业务对象清单、属性与职责、核心业务类图及完整关系说明。对象名称沿用团队统一约定，未修改 D/E/F 的认领、其他成员的时间或前序正式文档。

## 交给 H I J 的文件

- [Word 说明](./核心业务对象与类模型说明.docx)：可合入两组及合并分析报告；正文包括二十个核心对象、十九个辅助对象、属性说明、业务操作、二十七条关系、多重性和用例衔接。
- [可修改文字版](./核心业务对象与类模型说明.md)：与 Word 同源生成，图片使用相对路径。
- [高清类图 PNG](./图片/MB01_核心业务类图.png)和[矢量 PDF](./图片/MB01_核心业务类图.pdf)：一张完整模型。图中为二十个核心类及资源池辅助类，资源池用于表达节点聚合关系。
- [TikZ 源码](./源码/MB01_核心业务类图.tex)：与交付图片采用同一排版。
- [PlantUML 语义源码](./源码/MB01_核心业务类图.puml)：包含相同类、代表性属性/操作和关系，未调用外部渲染服务。不同工具排版可不同，语义应保持一致。
- [完整模型数据](./源码/core_model.json)：含完整职责、关键属性及解释、操作说明、连线端点、关系数量和约束，是重新生成图文时的单一输入。
- [实际 AI 使用与核对记录](./AI使用与核对记录.md)：H/I 可据实际人工复核情况补充，未填写的姓名及模型名称保持待填。

MB01 只绘制一次。插入 PPT 时建议先讲任务、快照、执行与资源分配主线，再对同一矢量图局部放大；不要另画另一套关系。完整模型较密，PNG 保留高清分辨率，PDF 适合放大查看。

## 与其他成员交接

C 负责的静态对象已经形成共同起点。D 使用 TrainingTask、ConfigSnapshot、ExecutionRecord 和 ResourceAllocation 表达受理、执行与停止；E 使用数据版本、产物及运行证据对象；F 使用连接、辅助请求、评估及推理对象。实体与协调服务分别命名，服务生命线不直接等同于业务类。

图上省略部分非主要属性，由对象清单补足。来源自关联通过 parentVersionId、baseVersionId、sourceTaskId 及完整说明保留。关系端的数字表示对端一个对象可关联的本端对象数量；组合和聚合的菱形都在整体端。资源分配的执行所有者与推理服务所有者恰选其一。

若 A 调整 SRS 的正式编号，H/I 同步用例追踪；若 C 的类名、数量或职责变化，先改模型数据并与 D/E/F 对齐，再重新生成文档与图片。当前正式文档日期仍记录 2026-10-13，新增智能辅助按团队已确认方向分析，不写成已经接入运行。

## 源文件与重新生成

运行时沿用已有 Python、Node、MiKTeX 和 Poppler；不需要新依赖。本轮编译、Word PDF 和逐页预览放在 D:/model-training-demo/analysis-c-20261019，项目内仅保留交付和复用源码。

在仓库根目录执行：

```powershell
& 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B 'docs/需求分析/成员C_业务对象与类模型/源码/build_diagram.py'
& 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B 'docs/需求分析/成员C_业务对象与类模型/源码/test_model.py'
```

生成的 TeX 采用 XeLaTeX、fontspec 和标准 TikZ。编译时使用 -no-shell-escape、-disable-installer 和 D 盘输出目录；从该 PDF 重新导出同名 PNG 后再运行 build_report.py，Word 和 Markdown 会采用最新模型数据及图片。生成脚本会替换本目录生成物，手改 Word 前先另存副本，避免后续生成覆盖人工排版。

```powershell
$mb01Build = 'D:/model-training-demo/analysis-c-20261019/rebuild'
New-Item -ItemType Directory -Path $mb01Build -Force | Out-Null
$mb01Source = (Resolve-Path -LiteralPath 'docs/需求分析/成员C_业务对象与类模型/源码/MB01_核心业务类图.tex').Path
$mb01Args = @('-interaction=nonstopmode', '-halt-on-error', '-no-shell-escape', '-disable-installer', '-jobname=MB01', "-output-directory=$mb01Build", $mb01Source)
& 'C:/Users/lixu/AppData/Local/Programs/MiKTeX/miktex/bin/x64/xelatex.exe' @mb01Args
Copy-Item -LiteralPath "$mb01Build/MB01.pdf" -Destination 'docs/需求分析/成员C_业务对象与类模型/图片/MB01_核心业务类图.pdf'
& 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe' -singlefile -r 400 -png "$mb01Build/MB01.pdf" 'docs/需求分析/成员C_业务对象与类模型/图片/MB01_核心业务类图'
& 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B 'docs/需求分析/成员C_业务对象与类模型/源码/build_report.py'
```

以上运行时路径为本机路径，换机器时替换工具位置；源模型不依赖当前账号。完整产物测试应在图与 Word 都重新生成后再运行。

Word 验收复用仓库 scripts/finalize_word_report.ps1，只读打开并导出到新 PDF；源码中的 render_report.py 将同版 PDF 交 documents.render_docx.rasterize 生成逐页图。更新内容或排版后必须重新看全部页面。

## 检查与尚需确认

- 模型结构、共同名称、关系端点、多重性、连线避开无关类框、图文源码、标签绘制顺序和渲染器参数已设自动检查。
- 最终 Word 共十页，已只读原生打开并导出、逐页视觉检查；PNG 为 3839 × 5378，400 DPI，PDF 为单页纯矢量。实际核对见 AI 使用与核对记录；自动检查和 AI 视觉检查不代替成员人工签字。
- 当前交付包含 TikZ 和 PlantUML 源码，未生成 CodeArts Modeling 原生工程。若提交必须采用 CodeArts，应按这份模型重建并复核导出，不将其他源码标为 CodeArts 工程。
- 外发范围、多组叠加、跨池节点和具体恢复阈值仍按团队待定项处理。

[返回分工](../分工.md) · [查看统一约定](../业务模型与用例交互模型统一约定.md) · [图的 Markdown 阅读版](./图片/MB01_核心业务类图.md)
