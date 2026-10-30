"""复现 Artifact Tool 绝对关系路径与原稿相对路径的兼容问题。"""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location('merge_modeling', Path(__file__).with_name('merge-modeling-deck.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_fixture(path):
    """两份模板各自合法，但母版编号相同，复现合并时的冲突。"""
    parts = {
        'ppt/presentation.xml': f'<p:presentation xmlns:p="{module.P}" xmlns:r="{module.R}"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="master"/></p:sldMasterIdLst><p:notesMasterIdLst><p:notesMasterId r:id="notes"/></p:notesMasterIdLst><p:sldIdLst><p:sldId id="256" r:id="slide"/></p:sldIdLst></p:presentation>',
        'ppt/_rels/presentation.xml.rels': f'<Relationships xmlns="{module.REL}"><Relationship Id="master" Target="slideMasters/slideMaster1.xml" Type="{module.R}/slideMaster"/><Relationship Id="notes" Target="notesMasters/notesMaster1.xml" Type="{module.R}/notesMaster"/><Relationship Id="slide" Target="slides/slide1.xml" Type="{module.R}/slide"/></Relationships>',
        'ppt/slideMasters/slideMaster1.xml': f'<p:sldMaster xmlns:p="{module.P}" xmlns:r="{module.R}"><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="layout"/></p:sldLayoutIdLst></p:sldMaster>',
        'ppt/slideMasters/_rels/slideMaster1.xml.rels': f'<Relationships xmlns="{module.REL}"><Relationship Id="layout" Target="../slideLayouts/slideLayout1.xml" Type="{module.R}/slideLayout"/></Relationships>',
        'ppt/slideLayouts/slideLayout1.xml': f'<p:sldLayout xmlns:p="{module.P}"/>',
        'ppt/notesMasters/notesMaster1.xml': f'<p:notesMaster xmlns:p="{module.P}"/>',
        'ppt/notesSlides/notesSlide1.xml': f'<p:notes xmlns:p="{module.P}"/>',
        'ppt/notesSlides/_rels/notesSlide1.xml.rels': f'<Relationships xmlns="{module.REL}"><Relationship Id="master" Target="../notesMasters/notesMaster1.xml" Type="{module.R}/notesMaster"/><Relationship Id="slide" Target="../slides/slide1.xml" Type="{module.R}/slide"/></Relationships>',
        'ppt/slides/slide1.xml': f'<p:sld xmlns:p="{module.P}"/>',
        'ppt/slides/_rels/slide1.xml.rels': f'<Relationships xmlns="{module.REL}"><Relationship Id="notes" Target="../notesSlides/notesSlide1.xml" Type="{module.R}/notesSlide"/></Relationships>',
        '[Content_Types].xml': f'<Types xmlns="{module.CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' + ''.join(f'<Override PartName="/{name}" ContentType="application/xml"/>' for name in ['ppt/presentation.xml', 'ppt/slideMasters/slideMaster1.xml', 'ppt/slideLayouts/slideLayout1.xml', 'ppt/notesMasters/notesMaster1.xml', 'ppt/notesSlides/notesSlide1.xml', 'ppt/slides/slide1.xml']) + '</Types>',
    }
    with ZipFile(path, 'x') as package:
        for name, data in parts.items():
            package.writestr(name, data)


class RelationshipPathTests(unittest.TestCase):
    def test_absolute_and_relative_slides(self):
        for target in ['/ppt/slides/slide1.xml', 'slides/slide1.xml']:
            parts = {
                'ppt/presentation.xml': f'<p:presentation xmlns:p="{module.P}" xmlns:r="{module.R}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>'.encode(),
                'ppt/_rels/presentation.xml.rels': f'<Relationships xmlns="{module.REL}"><Relationship Id="rId1" Target="{target}" Type="{module.R}/slide"/></Relationships>'.encode(),
            }
            self.assertEqual(module.ordered_slides(parts)[0][1], 'ppt/slides/slide1.xml')

    def test_default_content_type_namespace(self):
        root = module.xml(f'<Types xmlns="{module.CT}"><Default Extension="png" ContentType="image/png"/></Types>')
        result = module.serialize_content_types(root)
        self.assertIn(b'<Types xmlns=', result)
        self.assertIn(b'<Default ', result)
        self.assertNotIn(b':Types', result)

    def test_standard_slide_parts_for_native_chart_validation(self):
        names = ['ppt/slides/slide1.xml', 'ppt/slides/_rels/slide1.xml.rels', 'ppt/fonts/font.dat', 'ppt/theme/theme1.xml']
        mapping = module.map_parts(names, [(None, 'ppt/slides/slide1.xml')], 29)
        self.assertEqual(mapping['ppt/slides/slide1.xml'], 'ppt/slides/slide30.xml')
        self.assertEqual(mapping['ppt/slides/_rels/slide1.xml.rels'], 'ppt/slides/_rels/slide30.xml.rels')
        self.assertNotIn('ppt/fonts/font.dat', mapping)

    def test_only_normalize_roundtrip_numeric_precision(self):
        data = b'<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:numCache><c:pt idx="0"><c:v>0.16417899999999999</c:v></c:pt></c:numCache></c:chart>'
        result = module.normalize_roundtrip_cache(data, ['0.164179'])
        self.assertEqual(result, data.replace(b'0.16417899999999999', b'0.164179'))
        with self.assertRaises(ValueError):
            module.normalize_roundtrip_cache(data, ['0.5'])


class NativeMasterCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix='ppt-merge-regression-')
        self.addCleanup(self.directory.cleanup)
        folder = Path(self.directory.name)
        source, model, output = [folder / f'{name}.pptx' for name in ['source', 'model', 'output']]
        write_fixture(source)
        write_fixture(model)
        module.merge(source, model, output, keep=1)
        with ZipFile(output) as package:
            self.parts = {name: package.read(name) for name in package.namelist()}

    def test_one_notes_master_and_shared_notes_relationship(self):
        root = module.xml(self.parts['ppt/presentation.xml'])
        self.assertEqual(len(root.find(f'{{{module.P}}}notesMasterIdLst')), 1)
        imported = module.xml(self.parts['ppt/modeling/ppt/notesSlides/_rels/notesSlide1.xml.rels'])
        target = next(r.get('Target') for r in imported if r.get('Type').endswith('/notesMaster'))
        self.assertEqual(module.resolve_target('ppt/modeling/ppt/notesSlides', target), 'ppt/notesMasters/notesMaster1.xml')
        self.assertNotIn('ppt/modeling/ppt/notesMasters/notesMaster1.xml', self.parts)
        types = module.xml(self.parts['[Content_Types].xml'])
        overrides = [el.get('PartName') for el in types if el.tag == f'{{{module.CT}}}Override']
        self.assertEqual(len(overrides), len(set(overrides)))

    def test_layout_ids_unique_across_masters(self):
        ids = []
        for name, data in self.parts.items():
            if name.endswith('.xml') and '/slideMasters/' in name:
                ids.extend(node.get('id') for node in module.xml(data).findall(f'.//{{{module.P}}}sldLayoutId'))
        self.assertEqual(len(ids), len(set(ids)), '导入的版式编号与原稿冲突')
        self.assertTrue(all(2147483648 <= int(value) <= 4294967295 for value in ids))


if __name__ == '__main__':
    unittest.main()
