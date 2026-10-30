"""核对模型来源、关系端点、图中连线及生成源码一致性。"""
import json
import ast
from pathlib import Path
import re
import unittest
from zipfile import ZipFile
from docx import Document
from lxml import etree
from PIL import Image, ImageChops
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/"core_model.json").read_text(encoding="utf-8"))


class ModelTests(unittest.TestCase):
    def test_core_dictionary(self):
        shared=(ROOT.parent.parent/"业务模型与用例交互模型统一约定.md").read_text(encoding="utf-8")
        expected=set(re.findall(r"^\| O\d{2} \| [^|]*?([A-Za-z]+) \|",shared,re.M))
        self.assertEqual({c["key"] for c in DATA["classes"] if c["core"]},expected)
        self.assertEqual(len(expected),20)

    def test_support_dictionary(self):
        self.assertEqual(len(DATA["supplementary"]),19)
        self.assertEqual(len({x["key"] for x in DATA["supplementary"]}),19)

    def test_fields_and_behaviors(self):
        for c in DATA["classes"]:
            self.assertTrue(c["attributeNotes"] and c["operationNotes"])
            self.assertEqual(len(c["diagramAttributes"]),2)
            op=c["diagramOperation"].split("(")[0]
            self.assertIn(op,c["operations"])

    def test_relationships(self):
        keys={c["key"] for c in DATA["classes"]}
        self.assertEqual(len({r["id"] for r in DATA["relations"]}),27)
        for r in DATA["relations"]:
            self.assertIn(r["a"],keys); self.assertIn(r["b"],keys)
            self.assertTrue(r["constraint"])
            self.assertIn(r["kind"],{"association","composition","aggregation"})
            for m in (r["ma"],r["mb"]): self.assertRegex(m,r"^(0\.\.1|0\.\.\*|1\.\.\*|1)$")
        self.assertEqual({r["b"] for r in DATA["relations"] if r["kind"]=="composition"},{"ConfigSnapshot","ExecutionRecord"})
        self.assertEqual([r["a"] for r in DATA["relations"] if r["kind"]=="aggregation"],["ResourcePool"])

    def test_lines_avoid_unrelated_classes(self):
        for r in DATA["relations"]:
            for a,b in zip(r["points"],r["points"][1:]):
                self.assertTrue(abs(a[0]-b[0])<1e-7 or abs(a[1]-b[1])<1e-7,r["id"])
                for c in DATA["classes"]:
                    if c["key"] in (r["a"],r["b"]): continue
                    l,rr,lo,hi=c["x"]-2.8+.02,c["x"]+2.8-.02,c["y"]-1.4+.02,c["y"]+1.4-.02
                    crossed=(l<a[0]<rr and max(min(a[1],b[1]),lo)<min(max(a[1],b[1]),hi)) if abs(a[0]-b[0])<1e-7 else (lo<a[1]<hi and max(min(a[0],b[0]),l)<min(max(a[0],b[0]),rr))
                    self.assertFalse(crossed,(r["id"],c["key"],a,b))

    def test_generated_sources(self):
        for suffix in ("tex","puml"):
            text=(ROOT/("MB01_核心业务类图."+suffix)).read_text(encoding="utf-8")
            for c in DATA["classes"]: self.assertIn(c["key"],text)
            for r in DATA["relations"]: self.assertIn(r["id"],text)

    def test_relation_labels_above_crossing_lines(self):
        text=(ROOT/"MB01_核心业务类图.tex").read_text(encoding="utf-8")
        self.assertLess(text.rindex(r"\draw[line width=.55pt,preaction"),text.index("{R01 角色}"))

    def test_renderer_supplies_required_options(self):
        tree=ast.parse((ROOT/"render_report.py").read_text(encoding="utf-8"))
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="rasterize"]
        self.assertEqual(len(calls),1)
        self.assertTrue({"dpi","verbose","emit_pdf"}<={k.arg for k in calls[0].keywords})

    def test_word_contains_model_and_no_title_rule(self):
        path=ROOT.parent/"核心业务对象与类模型说明.docx"
        doc=Document(path)
        self.assertEqual(doc.paragraphs[0].style.name,"Title")
        text="\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        for c in DATA["classes"]:
            self.assertIn(c["key"],text)
            self.assertIn(c["operationNotes"],text)
            if c["core"]: self.assertIn(c["attributeNotes"],text)
        for r in DATA["relations"]: self.assertIn(r["constraint"],text)
        self.assertEqual(len(doc.inline_shapes),1)
        ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with ZipFile(path) as z:
            for name in ("word/styles.xml","word/document.xml"):
                self.assertEqual(etree.fromstring(z.read(name)).xpath(".//w:pBdr",namespaces=ns),[])

    def test_pdf_is_one_vector_page_with_all_classes(self):
        reader=PdfReader(ROOT.parent/"图片/MB01_核心业务类图.pdf")
        self.assertEqual(len(reader.pages),1)
        self.assertEqual(len(reader.pages[0].images),0)
        # PDF 字距调整可能被提取器解释为空格，不改变可见类名。
        text=re.sub(r"\s+","",reader.pages[0].extract_text())
        for c in DATA["classes"]:
            self.assertIn(c["key"],text)
            for value in c["diagramAttributes"]+[c["diagramOperation"]]:
                self.assertIn(re.sub(r"\s+","",value),text)
        for r in DATA["relations"]: self.assertIn(r["id"],text)

    def test_image_resolution_and_monochrome(self):
        with Image.open(ROOT.parent/"图片/MB01_核心业务类图.png") as im:
            self.assertGreaterEqual(max(im.size),3000)
            r,g,b=im.convert("RGB").split()
            self.assertIsNone(ImageChops.difference(r,g).getbbox())
            self.assertIsNone(ImageChops.difference(g,b).getbbox())


if __name__=="__main__": unittest.main()
