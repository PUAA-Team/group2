"""合并 Artifact Tool 新建模章节；保留原稿前部幻灯片与共享资源原字节。"""
import argparse
import copy
from decimal import Decimal
import io
import json
import posixpath
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZipFile, ZIP_DEFLATED

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
C = 'http://schemas.openxmlformats.org/drawingml/2006/chart'
E.register_namespace('p', P)
E.register_namespace('r', R)


def xml(data):
    return E.fromstring(data)


def serialize(root):
    return E.tostring(root, encoding='utf-8', xml_declaration=True)


def serialize_content_types(root):
    E.register_namespace('', CT)
    return serialize(root)


def resolve_target(owner_dir, target):
    return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(owner_dir, target))


def ordered_slides(parts):
    root = xml(parts['ppt/presentation.xml'])
    rels = {r.get('Id'): r for r in xml(parts['ppt/_rels/presentation.xml.rels'])}
    ids = list(root.find(f'{{{P}}}sldIdLst'))
    return [(s, resolve_target('ppt', rels[s.get(f'{{{R}}}id')].get('Target'))) for s in ids]


def map_parts(names, model_order, keep):
    excluded = {'[Content_Types].xml', '_rels/.rels', 'ppt/presentation.xml', 'ppt/_rels/presentation.xml.rels'}
    mapping = {name: f'ppt/modeling/{name}' for name in names if name not in excluded
               and not name.startswith(('docProps/', 'ppt/fonts/'))}
    for i, (_, part) in enumerate(model_order, 1):
        mapping[part] = f'ppt/slides/slide{keep + i}.xml'
        old_rel = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
        if old_rel in mapping:
            mapping[old_rel] = f'ppt/slides/_rels/slide{keep + i}.xml.rels'
    return mapping


def reuse_notes_master(root, rels, incoming, mapping):
    """整个演示文稿只保留一个备注母版，新备注页复用原稿母版。"""
    original = root.find(f'{{{P}}}notesMasterIdLst')
    imported = xml(incoming['ppt/presentation.xml']).find(f'{{{P}}}notesMasterIdLst')
    if any(group is not None and len(group) > 1 for group in [original, imported]):
        raise ValueError('输入演示文稿包含多个备注母版')
    if original is None or not len(original) or imported is None or not len(imported):
        return set()
    original_rel = next(r for r in rels if r.get('Id') == original[0].get(f'{{{R}}}id'))
    imported_rel = next(r for r in xml(incoming['ppt/_rels/presentation.xml.rels'])
                        if r.get('Id') == imported[0].get(f'{{{R}}}id'))
    existing = resolve_target('ppt', original_rel.get('Target'))
    redundant = resolve_target('ppt', imported_rel.get('Target'))
    mapping[redundant] = existing
    return {redundant, posixpath.join(posixpath.dirname(redundant), '_rels', posixpath.basename(redundant) + '.rels')}


def used_master_ids(parts, root):
    values = {int(n.get('id')) for n in root.findall(f'./{{{P}}}sldMasterIdLst/{{{P}}}sldMasterId')}
    for name, data in parts.items():
        if name.endswith('.xml') and '/slideMasters/' in name:
            values.update(int(n.get('id')) for n in xml(data).findall(f'.//{{{P}}}sldLayoutId'))
    return values


def next_master_id(used):
    candidate = max(used | {2147483647}) + 1
    if candidate > 4294967295:
        raise ValueError('母版编号超出 UInt32 范围')
    used.add(candidate)
    return str(candidate)


def normalize_roundtrip_cache(data, values):
    cached = xml(data).findall(f'.//{{{C}}}numCache/{{{C}}}pt/{{{C}}}v')
    if len(cached) != len(values):
        raise ValueError('图表缓存与工作簿长度不一致')
    for node, exact in zip(cached, values):
        previous = node.text
        if abs(Decimal(previous) - Decimal(exact)) > Decimal('1e-14'):
            raise ValueError('图表存在实质性数值差异，需要单独确认')
        if previous != exact:
            old = f'<c:v>{previous}</c:v>'.encode()
            if data.count(old) != 1:
                raise ValueError('图表缓存值无法唯一定位')
            data = data.replace(old, f'<c:v>{exact}</c:v>'.encode(), 1)
    return data


def normalize_source_survey(parts):
    chart = 'ppt/charts/chart1.xml'
    if chart not in parts:
        return
    formula = xml(parts[chart]).find(f'.//{{{C}}}numRef/{{{C}}}f').text
    if formula != "'Chart Data'!$B$2:$B$5":
        raise ValueError('原图表数据范围已变化，需要重新核对')
    rels = xml(parts['ppt/charts/_rels/chart1.xml.rels'])
    target = next(r.get('Target') for r in rels if r.get('Type').endswith('/package'))
    workbook = resolve_target('ppt/charts', target)
    with ZipFile(io.BytesIO(parts[workbook])) as z:
        sheet = xml(z.read('xl/worksheets/sheet1.xml'))
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    values = [sheet.find(f'.//s:c[@r="B{i}"]/s:v', ns).text for i in range(2, 6)]
    parts[chart] = normalize_roundtrip_cache(parts[chart], values)


def merge(source, modeling, output, keep):
    if output.exists():
        raise ValueError(f'输出已存在：{output}')
    with ZipFile(source) as z:
        base = {name: z.read(name) for name in z.namelist()}
    with ZipFile(modeling) as z:
        incoming = {name: z.read(name) for name in z.namelist()}
    original_order = ordered_slides(base)
    normalize_source_survey(base)
    model_order = ordered_slides(incoming)
    root = xml(base['ppt/presentation.xml'])
    rels = xml(base['ppt/_rels/presentation.xml.rels'])
    id_list = root.find(f'{{{P}}}sldIdLst')
    preserved_ids = {s.get(f'{{{R}}}id') for s, _ in original_order[:keep]}
    for item in list(id_list)[keep:]:
        id_list.remove(item)
    for item in list(rels):
        if item.get('Type').endswith('/slide') and item.get('Id') not in preserved_ids:
            rels.remove(item)

    # 新章节沿用原稿已嵌入的相同字体，避免复制仅被导入 presentation 引用的字体副本。
    mapping = map_parts(incoming, model_order, keep)
    skipped = reuse_notes_master(root, rels, incoming, mapping)
    used_ids = used_master_ids(base, root)
    for old, new in mapping.items():
        if old in skipped:
            continue
        data = incoming[old]
        if old.endswith('.xml') and '/slideMasters/' in old:
            master = xml(data)
            for layout in master.findall(f'.//{{{P}}}sldLayoutId'):
                layout.set('id', next_master_id(used_ids))
            data = serialize(master)
        elif old.endswith('.rels'):
            owner = posixpath.join(posixpath.dirname(posixpath.dirname(old)), posixpath.basename(old)[:-5])
            owner_new = mapping.get(owner, f'ppt/modeling/{owner}')
            relationships = xml(data)
            for relation in relationships:
                if relation.get('TargetMode') == 'External':
                    continue
                target = relation.get('Target')
                absolute = resolve_target(posixpath.dirname(owner), target)
                if absolute not in mapping:
                    raise ValueError(f'未映射关系：{old} -> {absolute}')
                relation.set('Target', posixpath.relpath(mapping[absolute], posixpath.dirname(owner_new)))
            data = serialize(relationships)
        base[new] = data

    for i, (_, part) in enumerate(model_order, 1):
        relation_id = f'rIdModelSlide{i}'
        E.SubElement(rels, f'{{{REL}}}Relationship', Id=relation_id, Type=f'{R}/slide', Target=posixpath.relpath(mapping[part], 'ppt'))
        E.SubElement(id_list, f'{{{P}}}sldId', id=str(10000 + i), attrib={f'{{{R}}}id': relation_id})

    import_root = xml(incoming['ppt/presentation.xml'])
    import_rels = {r.get('Id'): r for r in xml(incoming['ppt/_rels/presentation.xml.rels'])}
    for list_tag, child_tag, kind in [('sldMasterIdLst', 'sldMasterId', 'slideMaster'), ('notesMasterIdLst', 'notesMasterId', 'notesMaster')]:
        from_list = import_root.find(f'{{{P}}}{list_tag}')
        if from_list is None or (kind == 'notesMaster' and skipped):
            continue
        destination = root.find(f'{{{P}}}{list_tag}')
        if destination is None:
            destination = E.Element(f'{{{P}}}{list_tag}')
            # PresentationML 的母版列表有固定顺序。
            root.insert(0 if kind == 'slideMaster' else 1, destination)
        for i, item in enumerate(from_list, 1):
            relation = import_rels[item.get(f'{{{R}}}id')]
            part = resolve_target('ppt', relation.get('Target'))
            relation_id = f'rIdModel{kind}{i}'
            E.SubElement(rels, f'{{{REL}}}Relationship', Id=relation_id, Type=relation.get('Type'), Target=posixpath.relpath(mapping[part], 'ppt'))
            attrs = {f'{{{R}}}id': relation_id}
            if child_tag == 'sldMasterId':
                attrs['id'] = next_master_id(used_ids)
            E.SubElement(destination, f'{{{P}}}{child_tag}', attrs)

    content_types = xml(base['[Content_Types].xml'])
    extensions = {el.get('Extension') for el in content_types if el.tag == f'{{{CT}}}Default'}
    for el in xml(incoming['[Content_Types].xml']):
        if el.tag == f'{{{CT}}}Default' and el.get('Extension') not in extensions:
            content_types.append(copy.deepcopy(el))
            extensions.add(el.get('Extension'))
        elif (el.tag == f'{{{CT}}}Override' and el.get('PartName').lstrip('/') in mapping
              and el.get('PartName').lstrip('/') not in skipped):
            copied = copy.deepcopy(el)
            copied.set('PartName', '/' + mapping[el.get('PartName').lstrip('/')])
            existing = next((item for item in content_types if item.get('PartName') == copied.get('PartName')), None)
            if existing is not None:
                content_types.remove(existing)
            content_types.append(copied)
    base['ppt/presentation.xml'] = serialize(root)
    base['ppt/_rels/presentation.xml.rels'] = serialize(rels)
    base['[Content_Types].xml'] = serialize_content_types(content_types)
    if 'docProps/app.xml' in base:
        app = xml(base['docProps/app.xml'])
        for el in app:
            if el.tag.endswith('}Slides'):
                el.text = str(keep + len(model_order))
        base['docProps/app.xml'] = serialize(app)
    with ZipFile(output, 'x', ZIP_DEFLATED) as z:
        for name, data in base.items():
            z.writestr(name, data)
    with ZipFile(source) as z:
        for _, part in original_order[:keep]:
            assert base[part] == z.read(part), f'保留页发生变化：{part}'
    return {'preserved': keep, 'new': len(model_order), 'total': keep + len(model_order), 'output': str(output)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('modeling', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--keep', type=int, default=29)
    args = parser.parse_args()
    print(json.dumps(merge(args.source, args.modeling, args.output, args.keep), ensure_ascii=False))
