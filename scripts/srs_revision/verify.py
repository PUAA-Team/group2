"""核对用例、图像原样保留和修订需求覆盖，不把内容检查当成版面验收。"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree as E

from build import NS, media_manifest, q, text, uc_tables
from requirements import ACCEPTANCE, FAULTS, PARAGRAPHS, RULES, UC_ACCEPTANCE
from usecases import UC_EDITS

NS.update({
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
})


def signatures(archive, root):
    rels = E.fromstring(archive.read("word/_rels/document.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels}
    result = []
    for node in root.xpath("//a:blip|//v:imagedata", namespaces=NS):
        rid = node.get(f"{{{NS['r']}}}embed") or node.get(f"{{{NS['r']}}}id")
        target = targets[rid]
        name = target.lstrip("/") if target.startswith("/") else "word/" + target
        image_hash = hashlib.sha256(archive.read(name)).hexdigest()
        parent = node
        while parent is not None and parent.tag not in {q("drawing"), q("pict")}:
            parent = parent.getparent()
        extent = [(n.get("cx"), n.get("cy")) for n in parent.xpath(".//wp:extent", namespaces=NS)]
        crop = [tuple(sorted(n.attrib.items())) for n in parent.xpath(".//a:srcRect", namespaces=NS)]
        shapes = parent.xpath(".//v:shape", namespaces=NS)
        vsize = []
        for shape in shapes:
            vsize.extend(re.findall(r"(?:^|;)(width|height):([^;]+)", shape.get("style", "")))
        result.append((image_hash, str(extent), str(crop), str(vsize)))
    return Counter(result)


def inspect(source, target=None):
    with ZipFile(source) as z:
        original = E.fromstring(z.read("word/document.xml"))
        original_cases = uc_tables(original)
        old_media = Counter(media_manifest(z).values())
        old_signatures = signatures(z, original)
    checks = [{"check": "源稿包含49个唯一用例", "passed": len(original_cases) == 49}]
    misses = {prefix: len([p for p in original.xpath("./w:body/w:p", namespaces=NS) if text(p).startswith(prefix)]) for prefix in PARAGRAPHS}
    checks.append({"check": "全部正文修订锚点唯一", "passed": all(n == 1 for n in misses.values()), "mismatches": {k: v for k, v in misses.items() if v != 1}})
    checks.append({"check": "用例修订目标均存在", "passed": set(UC_EDITS) <= original_cases.keys()})
    if target is None:
        checks.append({"check": "原稿可复现缺少故障及验收编号", "passed": "F-016" not in text(original) and "AC-14" not in text(original)})
        return checks
    with ZipFile(target) as z:
        doc = E.fromstring(z.read("word/document.xml"))
        cases = uc_tables(doc)
        full = text(doc)
        checks.extend([
            {"check": "49个用例编号和标题原样保留", "passed": cases.keys() == original_cases.keys() and all(text(t.findall(q("tr"))[0]) == text(original_cases[uid].findall(q("tr"))[0]) for uid, t in cases.items())},
            {"check": "全部图片资源的内容哈希及数量不变", "passed": Counter(media_manifest(z).values()) == old_media, "source_assets": sum(old_media.values()), "target_assets": len(media_manifest(z))},
            {"check": "全部图片引用、显示尺寸和裁切不变", "passed": signatures(z, doc) == old_signatures, "source_references": sum(old_signatures.values()), "target_references": sum(signatures(z, doc).values())},
            {"check": "32条业务规则完整", "passed": all(uid in full for uid, _ in RULES)},
            {"check": "16类异常和14组验收完整", "passed": all(row[0] in full for row in FAULTS + ACCEPTANCE)},
            {"check": "关键权限和辅助边界已写入", "passed": all(s in full for s in ["显式禁用", "较小值", "外发范围", "人工确认", "隔离待核查", "真实业务外发", "随机初始化"])},
            {"check": "同任务派发重试与新任务重跑分开", "passed": "从未启动且原尝试已清理" in full and "已经运行过的训练按BR-004另建任务恢复" in full},
            {"check": "清理原制作过程说明", "passed": all(s not in full for s in ["根据课程反馈", "本次不修改原有用例", "原有用例包、45 个用例"])},
        ])
        bad = []
        for uid, table in cases.items():
            rows = table.findall(q("tr"))
            main = rows[6].findall(q("tc"))[-1]
            alternative = rows[7].findall(q("tc"))[-1]
            steps = [int(m.group(1)) for p in main.findall(q("p")) if (m := re.match(r"^(\d+)\.", text(p)))]
            refs = [int(n) for n in re.findall(r"(?:^|/|\s)(\d+)[a-z][.．]", text(alternative))]
            if steps != list(range(1, len(steps) + 1)) or any(n > len(steps) for n in refs):
                bad.append(uid)
            if not table.xpath("./w:tr[1]/w:trPr/w:tblHeader", namespaces=NS):
                bad.append(uid + ":无重复表头")
        checks.append({"check": "用例步骤编号和跨页表头有效", "passed": not bad, "bad": bad})
        headers = [text(p) for p in doc.xpath("./w:body/w:p[w:pPr/w:pStyle/@w:val='5']", namespaces=NS)]
        checks.append({"check": "新增补充规约标题齐全", "passed": all(s in headers for s in ["用例包7 智能辅助", "对象状态与转换规则", "故障处理与恢复", "功能范围与优先级", "用例与验收对应", "待配置条件"])})
        trace_tables = [t for t in doc.xpath("./w:body/w:tbl", namespaces=NS) if text(t.findall(q("tr"))[0]) == "用例名称等级验收"]
        checks.append({"check": "逐项验收追踪包含49行", "passed": len(trace_tables) == 1 and len(trace_tables[0].findall(q("tr"))) == 50})
        trace = {text(cells[0]): text(cells[-1]) for row in trace_tables[0].findall(q("tr"))[1:] if (cells := row.findall(q("tc")))}
        checks.append({"check": "逐用例验收与验收表精确对应", "passed": trace == UC_ACCEPTANCE and len(trace) == 49})
        plain_tables = [t for t in doc.xpath("./w:body/w:tbl", namespaces=NS)[2:] if t not in cases.values()]
        checks.append({"check": "短文字表格行完整且表头随首行", "passed": all(t.xpath("./w:tr[1]/w:tc/w:p/w:pPr/w:keepNext", namespaces=NS) and all(row.xpath("./w:trPr/w:cantSplit", namespaces=NS) for row in t.findall(q("tr"))) for t in plain_tables)})
        anchors = set(doc.xpath("//w:hyperlink/@w:anchor", namespaces=NS))
        bookmarks = set(doc.xpath("//w:bookmarkStart/@w:name", namespaces=NS))
        checks.append({"check": "目录超链接目标均存在", "passed": anchors <= bookmarks})
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", nargs="?", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    checks = inspect(args.source, args.target)
    result = {"passed": all(c["passed"] for c in checks), "checks": checks}
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
