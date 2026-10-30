"""核对算力补充范围与原稿保留，不把接入方案写成实测成果。"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from docx import Document

spec = importlib.util.spec_from_file_location('compute_report', Path(__file__).with_name('update_research_compute_report.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = Path('D:/model-training-demo/research-compute-20261013/input/需求调研报告.docx')


class ComputeReportTests(unittest.TestCase):
    def test_resources_and_implementation_status(self):
        text = '\n'.join(str(value) for _, value in module.BLOCKS)
        for value in ['4张RTX 4060', '1张RTX 4070', 'CPU', '实验室GPU服务器', 'AutoDL', 'Lightning AI', '腾讯Cloud Studio', 'Modal']:
            self.assertIn(value, text)
        self.assertIn('统一接入仍需在后续实现中验证', text)
        self.assertNotIn('已完成统一接入', text)

    def test_complete_interface_and_security(self):
        text = '\n'.join(str(value) for _, value in module.BLOCKS)
        for value in ['能力查询', '状态查询', '产物清单', '一次性', '可撤销', 'HTTPS', '有效租约', '重复派发', '敏感数据', '审计记录', '预算']:
            self.assertIn(value, text)
        for value in ['gpt的设计.md', '课程要求', '用户的输入要求', '不是', '而是']:
            self.assertNotIn(value, text)

    def test_only_requested_section_changes(self):
        with tempfile.TemporaryDirectory(dir=SOURCE.parent.parent / 'temp') as directory:
            output = Path(directory) / 'report.docx'
            result = module.supplement(SOURCE, output)
            original, updated = Document(SOURCE), Document(output)
            old_texts = [p.text for p in original.paragraphs]
            new_texts = [p.text for p in updated.paragraphs]
            changed = {'5 模型、训练框架与数据源技术调研', old_texts[99], '5.6 技术调研结论'}
            for text in old_texts:
                if text not in changed:
                    self.assertIn(text, new_texts)
            self.assertEqual(len(updated.tables), len(original.tables) + 1)
            self.assertIn('5.6 算力资源可行性分析', new_texts)
            self.assertIn('5.7 技术调研结论', new_texts)
            self.assertGreater(result['preserved_media'], 0)
            headings = [p.text for p in updated.paragraphs if p.style.name == 'Heading 3']
            self.assertEqual(len([text for text in headings if text.startswith('5.6.')]), 6)

    def test_table_titles_stay_with_content(self):
        with tempfile.TemporaryDirectory(dir=SOURCE.parent.parent / 'temp') as directory:
            output = Path(directory) / 'report.docx'
            module.supplement(SOURCE, output)
            updated = Document(output)
            for p in updated.paragraphs:
                if p.style.name.startswith('Heading'):
                    self.assertTrue(p.paragraph_format.keep_with_next)
            for prefix in ['4.2 ', '第13题']:
                title = next(p for p in updated.paragraphs if p.text.startswith(prefix))
                self.assertTrue(title.paragraph_format.keep_with_next)
                element = title._p.getnext()
                while element.tag.endswith('}p'):
                    self.assertIsNotNone(element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}keepNext'))
                    element = element.getnext()
                self.assertTrue(element.tag.endswith('}tbl'))
                self.assertIsNotNone(element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}keepNext'))


if __name__ == '__main__':
    unittest.main()
