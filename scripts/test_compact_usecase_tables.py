"""验证分页问题与紧凑排版的最小修改边界。"""
import unittest
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from compact_usecase_tables import NS, compact_xml, tag, usecase_id
from test_activity_batch import find_state_figure


SOURCE = Path(__file__).resolve().parents[1] / 'docs/需求调研+需求分析/初步提交材料/系统需求规格说明书.docx'


class CompactTablesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ZipFile(SOURCE) as archive:
            cls.raw = archive.read('word/document.xml')
        cls.before = etree.fromstring(cls.raw)
        cls.changed, cls.report = compact_xml(cls.raw)
        cls.after = etree.fromstring(cls.changed)

    def test_reproduces_forced_page_breaks(self):
        cases = [t for t in self.before.findall('.//w:tbl', NS) if usecase_id(t)]
        breaks = [t.getprevious().find('w:pPr/w:pageBreakBefore', NS) for t in cases]
        self.assertEqual(len(breaks), 45)
        self.assertTrue(all(x is not None and x.get(tag('val')) not in ('0', 'false') for x in breaks))

    def test_preserves_all_text_and_image_relationships(self):
        for query in ('.//w:t/text()', './/a:blip/@r:embed'):
            namespaces = NS | {'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
            self.assertEqual(self.before.xpath(query, namespaces=namespaces), self.after.xpath(query, namespaces=namespaces))

    def test_text_rows_can_split_and_images_cannot(self):
        for table in self.after.findall('.//w:tbl', NS):
            for row in table.findall('w:tr', NS):
                has_image = row.find('.//w:drawing', NS) is not None or row.find('.//w:pict', NS) is not None
                header = row.find('w:trPr/w:tblHeader', NS) is not None
                self.assertEqual(row.find('w:trPr/w:cantSplit', NS).get(tag('val')), '1' if has_image or header else '0')

    def test_case_headings_flow_and_images_scale_proportionally(self):
        self.assertEqual(len(self.report['usecases']), 45)
        for case in self.report['usecases']:
            self.assertEqual(case['after_emu'], [round(value * .9) for value in case['before_emu']])
        for table in self.after.findall('.//w:tbl', NS):
            if usecase_id(table):
                self.assertEqual(table.getprevious().find('w:pPr/w:pageBreakBefore', NS).get(tag('val')), '0')

    def test_state_figure_validation_without_legacy_alt(self):
        namespaces = NS | {'v': 'urn:schemas-microsoft-com:vml',
                           'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
        with ZipFile(SOURCE) as archive:
            relationships = {r.get('Id'): r.get('Target') for r in etree.fromstring(archive.read('word/_rels/document.xml.rels'))}
            figures = self.before.findall('.//v:shape', namespaces)
            without_alt = etree.fromstring(etree.tostring(self.before)).findall('.//v:shape', namespaces)
            for figure in without_alt:
                figure.attrib.pop('alt', None)
            self.assertEqual(len(figures), 9)
            self.assertIsNotNone(find_state_figure(without_alt, namespaces, relationships, archive.read))


if __name__ == '__main__':
    unittest.main()
