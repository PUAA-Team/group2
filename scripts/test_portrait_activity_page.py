"""横向活动图页转竖向的局部回归检查。"""
from pathlib import Path
import unittest
from zipfile import ZipFile

from lxml import etree

from portrait_activity_page import NS, W, portrait_xml

SOURCE = Path('D:/model-training-demo/srs-uml-20261013/portrait-20261013/source-current.docx')


class PortraitPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ZipFile(SOURCE) as package:
            cls.raw = package.read('word/document.xml')
        cls.original = etree.fromstring(cls.raw)
        cls.after, cls.report = portrait_xml(cls.raw)
        cls.result = etree.fromstring(cls.after)

    def test_preserves_body_and_45_usecase_diagrams(self):
        self.assertEqual(self.original.xpath('.//w:t/text()', namespaces=NS), self.result.xpath('.//w:t/text()', namespaces=NS))
        self.assertEqual(len(self.result.findall('.//w:drawing', NS)), 45)

    def test_all_sections_are_portrait(self):
        for size in self.result.findall('.//w:sectPr/w:pgSz', NS):
            self.assertLess(int(size.get(W + 'w')), int(size.get(W + 'h')))

    def test_page_settings_keep_schema_order(self):
        for section in self.result.findall('.//w:sectPr', NS):
            keys = [etree.QName(child).localname for child in section]
            self.assertLess(keys.index('pgSz'), keys.index('pgMar'))
            self.assertLess(keys.index('pgMar'), keys.index('cols'))
            self.assertLess(keys.index('pgMar'), keys.index('docGrid'))


if __name__ == '__main__':
    unittest.main()
