"""从同一模型生成业务对象说明的 Word 和 Markdown。"""
import argparse
import json
from pathlib import Path
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


TITLE="大模型集成训练平台核心业务对象与类模型说明"
STEM="核心业务对象与类模型说明"


def set_font(run,size=11,bold=False):
    run.font.name="Times New Roman"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"),"宋体")
    run.font.size=Pt(size)
    run.font.bold=bold
    run.font.color.rgb=RGBColor(0,0,0)


def table(doc,headers,rows,widths):
    result=doc.add_table(rows=1,cols=len(headers))
    result.autofit=False
    for col,width in zip(result.columns,widths): col.width=Cm(width)
    properties=result._tbl.tblPr
    borders=OxmlElement("w:tblBorders")
    for name in ("top","left","bottom","right","insideH","insideV"):
        border=OxmlElement("w:"+name)
        for key,value in {"val":"single","sz":"4","color":"D9D9D9"}.items(): border.set(qn("w:"+key),value)
        borders.append(border)
    properties.append(borders)
    repeat=OxmlElement("w:tblHeader"); result.rows[0]._tr.get_or_add_trPr().append(repeat)
    def fill(row,values,head=False):
        # 短业务条目整体保留；表格仍按行跨页并重复表头。
        if not head and sum(len(str(v)) for v in values)<700:
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for index,(cell,value,width) in enumerate(zip(row.cells,values,widths)):
            cell.width=Cm(width)
            cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cp=cell._tc.get_or_add_tcPr()
            margins=OxmlElement("w:tcMar")
            for side,n in (("top","65"),("bottom","65"),("left","85"),("right","85")):
                e=OxmlElement("w:"+side); e.set(qn("w:w"),n); e.set(qn("w:type"),"dxa"); margins.append(e)
            cp.append(margins)
            if head:
                shade=OxmlElement("w:shd"); shade.set(qn("w:fill"),"F2F2F2"); cp.append(shade)
            cell.text=""
            for n,line in enumerate(str(value).split("\n")):
                p=cell.paragraphs[0] if n==0 else cell.add_paragraph()
                p.paragraph_format.space_after=Pt(2)
                p.paragraph_format.line_spacing=1.12
                p.paragraph_format.keep_with_next=head
                if head or (index==0 and len(str(value))<7): p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                size=9.5 if index==0 and n>0 and line.isascii() and len(line)>19 else 10.5
                set_font(p.add_run(line),size,head)
    fill(result.rows[0],headers,True)
    for values in rows: fill(result.add_row(),values)
    doc.add_paragraph().paragraph_format.space_after=Pt(2)
    return result


def make_report(data,folder):
    doc=Document()
    sec=doc.sections[0]
    sec.page_width,sec.page_height=Cm(21),Cm(29.7)
    sec.top_margin,sec.bottom_margin,sec.left_margin,sec.right_margin=Cm(1.9),Cm(1.9),Cm(2),Cm(2)
    for name in ("Normal","Title","Heading 1","Heading 2","Caption"):
        style=doc.styles[name]
        style.font.name="Times New Roman"
        style._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"),"宋体" if name in ("Normal","Caption") else "黑体")
        style.font.color.rgb=RGBColor(0,0,0)
    normal=doc.styles["Normal"]
    normal.font.size=Pt(11.5)
    normal.paragraph_format.line_spacing=1.25
    normal.paragraph_format.space_after=Pt(6)
    for name,size in (("Title",20),("Heading 1",15),("Heading 2",12)):
        doc.styles[name].font.size=Pt(size)
        doc.styles[name].paragraph_format.space_before=Pt(12)
        doc.styles[name].paragraph_format.space_after=Pt(7)
    footer=sec.footer.paragraphs[0]
    footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    field=OxmlElement("w:fldSimple"); field.set(qn("w:instr"),"PAGE"); footer._p.append(field)
    doc.core_properties.title=TITLE
    doc.core_properties.author="项目组"
    doc.core_properties.subject="核心业务对象及 UML 静态类模型"
    md=["# "+TITLE,"", "版本 1.0　2026-10-19", ""]
    doc.add_paragraph(TITLE,style="Title")
    doc.add_paragraph("版本 1.0　2026-10-19")
    def h(title): doc.add_heading(title,level=1); md.extend(["## "+title,""])
    def p(text): doc.add_paragraph(text); md.extend([text,""])
    def t(headers,rows,widths):
        table(doc,headers,rows,widths)
        md.extend(["| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |"])
        md.extend("| "+" | ".join(str(v).replace("\n","；") for v in row)+" |" for row in rows)
        md.append("")
    core=[c for c in data["classes"] if c["core"]]
    by_key={c["key"]:c for c in data["classes"]}
    h("1 分析范围与对象识别")
    p("平台围绕数据准备、模型选择、训练提交、资源调度、过程监控、产物登记、评估和推理提供业务支持。静态模型识别二十个核心对象，并以辅助对象说明授权、数据处理、运行证据、智能建议和恢复记录。核心类图展示这些对象之间的主要关系。")
    p("对象识别结合需求中的业务名词与用例事件流：具有独立身份、业务状态或需要长期追溯的概念保留为对象；可重复使用的模型和数据按资产与版本分离；任务配置、实际执行与资源占用分别记录。前端、调度器、任务服务等协调职责在交互模型中表达。")
    p("训练项目组织多次实验，训练任务固定一套已受理配置，执行记录追踪一次实际派发。通过这一划分，参数修改、内部传输重试、用户重跑和检查点恢复可以分别说明，历史配置及结果保持可追溯。文本、视觉及表格任务由模型模板和数据契约表达，具体执行能力按接入结果登记。")
    h("2 核心业务对象清单")
    p("下表给出核心职责和关键属性含义。ID 表示稳定业务标识，Ref 表示受控对象引用；集合、状态和契约类型按业务含义描述，物理存储类型在后续设计中确定。")
    t(["业务对象","核心职责","关键属性说明"],[[c["id"]+" "+c["name"]+"\n"+c["key"],c["responsibility"],c["attributeNotes"]] for c in core],[3.9,3.2,9.9])
    h("3 辅助业务对象")
    p("辅助对象补充核心类的业务细节。资源池进入总图，用空心菱形表达节点的组织关系；其他辅助对象在文字中保留完整职责，交互模型可按场景引用。")
    t(["对象","职责与关键属性"],[[x["name"]+"\n"+x["key"],x["description"]] for x in data["supplementary"]],[4.4,12.6])
    h("4 核心业务类图")
    p("MB01 包含二十个核心类和资源池辅助类。每个类显示关键属性及代表性业务操作，全部属性职责由对象清单补充。R01 至 R27 对应下一节关系说明；菱形位于整体端，多重性标在对应端。")
    image=folder/"图片/MB01_核心业务类图.png"
    para=doc.add_paragraph(); para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    shape=para.add_run().add_picture(str(image),width=Cm(16.6))
    shape._inline.docPr.set("descr","MB01 核心业务类图，包含二十个核心类、资源池及二十七条关联、组合和聚合关系。")
    cap=doc.add_paragraph("图 1  核心业务类图 MB01",style="Caption"); cap.alignment=WD_ALIGN_PARAGRAPH.CENTER
    md.extend(["![MB01 核心业务类图](./图片/MB01_核心业务类图.png)",""])
    h("5 关系与多重性")
    p("表中“甲端—乙端”表示关联端名称及该端数量。例如 User[1]—TrainingProject[0..*] 表示每个项目由一个用户负责，而一个用户可负责多个项目。组合用于独占并整体归档的对象；普通关联对象可以按各自保留策略独立存在。")
    rows=[]
    kinds={"association":"关联","composition":"组合","aggregation":"聚合"}
    for r in data["relations"]:
        a,b=by_key[r["a"]],by_key[r["b"]]
        ends=f'{a["name"]}[{r["ma"]}]\n{b["name"]}[{r["mb"]}]'
        meaning=r["constraint"]
        rows.append([r["id"]+"\n"+kinds[r["kind"]],ends,meaning])
    t(["关系","两端及多重性","业务含义与约束"],rows,[1.5,5,10.5])
    p("来源关系按可选自关联保留：DatasetVersion.parentVersionId 追踪版本处理来源，ModelVersion.baseVersionId 追踪基础权重依赖，TrainingTask.sourceTaskId 追踪克隆或重跑来源。一个对象至多有一个此类直接来源，来源对象可关联多个后继；来源链不允许形成循环。")
    h("6 业务操作与交互职责")
    p("实体负责与自身状态和数据紧密相关的操作，控制职责负责跨对象协调。例如训练提交由任务服务组织授权、数据和模板校验，再固定快照并受理；TrainingTask 负责自身状态约束，ConfigSnapshot 保持输入不变，ResourceAllocation 负责占用事实。业务操作的返回结果包含成功与具体失败原因。")
    t(["对象","操作输入输出与职责"],[[c["name"]+"\n"+c["key"],c["operationNotes"]] for c in data["classes"]],[4.4,12.6])
    h("7 生命周期与关键约束")
    p("任务使用草稿、提交中、排队中、运行中、停止中、成功、失败、已取消和已停止九个主状态。下载、准备环境与产物上传记录为执行阶段。成功、失败、已取消、已停止为终态；用户重跑创建关联的新任务。")
    p("排队取消登记为已取消，实际启动后的停止登记为已停止。节点失联、停止超时及清理失败先保留待核查占用；任务结果与设备是否已释放分别判断。训练进程正常退出后，必要产物完整并校验通过才能确认业务成功。")
    p("用户组提供基础授权，个人允许与组允许合并后排除任一来源的显式禁用；空间和对象权限继续约束访问。个人配额取组上限与个人上限的较小值，未设置个人上限时继承组上限，启动前扣除已用与预留。当前采用单主组工作模型，多组叠加及共享总配额继续确认。")
    p("数据版本、模型版本和已受理配置保持确定输入。模型产物、日志、指标和故障关联具体执行，事件同时保留源时间、平台接收时间与去重标识。GPU 使用稳定设备标识定位，节点内编号仅用于展示，容量明确采用 MiB 或 GiB。")
    p("外部大模型连接与本平台训练权重分别管理。智能辅助请求保存输入版本、连接、授权与候选结果；建议经人工确认并再次检查权限及版本后，应用到新配置或新数据版本。外发日志、配置和样本范围尚待确定，授权落实前不发送真实内容。辅助调用失败保留人工业务路径。")
    h("8 用例覆盖与模型衔接")
    t(["业务范围","主要对象","用例与分析重点"],[
        ["账号与权限","User、Role、UserGroup、Workspace、AuditRecord；授权与配额辅助对象","UC-IAM-01 至 UC-IAM-06；登录主体、空间成员、对象访问和只读约束。"],
        ["模型与数据","ModelTemplate、ModelVersion、Dataset、DatasetVersion、ModelArtifact；处理与标注记录","UC-BM-01 至 UC-BM-03、UC-DAT-01 至 UC-DAT-07、UC-MDL-01 至 UC-MDL-04；版本来源、可用性及引用检查。"],
        ["训练与资源","TrainingProject、TrainingTask、ConfigSnapshot、ExecutionRecord、ComputeNode、GPUResource、ResourceAllocation、ResourcePool","UC-TRN-01 至 UC-TRN-08；训练受理、调度、取消/停止、运行事实及新任务重跑。"],
        ["监控与恢复","ExecutionRecord、ComputeNode、GPUResource；指标、日志、故障、检查点、恢复记录","UC-MON-01 至 UC-MON-07；真实证据、失联核查、完整产物和资源清理。"],
        ["推理与治理","InferenceService、ModelVersion、ResourceAllocation、AuditRecord；使用记录和调用凭据","UC-INF-01、UC-INF-02、UC-ADM-01 至 UC-ADM-08；发布就绪、独立占用、资源与审计治理。"],
        ["智能辅助扩展","ExternalModelConnection、AssistantRequest；候选结果与采纳记录","日志解释、参数推荐、辅助标注和人工采纳；新增规约编号由需求修订统一登记。"]],[2.5,6.3,8.2])
    p("关键训练提交交互按前端、任务服务、调度器、执行器、监控采集与前端推送组织。静态模型中的任务、快照、执行、资源分配和产物分别对应受理、派发、运行及完成事实；交互图沿用本说明的类名和状态，不以服务数量推导部署进程。")
    h("9 待定事项")
    p("外发授权范围、外部模型能力与预算、节点跨池归属、多用户组叠加、组总额度共享以及检查点续训的首批支持范围需要进一步确认。在规则明确前采用受限默认行为，并保留拒绝、待核查和人工处理路径。具体超时与重试参数在统一配置中确定。")
    h("10 参考资料")
    p("系统需求规格说明书，2026-10-13 版本。")
    p("核心模块开发规范，2026-10-13 版本。")
    p("Object Management Group，Unified Modeling Language 2.5.1，https://www.omg.org/spec/UML/2.5.1/。")
    # 清除默认模板的段落装饰线，正文及标题保持黑白。
    for element in (doc.styles.element,doc.element):
        for border in list(element.xpath(".//w:pBdr")):
            border.getparent().remove(border)
    doc.save(folder/(STEM+".docx"))
    (folder/(STEM+".md")).write_text("\n".join(md)+"\n",encoding="utf-8")
    diagram_note="# MB01 核心业务类图\n\n![核心业务类图](./MB01_核心业务类图.png)\n\n完整对象与关系见[模型说明](../核心业务对象与类模型说明.md)。同名 PDF 为矢量图，[TikZ 源码](../源码/MB01_核心业务类图.tex)和[PlantUML 语义源码](../源码/MB01_核心业务类图.puml)均保留。\n"
    (folder/"图片/MB01_核心业务类图.md").write_text(diagram_note,encoding="utf-8")
    return {"document":str(folder/(STEM+".docx")),"coreObjects":len(core),"relations":len(data["relations"])}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=Path(__file__).with_name("core_model.json"))
    args=parser.parse_args()
    model=json.loads(args.source.read_text(encoding="utf-8"))
    print(json.dumps(make_report(model,args.source.parent.parent),ensure_ascii=False))
