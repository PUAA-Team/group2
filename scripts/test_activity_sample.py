"""验证样图中的业务词组没有被自动拆行，关键分支与终态完整。"""
from pathlib import Path
import re
import sys
import unittest

import pdfplumber

PDF_PATH = Path(sys.argv.pop(1))


class ActivitySampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with pdfplumber.open(PDF_PATH) as pdf:
            cls.pages = len(pdf.pages)
            cls.width, cls.height = pdf.pages[0].width, pdf.pages[0].height
            cls.text = pdf.pages[0].extract_text(x_tolerance=1) or ''
            cls.colors = [item.get(key) for group in pdf.pages[0].objects.values()
                          for item in group for key in ('stroking_color', 'non_stroking_color')]

    def test_business_terms_are_not_split(self):
        for term in ['发起取消或停止', '发送停止请求', '终止训练进程', '释放占用资源', '进入异常处理']:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_guards_and_terminal_states_are_present(self):
        for term in ['[确认]', '[取消确认]', '[排队]', '[运行]', '[成功]', '[失败]', '标记已取消', '标记已停止']:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_single_page_size_is_suitable_for_word(self):
        self.assertEqual(self.pages, 1)
        self.assertLessEqual(self.width, 360)
        self.assertLessEqual(self.height, 520)

    def test_state_handling_belongs_to_system(self):
        source = PDF_PATH.with_suffix('.tex').read_text(encoding='utf-8')
        for name in ['keep', 'error']:
            with self.subTest(node=name):
                match = re.search(r'\(' + name + r'\) at \(([0-9.]+),', source)
                self.assertIsNotNone(match)
                self.assertGreater(float(match.group(1)), 2.7)

    def test_diagram_uses_only_black_and_white(self):
        for color in self.colors:
            if color is not None:
                components = color if isinstance(color, (tuple, list)) else (color,)
                self.assertTrue(all(value == components[0] for value in components))
                self.assertIn(components[0], (0, 1))

    def test_actual_node_clearance(self):
        log = PDF_PATH.with_suffix('.log').read_text(encoding='utf-8', errors='replace')
        positions = {name: float(y) for name, y in re.findall(
            r'UML-ANCHOR (\w+\.\w+)X=[^\n]+ Y=([-0-9.]+)pt', log)}
        for source, target in [('confirm.south', 'state.north'),
                               ('release.south', 'released.north'),
                               ('released.south', 'error.north')]:
            with self.subTest(edge=(source, target)):
                self.assertGreaterEqual(positions[source] - positions[target], 8.5)


if __name__ == '__main__':
    unittest.main()
