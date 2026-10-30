"""核对活动图控制流、规约覆盖、黑白输出和插图完整性。"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from docx import Document
from lxml import etree
import pdfplumber

from build_activity_diagrams import ASSETS, load_flows, validate, crosses_box


def find_state_figure(figures, namespaces, relationships, read_part):
    expected = hashlib.sha256((ASSETS/'图片/训练任务状态图.png').read_bytes()).digest()
    matches = []
    for figure in figures:
        data = figure.find('v:imagedata', namespaces)
        if data is None:
            continue
        rid = data.get('{'+namespaces['r']+'}id')
        actual = read_part('word/'+relationships[rid])
        if hashlib.sha256(actual).digest() == expected:
            matches.append(figure)
    assert len(matches) == 1, ('状态图内容匹配数量', len(matches))
    return matches[0]


def check(source,build,docx=None):
    flows=load_flows();by_id={g['id']:g for g in flows};errors=[]
    # 配置校验采用互斥的通过/未通过分支，避免多个错误同时满足且标签重叠。
    training=by_id['UC-TRN-01']
    assert {e.get('guard') for e in training['edges'] if e['from']=='result'}=={'通过','未通过'}
    specs={}
    for table in Document(source).tables:
        title=table.rows[0].cells[-1].text
        match=re.search(r'UC-[A-Z]+-\d{2}',title)
        if match:
            sections={}
            for row in table.rows:
                values=[c.text for c in row.cells]
                if any('基本' in v for v in values[:-1]):sections['basic']=values[-1]
                if any('备选' in v for v in values[:-1]):sections['alternatives']=values[-1]
            specs[match.group()]=sections
    assert set(by_id)|{'UC-TRN-06'}==set(specs)
    for identifier,graph in by_id.items():
        validate(graph)
        basic=set(re.findall(r'(?m)^([0-9]+)\.',specs[identifier]['basic']))
        alt=set(re.findall(r'\b([0-9]+[a-z])',specs[identifier]['alternatives']))
        coverage_alt=set(re.findall(r'[0-9]+[a-z]',','.join(graph['coverage']['alternatives'])))
        assert basic==set(graph['coverage']['basic']),(identifier,'基本步骤',basic)
        assert alt==coverage_alt,(identifier,'备选路径',alt,coverage_alt)
        outgoing=defaultdict(list)
        for edge in graph['edges']:outgoing[edge['from']].append(edge['to'])
        start=[n['key'] for n in graph['nodes'] if n['kind']=='initial'][0]
        reached=set();queue=[start]
        while queue:
            key=queue.pop()
            if key not in reached:reached.add(key);queue.extend(outgoing[key])
        assert reached=={n['key'] for n in graph['nodes']},(identifier,'不可达节点')
    for path in sorted(build.glob('UC-*.pdf')):
        with pdfplumber.open(path) as pdf:
            assert len(pdf.pages)==1,path.name
            page=pdf.pages[0]
            assert path.stem in (page.extract_text() or ''),path.name
            for items in page.objects.values():
                for item in items:
                    for kind in ['stroking_color','non_stroking_color']:
                        color=item.get(kind)
                        if color is None:continue
                        components=color if isinstance(color,(tuple,list)) else [color]
                        assert all(c==components[0] for c in components) and components[0] in [0,1],path.name
    validation=json.loads((build/'validation.json').read_text(encoding='utf-8'))
    for item in validation:
        for route in item['routes']:
            source_key,target=route['edge']['from'],route['edge']['to']
            for a,b in zip(route['points'],route['points'][1:]):
                for key,box in item['boxes'].items():
                    if key not in [source_key,target]:
                        assert not crosses_box(a,b,box),(item['id'],'连线穿框',key)
    if docx:
        with ZipFile(docx) as package:
            root=etree.fromstring(package.read('word/document.xml'))
            ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
                'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
                'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
                'v':'urn:schemas-microsoft-com:vml'}
            relationships={r.get('Id'):r.get('Target') for r in etree.fromstring(package.read('word/_rels/document.xml.rels'))}
            count=len(root.findall('.//w:drawing',ns))
            assert count==45,count
            for table in root.findall('w:body/w:tbl',ns):
                match=re.search(r'UC-[A-Z]+-\d{2}',''.join(table.findall('w:tr',ns)[0].xpath('.//w:t/text()',namespaces=ns)))
                if match:
                    assert len(table.findall('.//w:drawing',ns))==1
                    rid=table.find('.//a:blip',ns).get('{'+ns['r']+'}embed')
                    embedded=package.read('word/'+relationships[rid])
                    assert hashlib.sha256(embedded).digest()==hashlib.sha256((build/(match.group()+'.png')).read_bytes()).digest(),match.group()
            original_figures=root.findall('.//v:shape',ns)
            assert len(original_figures)==9,len(original_figures)
            # Word 另存可能清除旧 VML 标签，改按图片关系与内容唯一匹配。
            find_state_figure(original_figures, ns, relationships, package.read)
    return dict(usecases=len(specs),generated=len(list(build.glob('UC-*.pdf'))),control_flow='passed',
                source_coverage='passed',black_white='passed',edge_clearance='passed',word=bool(docx))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path);parser.add_argument('--build',required=True,type=Path)
    parser.add_argument('--docx',type=Path)
    args=parser.parse_args();print(json.dumps(check(args.source,args.build,args.docx),ensure_ascii=False))
