"""在原始 OOXML 上局部修订文字，原包的图片和关系文件逐字节保留。"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree as E

from requirements import (
    ACCEPTANCE, ACTOR_ROW, DATA_ITEMS, FAULTS, NFR_ADDITIONS, NFR_UPDATES,
    OTHER_STATES, PARAGRAPHS, PRIORITIES, RELATIONS, RULES, TERMS,
    TRAIN_STATES, UC_ACCEPTANCE,
)
from usecases import UC_EDITS

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W, "v": "urn:schemas-microsoft-com:vml"}


def q(name):
    return f"{{{W}}}{name}"


def text(node):
    return "".join(node.xpath(".//w:t/text()", namespaces=NS)).strip()


def child(parent, name, **attrs):
    node = E.SubElement(parent, q(name))
    for key, value in attrs.items():
        node.set(q(key), str(value))
    return node


def set_paragraph(p, value):
    if p.xpath(".//w:drawing|.//w:pict", namespaces=NS):
        raise ValueError("禁止改写包含图片的段落")
    first_run = p.find(q("r"))
    rpr = deepcopy(first_run.find(q("rPr"))) if first_run is not None and first_run.find(q("rPr")) is not None else None
    for node in list(p):
        if node.tag not in {q("pPr"), q("bookmarkStart"), q("bookmarkEnd")}:
            p.remove(node)
    r = E.Element(q("r"))
    if rpr is not None:
        r.append(rpr)
    t = child(r, "t")
    t.text = value
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    ends = p.findall(q("bookmarkEnd"))
    if ends:
        p.insert(list(p).index(ends[0]), r)
    else:
        p.append(r)


def paragraph(value, style=None, size=22, bold=False, center=False):
    p = E.Element(q("p"))
    pp = child(p, "pPr")
    if style:
        child(pp, "pStyle", val=style)
    child(pp, "spacing", before=80 if style else 0, after=80, line=276, lineRule="auto")
    if style:
        child(pp, "keepNext")
    if center:
        child(pp, "jc", val="center")
    r = child(p, "r")
    rp = child(r, "rPr")
    child(rp, "rFonts", ascii="Times New Roman", hAnsi="Times New Roman", eastAsia="宋体")
    if bold:
        child(rp, "b")
    child(rp, "color", val="000000")
    if not style:
        child(rp, "sz", val=size)
    child(r, "t").text = value
    return p


def set_cell(cell, values):
    if cell.xpath(".//w:drawing|.//w:pict", namespaces=NS):
        raise ValueError("禁止改写包含图片的单元格")
    old_p = cell.find(q("p"))
    template = deepcopy(old_p) if old_p is not None else paragraph("")
    for node in list(cell):
        if node.tag != q("tcPr"):
            cell.remove(node)
    for value in values if isinstance(values, list) else [values]:
        p = deepcopy(template)
        for key in list(p.attrib):
            p.attrib.pop(key)
        for node in p.xpath(".//w:bookmarkStart|.//w:bookmarkEnd", namespaces=NS):
            node.getparent().remove(node)
        set_paragraph(p, value)
        pp = p.find(q("pPr"))
        if pp is not None:
            for node in pp.findall(q("keepNext")) + pp.findall(q("pageBreakBefore")):
                pp.remove(node)
        cell.append(p)


def append_row(table, values):
    template = table.findall(q("tr"))[-1]
    row = deepcopy(template)
    for key in list(row.attrib):
        row.attrib.pop(key)
    for tag in ["tblHeader", "cantSplit", "trHeight"]:
        for node in row.xpath(f"./w:trPr/w:{tag}", namespaces=NS):
            node.getparent().remove(node)
    cells = row.findall(q("tc"))
    if len(cells) != len(values):
        raise ValueError(f"新行列数错误：{len(cells)} != {len(values)}")
    for c, value in zip(cells, values):
        set_cell(c, value)
    table.append(row)


def data_table(headers, rows, widths):
    table = E.Element(q("tbl"))
    prop = child(table, "tblPr")
    child(prop, "tblW", w=sum(widths), type="dxa")
    child(prop, "jc", val="center")
    child(prop, "tblLayout", type="fixed")
    borders = child(prop, "tblBorders")
    for edge in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        child(borders, edge, val="single", sz=4, color="D9D9D9")
    grid = child(table, "tblGrid")
    for width in widths:
        child(grid, "gridCol", w=width)
    for i, values in enumerate([headers] + list(rows)):
        row = child(table, "tr")
        if i == 0:
            child(child(row, "trPr"), "tblHeader")
        for j, (value, width) in enumerate(zip(values, widths)):
            cell = child(row, "tc")
            cp = child(cell, "tcPr")
            child(cp, "tcW", w=width, type="dxa")
            child(cp, "vAlign", val="center")
            margins = child(cp, "tcMar")
            for side, amount in [("top", 65), ("bottom", 65), ("left", 80), ("right", 80)]:
                child(margins, side, w=amount, type="dxa")
            if i == 0:
                child(cp, "shd", fill="EEEEEE", val="clear")
            p = paragraph(str(value), size=20, bold=i == 0, center=i == 0 or (j == 0 and width < 1500))
            if i > 0 and not (j == 0 and width < 1500):
                child(p.find(q("pPr")), "jc", val="left")
            spacing = p.find(q("pPr")).find(q("spacing"))
            spacing.set(q("line"), "258")
            spacing.set(q("after"), "20")
            cell.append(p)
    return table


def replace_table(table, headers, rows, widths):
    replacement = data_table(headers, rows, widths)
    table.getparent().replace(table, replacement)
    return replacement


def insert_before(anchor, nodes):
    for node in nodes:
        anchor.addprevious(node)


def heading(root, value):
    hits = [p for p in root.xpath("./w:body/w:p", namespaces=NS) if text(p) == value]
    if len(hits) != 1:
        raise ValueError(f"标题定位不唯一：{value} {len(hits)}")
    return hits[0]


def uc_tables(root):
    result = {}
    for table in root.xpath("./w:body/w:tbl", namespaces=NS):
        m = re.search(r"UC-[A-Z]+-\d{2}", text(table.findall(q("tr"))[0]))
        if m:
            result[m.group()] = table
    return result


def media_manifest(archive):
    return {n: hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist() if n.startswith("word/media/")}


def write_package(original, root, output):
    with ZipFile(output, "w") as target:
        for entry in original.infolist():
            value = E.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True) if entry.filename == "word/document.xml" else original.read(entry.filename)
            # 写入会改变 ZipInfo 的文件偏移，必须复制，避免破坏仍在读取的源目录。
            target.writestr(deepcopy(entry), value)


def revise(source, output, audit_path):
    if output.exists():
        raise ValueError(f"不覆盖现有输出：{output}")
    with ZipFile(source) as original:
        root = E.fromstring(original.read("word/document.xml"))
        tables = root.xpath("./w:body/w:tbl", namespaces=NS)
        cases = uc_tables(root)
        if len(cases) != 49:
            raise ValueError(f"原稿用例数不符：{len(cases)}")
        changed = []
        for uid, changes in UC_EDITS.items():
            rows = cases[uid].findall(q("tr"))
            fields = {text(row.findall(q("tc"))[0]).replace("\n", ""): row.findall(q("tc"))[-1] for row in rows[:6]}
            fields.update({"基本路径": rows[6].findall(q("tc"))[-1], "备选路径": rows[7].findall(q("tc"))[-1]})
            for label, value in changes.items():
                if label == "基本路径":
                    value = [f"{i}. {line}" for i, line in enumerate(value, 1)]
                set_cell(fields[label], value)
            changed.append(uid)

        replaced = []
        for prefix, replacement in PARAGRAPHS.items():
            hits = [p for p in root.xpath("./w:body/w:p", namespaces=NS) if text(p).startswith(prefix)]
            if len(hits) != 1:
                raise ValueError(f"正文定位不唯一：{prefix} {len(hits)}")
            set_paragraph(hits[0], replacement)
            replaced.append(prefix)

        replace_table(tables[2], ["术语", "说明"], TERMS, [1900, 6409])
        append_row(tables[3], ACTOR_ROW)
        # 使用原版本表空行，不编造编制人与审核结论。
        history = tables[1].findall(q("tr"))[3].findall(q("tc"))
        for c, value in zip(history, ["3", "20261020", "待填写", "待审核", "补充权限、状态、训练故障、智能辅助及需求验收规则；图片保留"]):
            set_cell(c, value)
        previous_note = tables[1].findall(q("tr"))[2].findall(q("tc"))[-1]
        set_cell(previous_note, "新增智能辅助用例包")

        for table in tables[57:]:
            for row in table.findall(q("tr"))[1:]:
                cells = row.findall(q("tc"))
                if text(cells[0]) in NFR_UPDATES:
                    set_cell(cells[1], NFR_UPDATES[text(cells[0])])
        nfr_tables = {"PERF": tables[57], "REL": tables[58], "SEC": tables[59], "USE": tables[60], "MNT": tables[61]}
        for uid, value in NFR_ADDITIONS.items():
            append_row(nfr_tables[uid.split("-")[1]], [uid, value])

        replace_table(tables[54], ["源对象", "关系", "目标对象"], RELATIONS, [2500, 1800, 4009])
        replace_table(tables[55], ["业务对象", "必要数据"], DATA_ITEMS, [2000, 6309])
        replace_table(tables[56], ["编号", "业务规则"], RULES, [1150, 7159])
        insert_before(heading(root, "用例规约"), [paragraph("本节规约描述成功路径及其备选处理。各用例的成功后置条件在对应流程完成后成立；被拒绝、取消或失败时，按备选路径保留实际结果、证据及必要的资源处理记录。图示用于展示相应业务主线，状态条件、权限及异常分支由规约和补充规则逐项说明。")])
        insert_before(heading(root, "核心实体及关系").getnext(), [paragraph("以下对象名称表达业务含义和引用关系，不规定数据库表或物理部署。训练项目组织任务，任务保存固定配置，执行记录追踪实际派发；各资产均保留空间、所有者和稳定标识。资源分配的所有者为一次执行或一个推理服务，二者恰选其一。")])

        sections = [
            paragraph("对象状态与转换规则", "5"),
            paragraph("训练业务状态统一如下。实际启动以执行组件确认事实为依据；节点健康、联系异常、准备和产物处理阶段分别保存。状态变化记录来源、时间、原因及执行标识，迟到事件须核对执行版本。"),
            data_table(["当前状态", "允许转入", "成立条件"], TRAIN_STATES, [1200, 2200, 4909]),
            paragraph("取消与派发竞争时先核查真实启动：未启动则撤销指令、结束准备并核对分配，已启动则进入停止流程。停止与正常完成竞争时保留先确认的合法结果和请求记录。心跳超时、停止超时或清理失败均不直接证明进程已结束。"),
            paragraph("成功和失败等业务结果与资源清理分别记录。取消后未确认释放的分配继续显示待释放；停止中须等待进程与清理确认。出现独立执行故障时可记录失败，相关占用继续核查。图3-5中的主要路径结合本表的条件执行。"),
            data_table(["对象", "状态", "约束"], OTHER_STATES, [1300, 3000, 4009]),
            paragraph("故障处理与恢复", "5"),
            paragraph("故障记录至少包含业务对象和执行标识、发生阶段、类别、源时间、原始错误、证据位置、当前业务结果、占用与清理状态、处理动作及实际结果。无法确认的原因标记待核查；诊断推测与原始事实分别保存。"),
            data_table(["编号及环节", "故障", "状态处理", "恢复与证据"], [(f"{a}\n{b}", c, d, e) for a, b, c, d, e in FAULTS], [1350, 1450, 2600, 2909]),
            paragraph("连接恢复和产物重传沿用原任务及执行标识，用户重跑另建任务。原执行结束未知时，先核查进程及有效隔离，确认不会重复运行后才能安排恢复。检查点续训仅对支持该能力的模板开放；权重、优化器、调度器、步数及随机状态等必需内容按模板清单校验。只有权重时明确允许的初始化方式，不能承诺完整续训。"),
            paragraph("心跳超时、停止超时、无进展阈值、重试次数、保留期限和辅助预算采用统一配置。配置应给出单位、作用范围和处置动作；缺少安全调用限制或真实数据授权的连接不启用真实业务外发，未配置无进展规则时只提示待核查。"),
            paragraph("功能范围与优先级", "5"),
            paragraph("P0为基础闭环和安全运行条件，P1为可独立关闭的增强能力。P1不可用时，基础训练、人工配置与标注路径仍可完成；已开放能力的权限、版本与错误规则同样必须满足。"),
            data_table(["范围", "用例编号省略UC前缀", "等级", "内容"], PRIORITIES, [1250, 2300, 650, 4109]),
            paragraph("数据增强、自动超参搜索、量化蒸馏、多机分布式训练和复杂流量治理保留为后续候选，纳入前分别确定用例、能力条件和验收。完整评估任务创建及高级比较另行规约；本版MDL-02覆盖既有报告的查看下载，并约束同条件比较。"),
        ]
        insert_before(heading(root, "非功能性需求"), sections)

        acceptance_heading = heading(root, "验收约束")
        sibling = acceptance_heading.getnext()
        while sibling is not None and sibling.tag != q("sectPr"):
            next_sibling = sibling.getnext()
            if sibling.xpath(".//w:drawing|.//w:pict", namespaces=NS):
                raise ValueError("验收段落中存在图片，停止替换")
            sibling.getparent().remove(sibling)
            sibling = next_sibling
        content = [
            paragraph("验收按明确场景同时检查页面反馈、服务端持久记录、实际执行及资源占用。P0用例全部覆盖，P1在能力开放后执行对应验收；以下内容为判定标准，不代表测试已经通过。"),
            data_table(["编号", "覆盖用例省略UC前缀", "规则", "通过条件"], ACCEPTANCE, [800, 1700, 1600, 4209]),
            paragraph("性能验收在记录明确的服务器配置、数据规模、并发数和采样窗口后进行。常用查询P95不超过2秒，任务提交在3秒内返回标识，采集成功的新日志和状态宜在5秒内到达页面；外部模型和训练耗时单独记录，不计作普通查询响应。至少覆盖24小时记录浏览及大文件传输的内存行为。"),
            paragraph("可靠性和安全验收覆盖控制面重启、重复提交/领取/事件、Worker失联、显存不足、损坏数据、存储拒写、停止超时、跨空间访问及凭据撤销。辅助能力另验证外发阻断、脱敏、预算耗尽、非法输出、过期和重复采纳；记录原始证据和结果，不预填准确率或恢复成功率。"),
            paragraph("用例与验收对应", "5"),
        ]
        trace_rows = []
        for uid, table in cases.items():
            name = text(table.findall(q("tr"))[0].findall(q("tc"))[-1]).split("：", 1)[-1]
            group = uid.split("-")[1]
            priority = "P1" if group == "AI" or uid == "UC-DAT-03" else "P0"
            trace_rows.append((uid, name, priority, UC_ACCEPTANCE[uid]))
        content.append(data_table(["用例", "名称", "等级", "验收"], trace_rows, [1650, 4000, 650, 2009]))
        content.extend([
            paragraph("待配置条件", "5"),
            paragraph("真实日志、配置和样本的外发范围及授权方式待确定，确认前保持关闭。连接、模态、预算、模板及恢复能力按有效配置启用。多用户组叠加、组共享总额及多资源池归属须先明确计算规则，同一设备不得重复分配。"),
        ])
        insert_before(root.find(q("body"))[-1], content)

        # 目录只列前三层，包含七个用例包及新增补充规约。
        for field in root.xpath("//w:instrText", namespaces=NS):
            if (field.text or "").strip().startswith("TOC "):
                field.text = 'TOC \\o "1-3" \\h \\z'
        # 正文表格可跨页，保留原图片的尺寸和节点，不调整图本身。
        for table in root.xpath("./w:body/w:tbl", namespaces=NS)[2:]:
            is_case = table in cases.values()
            for row in table.findall(q("tr")):
                for node in row.xpath("./w:trPr/w:cantSplit|./w:trPr/w:trHeight", namespaces=NS):
                    node.getparent().remove(node)
                # 短文字行保持完整，表格仍在行与行之间跨页；用例长行沿用可跨页规则。
                if not is_case:
                    rp = row.find(q("trPr"))
                    if rp is None:
                        rp = E.Element(q("trPr")); row.insert(0, rp)
                    child(rp, "cantSplit")
            first = table.findall(q("tr"))[0]
            rp = first.find(q("trPr"))
            if rp is None:
                rp = E.Element(q("trPr")); first.insert(0, rp)
            if rp.find(q("tblHeader")) is None:
                child(rp, "tblHeader")
            if not is_case:
                for p in first.xpath("./w:tc/w:p", namespaces=NS):
                    pp = p.find(q("pPr"))
                    if pp is None:
                        pp = E.Element(q("pPr")); p.insert(0, pp)
                    if pp.find(q("keepNext")) is None:
                        child(pp, "keepNext")

        output.parent.mkdir(parents=True, exist_ok=True)
        write_package(original, root, output)
        audit = {
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_images": media_manifest(original), "uc_count": len(cases),
            "changed_usecases": changed, "changed_body_paragraphs": replaced,
            "business_rules": len(RULES), "fault_scenarios": len(FAULTS),
            "acceptance_groups": len(ACCEPTANCE), "trace_rows": len(trace_rows),
        }
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    result = revise(args.source, args.output, args.audit)
    print(json.dumps({key: value for key, value in result.items() if key != "source_images"}, ensure_ascii=False))
