"""局部调整规格书分页与活动图显示尺寸，保留正文和所有原始包部件。"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
}


def tag(name):
    return '{' + NS['w'] + '}' + name


def properties(element, name):
    child = element.find('w:' + name, NS)
    if child is None:
        child = etree.Element(tag(name))
        element.insert(0, child)
    return child


def flag(parent, name, enabled):
    child = parent.find('w:' + name, NS)
    if child is None:
        child = etree.SubElement(parent, tag(name))
    child.set(tag('val'), '1' if enabled else '0')


def usecase_id(table):
    value = ''.join(table.xpath('./w:tr[1]//w:t/text()', namespaces=NS))
    match = re.search(r'UC-[A-Z]+-\d{2}', value)
    return match.group(0) if match else None


def compact_xml(data, scale=0.9):
    if not 0.85 <= scale <= 1:
        raise ValueError('缩放比例须在 0.85 到 1 之间，避免图片过小。')
    document = etree.fromstring(data)
    report = {'tables': 0, 'text_rows': 0, 'usecases': [], 'scale': scale}
    for table in document.findall('.//w:tbl', NS):
        report['tables'] += 1
        identifier = usecase_id(table)
        for row in table.findall('w:tr', NS):
            row_properties = properties(row, 'trPr')
            picture = row.find('.//w:drawing', NS) is not None or row.find('.//w:pict', NS) is not None
            header = row_properties.find('w:tblHeader', NS) is not None
            # 文字行可分页，标题行和图片行保持完整。
            flag(row_properties, 'cantSplit', picture or header)
            for height in row_properties.findall('w:trHeight', NS):
                if height.get(tag('hRule')) == 'exact':
                    height.set(tag('hRule'), 'atLeast')
            for paragraph in row.findall('.//w:p', NS):
                p_properties = properties(paragraph, 'pPr')
                has_picture = paragraph.find('.//w:drawing', NS) is not None or paragraph.find('.//w:pict', NS) is not None
                flag(p_properties, 'keepLines', has_picture or header)
                flag(p_properties, 'keepNext', header)
                flag(p_properties, 'pageBreakBefore', False)
            if not picture and not header:
                report['text_rows'] += 1
        if identifier is None:
            continue
        heading = table.getprevious()
        if heading is None or identifier not in ''.join(heading.xpath('.//w:t/text()', namespaces=NS)):
            raise ValueError(f'{identifier} 缺少相邻用例标题，停止修改。')
        heading_properties = properties(heading, 'pPr')
        flag(heading_properties, 'pageBreakBefore', False)
        flag(heading_properties, 'keepNext', True)
        flag(heading_properties, 'keepLines', True)
        drawings = table.findall('.//w:drawing', NS)
        if len(drawings) != 1:
            raise ValueError(f'{identifier} 活动图数量不为 1。')
        extent = drawings[0].find('.//wp:extent', NS)
        transform = drawings[0].find('.//a:xfrm/a:ext', NS)
        if extent is None or transform is None:
            raise ValueError(f'{identifier} 缺少内嵌图片尺寸。')
        before = [int(extent.get(k)) for k in ('cx', 'cy')]
        after = [round(value * scale) for value in before]
        for element in (extent, transform):
            for key, value in zip(('cx', 'cy'), after):
                element.set(key, str(value))
        report['usecases'].append({'id': identifier, 'before_emu': before, 'after_emu': after})
    if len(report['usecases']) != 45:
        raise ValueError('应有 45 张用例活动图，停止修改。')
    return etree.tostring(document, xml_declaration=True, encoding='UTF-8', standalone=True), report


def compact(source, output, report_path, scale=0.9):
    if output.exists() or report_path.exists():
        raise FileExistsError('输出或报告已存在，请使用新的路径。')
    with ZipFile(source) as original:
        before = original.read('word/document.xml')
        after, report = compact_xml(before, scale)
        # 正文、绘图关系和媒体字节必须完全保留，仅修改布局属性。
        old_text = etree.fromstring(before).xpath('.//w:t/text()', namespaces=NS)
        new_text = etree.fromstring(after).xpath('.//w:t/text()', namespaces=NS)
        if old_text != new_text:
            raise AssertionError('布局修改改变了正文，停止保存。')
        with ZipFile(output, 'w') as result:
            for member in original.infolist():
                result.writestr(member, after if member.filename == 'word/document.xml' else original.read(member))
    report['source'] = str(source.resolve())
    report['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    report['output_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {key: value for key, value in report.items() if key != 'usecases'} | {'usecase_count': len(report['usecases'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--scale', type=float, default=0.9)
    arguments = parser.parse_args()
    print(json.dumps(compact(arguments.source, arguments.output, arguments.report, arguments.scale), ensure_ascii=False))
