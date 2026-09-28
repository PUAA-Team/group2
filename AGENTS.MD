# 一、开发环境

## 本机（当前对话使用）

- Windows 11 / PowerShell
- 已经安装的系统环境以及对应路径（避免重复检查，请每次检查完更新这里）：
- 当前 C 盘空间特别少；后端本地测试、打包、运行、缓存、临时日志等不要放在 C 盘，优先同步到 D 盘英文路径下的项目子目录。
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

# 四、文档规范

所有文档放在`docs`文件夹下面，设计总体设计的部分放在该文件夹下。后续每一个步骤开发时，应该新建一个`docs/stage[x]`文件夹，并交付本阶段说明与部署说明markdown文档，文档均需保持索引放在docs/ReadMe.md。

对于需要交付的“软工”类文档，一个是需要满足当前系统真实的设计或者实现，另外要按照真实系统的文档制作，不要引用本地任何的中间文档，不要有任何“课程要求”、“软件分析”、“用户的输入要求”等等的口径。同时需要满足软件工程的规范。这类文档还有一些语言的要求：

- 禁止大量使用反驳式语句，比如“xxx不是xxx，而是xxx”，有话直接用正常的语气讲明白即可，不要靠这个显得很有逻辑，每次完成文档务必检查。
- 不要大量使用相同的markdown格式，比如连着好几个章节都是列表或者表格，满足规范的条件下不要那么像ai
- 段落间减少重复的结构，章节间不要每个章节都是同样的段落数量以及长度，仅可能有变化，最好不同章节分开思考、交给不同的agents去做
- 语言使用正常人的词汇，不要把两个不相关的字凑到一起组成新的词，这一点在每次软工类文档完成后必须仔细检查
- **后面用户经常提到的软工文档写作问题，你也要记录在这里！！！**

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