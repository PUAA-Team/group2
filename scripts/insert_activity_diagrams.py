"""在原规约的活动图单元格插图，仅局部修改 OOXML 并另存新文件。"""
import argparse
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt
from lxml import etree
from PIL import Image

NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p':'http://schemas.openxmlformats.org/package/2006/relationships',
    'ct':'http://schemas.openxmlformats.org/package/2006/content-types',
    'v':'urn:schemas-microsoft-com:vml'}


def tag(name):
    prefix,local=name.split(':');return '{'+NS[prefix]+'}'+local


def text(element):return ''.join(element.xpath('.//w:t/text()',namespaces=NS))


def element(parent,name,**attrs):
    existing=parent.find(tag(name))
    if existing is None:existing=etree.SubElement(parent,tag(name))
    for key,value in attrs.items():existing.set(tag('w:'+key),str(value))
    return existing


def replace_cell(cell,old,new,changes,label):
    nodes=cell.findall('.//w:t',NS)
    full=''.join(node.text or '' for node in nodes)
    count=full.count(old)
    if count!=1:raise ValueError(f'{label} 文本定位不唯一：{count}')
    start=full.index(old);end=start+len(old);offset=0;inserted=False
    for node in nodes:
        value=node.text or '';stop=offset+len(value)
        if stop>start and offset<end:
            prefix=value[:max(0,start-offset)]
            suffix=value[max(0,end-offset):] if end<stop else ''
            node.text=prefix+('' if inserted else new)+suffix
            inserted=True
        offset=stop
    changes.append(dict(location=label,old=old,new=new))


def create_picture(image_path,identifier,width_mm,height_mm,rid,doc_id):
    helper=Document();p=helper.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(3)
    p.paragraph_format.line_spacing=1;p.paragraph_format.keep_with_next=False
    p.paragraph_format.keep_together=True
    picture=p.add_run().add_picture(str(image_path),width=Mm(width_mm),height=Mm(height_mm))
    picture._inline.docPr.set('id',str(doc_id))
    picture._inline.docPr.set('name',identifier+' 活动图')
    picture._inline.docPr.set('descr',identifier+' 黑白 UML 活动图，展示基本和备选流程。')
    root=deepcopy(p._p)
    root.find('.//a:blip',NS).set(tag('r:embed'),rid)
    return root


def insert(source,images,output,report):
    if output.exists():raise ValueError(f'输出已存在：{output}')
    with ZipFile(source) as package:
        parts={name:package.read(name) for name in package.namelist()}
    original_parts=dict(parts)
    root=etree.fromstring(parts['word/document.xml'])
    rels=etree.fromstring(parts['word/_rels/document.xml.rels'])
    types=etree.fromstring(parts['[Content_Types].xml'])
    if not any(e.get('Extension')=='png' for e in types):
        etree.SubElement(types,tag('ct:Default'),Extension='png',ContentType='image/png')
    used={e.get('Id') for e in rels};counter=1
    max_id=max([int(e.get('id')) for e in root.findall('.//wp:docPr',NS)]+[0])
    records=[];changes=[]
    tables=root.findall('w:body/w:tbl',NS)
    for index,table in enumerate(tables):
        rows=table.findall('w:tr',NS)
        match=re.search(r'UC-[A-Z]+-\d{2}',text(rows[0]))
        if not match:continue
        identifier=match.group()
        activity=[row for row in rows if text(row).startswith('活动图')]
        if len(activity)!=1:raise ValueError(f'{identifier} 活动图行不存在或重复')
        row=activity[0];cell=row.findall('w:tc',NS)[-1]
        image=images/(identifier+'.png')
        with Image.open(image) as im:pw,ph=im.size
        # 原有单元格约 120 mm；为大图保留标题行与页眉页脚空间。
        width_mm=min(116,215*pw/ph);height_mm=width_mm*ph/pw
        while f'rId{counter}' in used:counter+=1
        rid=f'rId{counter}';used.add(rid)
        media=f'media/activity-{identifier}.png'
        etree.SubElement(rels,tag('p:Relationship'),Id=rid,Type=NS['r']+'/image',Target=media)
        parts['word/'+media]=image.read_bytes()
        for child in list(cell):
            if child.tag!=tag('w:tcPr'):cell.remove(child)
        max_id+=1
        cell.append(create_picture(image,identifier,width_mm,height_mm,rid,max_id))
        properties=element(row,'w:trPr');element(properties,'w:cantSplit')
        for h in properties.findall('w:trHeight',NS):properties.remove(h)
        element(element(rows[0],'w:trPr'),'w:tblHeader')
        if identifier=='UC-TRN-05':
            replace_cell(table,'进程终止且资源释放后标记已取消','进程终止且资源释放后标记已停止',changes,identifier+' 备选4b')
        if identifier=='UC-TRN-06':
            for candidate in rows:
                label=text(candidate.findall('w:tc',NS)[0])
                if label=='后置条件':
                    replace_cell(candidate,'队列项已移除，或进程已终止且资源已释放；任务标记已取消并记录操作信息。',
                                 '排队任务的队列项已移除并标记已取消；运行任务的进程已终止且资源已释放，并标记已停止；两类操作均记录操作信息。',changes,identifier+' 后置条件')
                elif '基本' in text(candidate)[:20]:
                    replace_cell(candidate,'5. 系统确认进程终止及资源释放，标记已取消并记录操作者和时间。',
                                 '5. 排队任务移除队列项后标记已取消；运行任务确认进程终止及资源释放后标记已停止；系统记录操作者和时间。',changes,identifier+' 基本5')
        records.append(dict(id=identifier,table=index+1,width_mm=round(width_mm,2),height_mm=round(height_mm,2),
                            pixels=[pw,ph],sha256=hashlib.sha256(image.read_bytes()).hexdigest()))
    if len(records)!=45:raise ValueError(f'用例数量不是45：{len(records)}')
    # 同步原有状态图：排队取消与运行停止分别进入已取消、已停止。
    state=images/'训练任务状态图.png'
    state_shapes=[e for e in root.findall('.//v:shape',NS) if '训练任务状态图' in (e.get('alt') or '')]
    if len(state_shapes)!=1:raise ValueError('原有训练状态图定位不唯一')
    state_shape=state_shapes[0]
    state_rid=state_shape.find('v:imagedata',NS).get(tag('r:id'))
    state_rel=next(e for e in rels if e.get('Id')==state_rid)
    state_rel.set('Target','media/training-task-state.png')
    parts['word/media/training-task-state.png']=state.read_bytes()
    # 原 VML 的 gfxdata 包含旧图缓存，清除该图缓存以使用新图，其他图保持原样。
    state_shape.attrib.pop('{urn:schemas-microsoft-com:office:office}gfxdata',None)
    for p in root.findall('w:body/w:p',NS):
        if '训练任务状态至少包括草稿' in text(p):
            replace_cell(p,'停止中、成功、失败和已取消','停止中、成功、失败、已取消和已停止',changes,'训练任务总状态列表')
    for name,node in [('word/document.xml',root),('word/_rels/document.xml.rels',rels),('[Content_Types].xml',types)]:
        parts[name]=etree.tostring(node,encoding='UTF-8',xml_declaration=True,standalone=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,'w',ZIP_DEFLATED) as package:
        for name,data in parts.items():package.writestr(name,data)
    changed=[name for name,data in original_parts.items() if parts[name]!=data]
    assert set(changed)=={'word/document.xml','word/_rels/document.xml.rels','[Content_Types].xml'},changed
    data=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),output=str(output),
              figures=records,text_changes=changes,changed_original_parts=changed,
              preserved_parts=len(original_parts)-len(changed))
    report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['source','images','output','report']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    result=insert(args.source,args.images,args.output,args.report)
    print(json.dumps(dict(figures=len(result['figures']),text_changes=result['text_changes']),ensure_ascii=False,indent=2))
