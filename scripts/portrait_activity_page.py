"""将端到端活动图的横向节改为竖向，仅调整页面和图片显示尺寸。"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'v': 'urn:schemas-microsoft-com:vml'}
W = '{' + NS['w'] + '}'


def portrait_xml(data):
    document = etree.fromstring(data)
    body = document.find('w:body', NS)
    blocks = list(body)
    sections = document.findall('.//w:sectPr', NS)
    targets = [s for s in sections if s.find('w:pgSz', NS).get(W + 'orient') == 'landscape']
    if len(targets) != 1:
        raise ValueError('应恰有一个横向节，停止以免修改错误页面。')
    target = targets[0]
    previous = sections[sections.index(target) - 1]
    start = blocks.index(previous.getparent().getparent()) + 1
    end = blocks.index(target.getparent().getparent())
    section_blocks = blocks[start:end + 1]
    title = ''.join(t for p in section_blocks for t in p.xpath('.//w:t/text()', namespaces=NS))
    if '训练任务端到端活动图' not in title:
        raise ValueError('横向节不是端到端活动图，停止修改。')
    pictures = [shape for p in section_blocks for shape in p.findall('.//v:shape', NS)]
    if len(pictures) != 1:
        raise ValueError('目标节应只包含一张活动图。')
    # 沿用相邻竖向节的纸张与页眉页脚，保留原图页边距以充分利用图宽。
    for name in ('pgSz', 'headerReference', 'footerReference'):
        old_nodes = target.findall('w:' + name, NS)
        index = list(target).index(old_nodes[0]) if old_nodes else 0
        for old in old_nodes:
            target.remove(old)
        for offset, original in enumerate(previous.findall('w:' + name, NS)):
            target.insert(index + offset, deepcopy(original))
    size = target.find('w:pgSz', NS)
    margins = target.find('w:pgMar', NS)
    if int(size.get(W + 'w')) >= int(size.get(W + 'h')):
        raise ValueError('相邻节的纸张不是竖向。')
    available = (int(size.get(W + 'w')) - int(margins.get(W + 'left')) - int(margins.get(W + 'right'))) / 20
    shape = pictures[0]
    style = shape.get('style')
    dimensions = {}
    for key in ('width', 'height'):
        match = re.search(rf'(?:^|;){key}:([0-9.]+)pt', style)
        if match is None:
            raise ValueError('活动图尺寸单位不符合预期。')
        dimensions[key] = float(match.group(1))
    ratio = min(1, (available - 4) / dimensions['width'])
    for key, value in dimensions.items():
        style = re.sub(rf'(?<=;){key}:[0-9.]+pt|^{key}:[0-9.]+pt',
                       f'{key}:{value * ratio:.4f}pt', style)
    shape.set('style', style)
    result = etree.tostring(document, xml_declaration=True, encoding='UTF-8', standalone=True)
    if document.xpath('.//w:t/text()', namespaces=NS) != etree.fromstring(data).xpath('.//w:t/text()', namespaces=NS):
        raise AssertionError('文字改变，停止保存。')
    return result, {'portrait_sections': len(sections), 'changed_sections': 1,
                    'picture_scale': round(ratio, 6), 'picture_width_pt': round(dimensions['width'] * ratio, 4)}


def build(source, output):
    if output.exists():
        raise FileExistsError('输出已存在，请换新路径。')
    with ZipFile(source) as original:
        data, report = portrait_xml(original.read('word/document.xml'))
        with ZipFile(output, 'w') as result:
            for part in original.infolist():
                result.writestr(part, data if part.filename == 'word/document.xml' else original.read(part))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.source, arguments.output), ensure_ascii=False))
