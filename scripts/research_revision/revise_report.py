"""保留调研原稿，替换验证章节并同步相邻结论。"""
import argparse
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import re
import shutil

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from PIL import Image

from report_content import FLOW, COMPUTE
from polish_report import polish

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / 'docs/需求调研+需求建模/初步提交材料'
SOURCE = ROOT / '需求调研报告_修订版_20261019.docx'
OUTPUT = ROOT / '需求调研报告_完整修订版_20261020.docx'
SUPPORT = ROOT / '支撑材料/原型验证_20261020'


def paragraphs(container):
    for p in container.paragraphs:
        yield p
    for table in container.tables:
        for row in table.rows:
            seen = set()
            for cell in row.cells:
                if id(cell._tc) not in seen:
                    seen.add(id(cell._tc))
                    yield from paragraphs(cell)


def set_text(p, text):
    if p.text == text:
        return
    for run in p.runs:
        run.text = ''
    if p.runs:
        p.runs[0].text = text
    else:
        p.add_run(text)


def add_p(doc, anchor, text, style='Normal'):
    p = doc.add_paragraph(text, style=style)
    anchor.addprevious(p._p)
    p.paragraph_format.keep_with_next = style.startswith('Heading')
    p.paragraph_format.widow_control = True
    if style == 'Normal':
        p.paragraph_format.space_after = Pt(6)
        if text:
            p.paragraph_format.first_line_indent = Pt(24)
    return p


def add_table(doc, anchor, rows, widths):
    table = doc.add_table(rows=0, cols=len(widths))
    table.autofit = False
    borders = OxmlElement('w:tblBorders')
    for side in ['top', 'bottom', 'left', 'right', 'insideH', 'insideV']:
        border = OxmlElement('w:' + side)
        for key, value in [('val', 'single'), ('sz', '4'), ('color', 'D9D9D9')]:
            border.set(qn('w:' + key), value)
        borders.append(border)
    table._tbl.tblPr.append(borders)
    for i, values in enumerate(rows):
        row = table.add_row()
        if not i:
            row._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        for cell, value, width in zip(row.cells, values, widths):
            cell.width = Cm(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(str(value))
            r.font.size = Pt(10.5)
            r.bold = not i
            if not i:
                shade = OxmlElement('w:shd')
                shade.set(qn('w:fill'), 'E7E6E6')
                cell._tc.get_or_add_tcPr().append(shade)
    anchor.addprevious(table._tbl)
    return table


def figure(doc, anchor, blob, caption, crop=None):
    p = add_p(doc, anchor, '')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.keep_with_next = True
    w, h = Image.open(BytesIO(blob)).size
    crop = crop or (0, 0, 0, 0)
    left, top, right, bottom = crop
    height = 15.5 * h * (1 - top - bottom) / (w * (1 - left - right))
    pic = p.add_run().add_picture(BytesIO(blob), width=Cm(15.5), height=Cm(height))
    if any(crop):
        fill = pic._inline.graphic.graphicData.pic.blipFill
        rect = OxmlElement('a:srcRect')
        for name, value in zip(['l', 't', 'r', 'b'], crop):
            rect.set(name, str(round(value * 100000)))
        fill.insert(1, rect)
    p = add_p(doc, anchor, caption)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_after = Pt(10)
    for run in p.runs:
        run.font.size = Pt(11)


def main(work):
    if OUTPUT.exists() or SUPPORT.exists():
        raise FileExistsError('交付文件已存在，请另选版本，禁止覆盖')
    evidence = json.loads((work / 'verification.json').read_text(encoding='utf-8'))
    assert len(evidence['checks']) == 15 and all(c['passed'] for c in evidence['checks'])
    doc = Document(SOURCE)
    old_images = {}
    previous = None
    for p in doc.paragraphs:
        embeds = p._p.xpath('.//a:blip/@r:embed')
        if embeds:
            previous = doc.part.related_parts[embeds[0]].blob
        match = re.match(r'图\s*(6-\d+)\s', p.text)
        if match and previous:
            old_images[match[1]] = previous
    assert len(old_images) == 16
    SUPPORT.mkdir(parents=True)
    image_dir = SUPPORT / '图片'
    image_dir.mkdir()
    for key, blob in old_images.items():
        (image_dir / ('F' + key + '.jpg')).write_bytes(blob)
    for path in (work / 'screenshots').glob('*.png'):
        shutil.copy2(path, image_dir / path.name)
    shutil.copy2(work / 'verification.json', SUPPORT / 'GPU接入验证记录.json')
    shutil.copy2(work / 'preparation.json', SUPPORT / '运行环境与原包校验.json')
    shutil.copy2(SOURCE, work / '需求调研报告_修改前快照.docx')

    start = next(p for p in doc.paragraphs if p.text == '6.3 原型验证')
    end = next(p for p in doc.paragraphs if p.text == '7 需求点与可借鉴创新点')
    node = start._p
    while node is not end._p:
        following = node.getnext()
        node.getparent().remove(node)
        node = following
    for block in FLOW + COMPUTE:
        kind = block[0]
        if kind in ['p', 'h2', 'h3']:
            add_p(doc, end._p, block[1], {'p': 'Normal', 'h2': 'Heading 2', 'h3': 'Heading 3'}[kind])
        elif kind == 'fig':
            crop = (0, 0, 0, .20) if block[1] == '6-11' else None
            figure(doc, end._p, old_images[block[1]], f'图{block[1]}　{block[2]}', crop)
        elif kind == 'workerfig':
            name, number, title = block[1:]
            crop = {'W02_训练配置': (0, 0, 0, .22), 'W03_推理配置': (0, 0, 0, .42),
                    'W04_GPU节点在线': (0, 0, 0, .59), 'W06_GPU节点离线': (0, 0, 0, .59),
                    'W05_Worker任务日志': (.175, .31, .175, .31)}[name]
            figure(doc, end._p, (image_dir / (name + '.png')).read_bytes(), f'图{number}　{title}', crop)
        elif kind == 'checks':
            add_p(doc, end._p, '表6-1　GPU接入与计算执行检查结果')
            rows = [['检查项目', '结果', '核对内容']]
            details = [
                ('节点注册与硬件探测', 'RTX 4060 Laptop与8188 MiB显存写入节点记录'),
                ('连续心跳更新', '后次心跳时间大于前次，节点在线'),
                ('无效凭据拒绝', '节点查询返回401'),
                ('数据目录加载', '五份小样本数据集可查询'),
                ('异步任务受理', '返回任务标识与排队状态'),
                ('Worker 领取与子进程执行', '任务正常完成并保存执行节点'),
                ('真实样本结果回传', '样本30条，两个标签各15条'),
                ('事件日志保存', '排队、调度、启动和完成事件可查询'),
                ('运行时不匹配保持排队', '不向缺少对应运行时的节点派发'),
                ('运行时不匹配保持排队后取消', '取消后保存CANCELLED结果'),
                ('显存不足保持排队', '超出设备容量的请求未启动'),
                ('显存不足保持排队后取消', '排队取消成功'),
                ('不存在数据集拒绝受理', '返回400，保留错误原因'),
                ('执行结束回到空闲', '节点恢复IDLE且清空当前任务关联'),
                ('节点失联识别', '停止Worker后超过30秒显示离线')]
            actual = {c['name']: c for c in evidence['checks']}
            for name, detail in details:
                assert actual[name]['passed']
                rows.append([name, '通过', detail])
            add_table(doc, end._p, rows, [5.2, 1.5, 8.8])

    # 同步报告前后引用，保留原始问卷和同类平台调研数据。
    changes = {
        '原型验证作为问卷和技术调研之后': '原型验证沿完整业务流程开展，结合综合业务原型核对数据、训练、监控、模型、推理及管理操作，再以独立计算执行原型复核GPU接入、任务匹配和结果回传。两条验证线共同支持需求边界与优先级的确定。',
        '（7）原型验证补充结论。': '（7）原型验证覆盖完整业务流程，并完成单台RTX 4060节点的注册、心跳、数据概况任务及结果回传复核。15项检查通过，支持采用控制面与Worker分离的接入路线。模型训练、节点治理和云平台接入按能力分别验收，相关要求见第6.3与6.4节。',
        '（1）资源组+配额的管理员分配模型。': '（1）资源组与配额管理。管理员将设备纳入资源组，按用户或用户组分配可用设备范围、数量及时间上限，并限定任务类型。用户在授权范围内接受自动推荐或手动指定设备。组与个人允许合并后排除显式禁用；配额取组与个人上限的较小值。启动前重新核对真实占用与预留，资源组用于组织设备，设备级约束继续保留。',
        '（3）两个关键设计决策有明确调研依据：': '（3）管理员采用资源组、设备范围、配额和任务类型组合管理算力；训练表单采用常用参数与高级参数分层，任务详情按标签页组织。对应问卷支持率分别为73.13%和40.3%。GPU接入验证进一步支持Worker主动连接控制端的路线。',
        '（6）技术可行性与调研边界：': '（6）技术可行性方面，项目已提供Qwen3-0.6B、PyTorch、Transformers和LoRA的文本二分类训练与推理原型。本轮独立复核个人GPU的硬件探测、注册、任务领取和结果回传。PAI、Azure ML及开源平台的调研按实际体验与资料范围记录，跨平台接入和多机训练继续按场景验证。',
    }
    for p in list(paragraphs(doc)):
        text = p.text
        if text.strip() == '软件系统分析与设计作业':
            p._p.getparent().remove(p._p)
            continue
        for prefix, replacement in changes.items():
            if text.startswith(prefix):
                text = replacement
                break
        text = text.replace('任务书对平台需求的描述是概要性的，具体界面形态、业务逻辑和子功能取舍需要通过调研明确。',
            '平台的界面形态、业务规则和功能优先级通过资料研读、平台体验、问卷与原型验证确定。')
        text = text.replace('平台调研先对照任务书列出需要澄清的问题', '平台调研先围绕业务目标列出需要澄清的问题')
        text = text.replace('课程环境下', '现有资源条件下').replace('课程部署条件', '实际部署条件')
        text = text.replace('任务书', '项目目标')
        text = text.replace('课程可对接的', '可接入的').replace('课程场景', '项目场景')
        text = text.replace('2026-10-19统一约定；', '权限与数据保护规则；')
        text = text.replace('统一约定；第6.3节原型验证；成熟平台的智能辅助做法', '原型流程验证；人工确认与外发授权规则')
        text = text.replace('小规模指令数据', '小规模二分类文本数据')
        if text.startswith('小组内已确认4张RTX 4060'):
            text = '团队可使用的资源包括RTX 4060、RTX 4070笔记本GPU及CPU主机。笔记本GPU的标准显存为8 GB，逐设备接入时探测实际总显存与空闲显存[6]；本轮RTX 4060实测总显存8188 MiB。多台设备优先承接独立任务，单任务按所分配设备的容量判断。'
        text = text.replace('笔记本GPU4060×4、4070×1', 'RTX 4060、RTX 4070笔记本GPU')
        text = text.replace('现有CPU、5张笔记本GPU与已完成的真实训练Demo', '现有CPU、笔记本GPU与训练执行原型')
        text = text.replace('管理员分配采用"资源组+配额"模型：资源组划分、按用户/组设卡数与时长上限、作业类型开关；不做单卡授权',
            '管理员采用资源组、设备范围、用户组与个人授权、卡数及时间配额、任务类型的组合规则')
        text = text.replace('适合做进一期但不必做重', '列入P1增强范围，先采用模板与检查点兼容性校验')
        text = text.replace('部署流量切分（加分项）', '部署流量切分').replace('可作为部署模块的加分功能；不做也不影响主流程', '作为后续部署能力扩展')
        text = text.replace('实现成本不高（多个部署后端+权重路由）', '需要多个部署后端和权重路由')
        text = text.replace('实现成本极低（提交后锁定表单，克隆时复制全套配置）', '实现时需冻结配置、保留来源并重新校验权限与版本')
        text = text.replace('项目组已用Qwen3-0.6B、PyTorch、Transformers、LoRA和小规模二分类文本数据构建最小可运行Demo，这一组合说明有限算力也能验证完整训练链路，可作为一期开发和测试的实践起点。',
            '项目组提供了Qwen3-0.6B文本二分类训练与推理原型；本轮GPU接入复核覆盖节点注册、任务执行及结果回传，可作为训练模板与计算协议集成的起点。')
        set_text(p, text)
    method = next(p for p in doc.paragraphs if p.text == '1.2 调研方法与范围')
    add_p(doc, method._p.getnext(), '背景资料研读覆盖模型训练与推理的业务过程、模型及数据许可证、训练框架文档和资源管理机制。平台调研比较商业平台与开源项目，问卷采集普通用户和管理员对功能、页面与资源限制的偏好，原型验证进一步检查业务衔接与GPU接入。调查对象同时包括模型使用者、平台管理员及承担资源和运行维护的人员；本轮原型复核由项目组开展。')
    section2 = next(p for p in doc.paragraphs if p.text == '2 商用训推平台调研')
    add_p(doc, section2._p, '调研工作于2026年9月启动平台体验与资料整理，10月9日形成合并报告，10月12日补充技术与算力分析，10月19日补充业务原型验证，10月20日完成GPU接入复核并统一需求结论。问卷原始统计与样本范围保留在第6.1、6.2节及附录A。')
    # 基础恢复优先于增强功能，避免章节之间重复出现不同优先级。
    priority_table = next(t for t in doc.tables if t.cell(0, 0).text == '档位')
    for row in priority_table.rows:
        cells = row.cells
        if '模型/数据集下载通道' in cells[1].text:
            cells[1].text = '模型/数据集下载通道（HuggingFace/ModelScope，含复用与额度）'
        if '断点续训' in cells[1].text:
            cells[1].text = cells[1].text.replace('、断点续训（问卷23.88%）', '')
    for values in [
        ['一期必做', '不可变配置快照、克隆重跑、失败阶段与原始证据、任务终态和资源清理分别记录', '完整业务流程验证；失败恢复要求'],
        ['增强项', '从校验通过的检查点恢复训练；兼容性检查与恢复记录', '平台调研；问卷23.88%；模板依赖']]:
        row = priority_table.add_row()
        for cell, text in zip(row.cells, values):
            cell.text = text
    version = doc.tables[1].add_row()
    for cell, value in zip(version.cells, ['5', '20261020', '项目组', '待复核', '重写完整业务流程验证，新增GPU接入实测与截图，统一权限、恢复与优先级表述']):
        cell.text = value
    all_text = '\n'.join(p.text for p in paragraphs(doc))
    for forbidden in ['课程要求', '老师要求', '任务书', '课程环境', '前端演示', '只观察了第一步', '统一约定；']:
        assert forbidden not in all_text, forbidden
    assert '15项检查通过' in all_text
    assert all(f'图6-{i}' in all_text for i in range(1, 22))
    polish(doc).save(OUTPUT)
    print(json.dumps({'output': str(OUTPUT), 'support': str(SUPPORT), 'figures': 21, 'checks': 15}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('work', type=Path)
    main(parser.parse_args().work.resolve())
