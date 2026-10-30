"""核对需求调研二次修订稿的顺序、语言、原生内容和模板文字框。"""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

_spec = importlib.util.spec_from_file_location("verify_defense_v2", Path(__file__).with_name("verify-defense-v2.py"))
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)
verify = _shared.verify

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}
LANGUAGE_BANNED = ["而是", "不是", "不能", "不要", "不等于", "截图来源", "原始像素",
                   "本页结论", "项目背景与调研方案", "原调研计划的周次安排"]


def check(target, manifest, project):
    # 复用公共包检查，避免两份验证器重复维护基础规则。
    verify(target, manifest)
    records = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(records) == 31
    assert [r["page"] for r in records if r["main"]] == [1, 4, 9, 10, 25, 28, 29, 30]
    assert records[23]["title"] == "问卷样本与调查范围"
    assert records[28]["title"] == "团队分工与两组研究路线"
    assert records[29]["title"] == "调研时间规划"
    with ZipFile(target) as package:
        for record in records:
            tree = ET.fromstring(package.read(f"ppt/slides/slide{record['page']}.xml"))
            copy = "".join(node.text or "" for node in tree.findall(".//a:t", NS))
            # 封面沿用正式队名，其中的字词不属于正文反驳表达。
            if record["page"] != 1:
                for term in LANGUAGE_BANNED:
                    assert term not in copy, f"第{record['page']}页残留：{term}"
            for color in tree.findall(".//a:rPr/a:solidFill/a:srgbClr", NS):
                assert color.get("val", "").upper() not in {"536777", "65758A", "64748B"}, f"第{record['page']}页仍有灰色辅助文字"
            if record["kind"].startswith("survey"):
                assert tree.find(".//c:chart", NS) is not None, f"第{record['page']}页缺少原生图表"
        def method_copy(tree):
            return {shape.find("p:nvSpPr/p:cNvPr", NS).get("name", "").replace(" ", ""):
                    re.sub(r"\s", "", "".join(n.text or "" for n in shape.findall(".//a:t", NS)))
                    for shape in tree.findall(".//p:sp", NS)}

        with ZipFile(project / "docs/需求调研+需求分析/大模型集成训练平台需求调研汇报.pptx") as source:
            original = ET.fromstring(source.read("ppt/slides/slide3.xml"))
            assert method_copy(ET.fromstring(package.read("ppt/slides/slide4.xml"))) == method_copy(original), "原调研方法页发生改写"
        charts = [n for n in package.namelist() if re.fullmatch(r"ppt/(?:slides/)?charts/chart\d+\.xml", n)]
        workbooks = [n for n in package.namelist() if n.startswith("ppt/embeddings/") and n.endswith(".xlsx")]
        assert len(charts) == len(workbooks) == 4, "原生图表或数据工作簿数量错误"
        actual = []
        for name in charts:
            tree = ET.fromstring(package.read(name))
            values = [float(n.text) for n in tree.findall(".//c:ser/c:val/c:numRef/c:numCache/c:pt/c:v", NS)]
            assert values and all(0 <= value <= 1 for value in values), "百分比数据越界或缓存缺失"
            actual.append(tuple(sorted(values)))
        expected = [tuple(sorted(round(n / 67, 6) for n in counts)) for counts in
                    ([22, 19, 15, 11], [45, 45, 44, 44], [16, 19, 24, 8], [52, 50, 46])]
        assert sorted(actual) == sorted(expected), "图表人数与问卷原始计数不符"
    preserved = {
        "大模型集成训练平台需求调研汇报.pptx": "de32ca6870a4cefceded31b9f1dbe71509201f47e2d48bf4e25c20fb39d7117f",
        "大模型集成训练平台_需求调研答辩_修订版.pptx": "24b6905e97ed97804449db4a0653e7bb30adfb120055d0c6ba77bcd30b40148e",
        "大模型集成训练平台_需求分析答辩_修订版.pptx": "d3925ae07c6325d1203fb10a5e2735452452c0e5dff1d2e32ee0ad53217905da",
    }
    for filename, expected_hash in preserved.items():
        source = project / "docs/需求调研+需求分析" / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_hash, f"保留文件发生变化：{filename}"
    print(json.dumps({"native_tables": 8, "native_charts": 4, "editable_workbooks": 4,
                      "original_methods_copy": "passed", "source_files_preserved": True}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("revision")
    args = parser.parse_args()
    check(args.workspace / f"output-{args.revision}" / "大模型集成训练平台_需求调研答辩_二次修订版.pptx",
          args.workspace / f"private-{args.revision}" / "manifest.json", Path(__file__).resolve().parents[2])
