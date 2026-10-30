"""复现 ZipInfo 复用影响源包读取的问题，并保护图片与源目录。"""

from io import BytesIO
import unittest
from zipfile import ZipFile

from lxml import etree as E

from build import data_table, media_manifest, q, text, write_package
from requirements import UC_ACCEPTANCE


class PackageRegression(unittest.TestCase):
    def source(self):
        value = BytesIO()
        with ZipFile(value, "w") as z:
            z.writestr("word/document.xml", b"<original/>")
            z.writestr("word/media/image.png", b"unchanged-picture")
        value.seek(0)
        return value

    def test_old_reuse_reproduces_invalid_source_offset(self):
        with ZipFile(self.source()) as original:
            with ZipFile(BytesIO(), "w") as target:
                for entry in original.infolist():
                    data = original.read(entry.filename)
                    if entry.filename == "word/document.xml":
                        data += b"extra bytes changing later offsets"
                    target.writestr(entry, data)
            from zipfile import BadZipFile
            with self.assertRaises(BadZipFile):
                media_manifest(original)

    def test_source_directory_stays_readable_after_longer_xml(self):
        with ZipFile(self.source()) as original:
            offsets = [n.header_offset for n in original.infolist()]
            before = media_manifest(original)
            target = BytesIO()
            write_package(original, E.fromstring(b"<changed>much longer document content</changed>"), target)
            self.assertEqual(offsets, [n.header_offset for n in original.infolist()])
            self.assertEqual(before, media_manifest(original))
            target.seek(0)
            with ZipFile(target) as result:
                self.assertEqual(before, media_manifest(result))


class TraceRegression(unittest.TestCase):
    def test_exact_cross_package_acceptance(self):
        self.assertEqual(49, len(UC_ACCEPTANCE))
        expected = {
            "UC-BM-03": "AC-02", "UC-TRN-01": "AC-03",
            "UC-TRN-05": "AC-05、AC-09", "UC-TRN-08": "AC-07",
            "UC-ADM-04": "AC-06、AC-12", "UC-AI-04": "AC-14",
        }
        for uid, aid in expected.items():
            with self.subTest(usecase=uid):
                self.assertEqual(aid, UC_ACCEPTANCE[uid])

    def test_table_content_stays_in_independent_rows(self):
        table = data_table(["编号", "规则"], [("BR-001", "规则一"), ("BR-002", "规则二")], [1000, 7000])
        self.assertEqual(["编号规则", "BR-001规则一", "BR-002规则二"], [text(row) for row in table.findall(q("tr"))])


if __name__ == "__main__":
    unittest.main()
