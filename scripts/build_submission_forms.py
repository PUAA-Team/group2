"""生成两阶段的提交表单；已有成果、图片与压缩包保持不动。"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/需求调研+需求建模/最终提交材料'
TEAM = '5组-王者灵宝的coding能力也不是不行'
DATE = '2026年10月20日'
SKILL = Path('C:/Users/lixu/.codex/plugins/cache/openai-primary-runtime/documents/26.1015.12040/skills/documents')


def font_style(style, name, size, bold=False):
    style.font.name = name
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), name)


def make_doc(stage, title):
    doc = Document()
    # 随附默认模板含标题蓝线，新建表单使用纯黑文字和留白。
    for border in list(doc.styles.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.top_margin, sec.bottom_margin = Cm(1.65), Cm(1.65)
    sec.left_margin, sec.right_margin = Cm(1.8), Cm(1.8)
    font_style(doc.styles['Normal'], '宋体', 11)
    doc.styles['Normal'].paragraph_format.line_spacing = 1.15
    doc.styles['Normal'].paragraph_format.space_after = Pt(5)
    font_style(doc.styles['Title'], '黑体', 19)
    doc.styles['Title'].paragraph_format.space_after = Pt(10)
    font_style(doc.styles['Heading 1'], '黑体', 12)
    doc.styles['Heading 1'].paragraph_format.space_before = Pt(10)
    doc.styles['Heading 1'].paragraph_format.space_after = Pt(6)
    doc.core_properties.title = stage + title
    doc.core_properties.subject = '大模型集成训练平台'
    doc.core_properties.author = '5组'
    doc.add_paragraph(stage + title, 'Title')
    doc.add_paragraph('项目  大模型集成训练平台')
    doc.add_paragraph('团队  5组  王者灵宝的coding能力也不是不行')
    doc.add_paragraph('编制日期  ' + DATE)
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    return doc


def table(doc, headers, rows, widths, size=10.5):
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    for col, width in zip(tbl.columns, widths):
        col.width = Cm(width)
    borders = OxmlElement('w:tblBorders')
    for edge in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        line = OxmlElement('w:' + edge)
        for key, val in [('val', 'single'), ('sz', '5'), ('color', 'D9D9D9')]:
            line.set(qn('w:' + key), val)
        borders.append(line)
    tbl._tbl.tblPr.append(borders)
    for values in [headers, *rows]:
        cells = tbl.rows[0].cells if values is headers else tbl.add_row().cells
        is_head = values is headers
        if is_head:
            repeat = OxmlElement('w:tblHeader')
            tbl.rows[0]._tr.get_or_add_trPr().append(repeat)
        for idx, (cell, text, width) in enumerate(zip(cells, values, widths)):
            cell.width = Cm(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tc_pr = cell._tc.get_or_add_tcPr()
            margins = OxmlElement('w:tcMar')
            for edge in ['top', 'left', 'bottom', 'right']:
                m = OxmlElement('w:' + edge)
                m.set(qn('w:w'), '75' if edge in ['top', 'bottom'] else '85')
                m.set(qn('w:type'), 'dxa')
                margins.append(m)
            tc_pr.append(margins)
            if is_head:
                shade = OxmlElement('w:shd')
                shade.set(qn('w:fill'), 'EEEEEE')
                tc_pr.append(shade)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.08
            # 短字段居中，说明字段左对齐，避免日期和状态贴边。
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if is_head or (len(text) <= 8 and '\n' not in text) else WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(text)
            run.font.size = Pt(size)
            run.bold = is_head
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return tbl


RESEARCH_CHANGES = [
    ('原型验证', '团队需求讨论', '报告第6.3节按业务流程补充两版原型的验证内容、页面截图与需求对应关系。', '核对原型流程、截图及第6.3节。'),
    ('算力与接入', '技术调研复核', '补充本地CPU、笔记本GPU、实验室与云平台的接入方式，说明统一计算接口及接入限制。', '对照第5.6节、平台资料与接入方案。'),
    ('GPU接入验证', '程序验证复核', '第6.4节增加单台RTX 4060的探测、注册、心跳、数据概况任务和结果回传记录。', '核对设备信息、15项检查及对应截图。'),
    ('验证结论', '团队内容复核', '分别说明界面演示、节点接入与任务回传的验证范围；模型训练和云平台接入按能力继续验证。', '核对第6.3、第6.4节及结论中的验证范围。'),
    ('配套提交材料', '提交材料核对', '新增调研阶段修改记录表、自查表和独立AI使用声明，登记待签署与待同步事项。', '打开三份Word，核对字段、清单和声明。'),
]

MODELING_CHANGES = [
    ('权限与数据', '团队规则复核', '统一用户组授权、个人允许和显式禁用；补齐配额、数据版本、模型依赖及推理服务约束。', '对照相关用例与32条业务规则。'),
    ('任务与故障', '团队需求讨论', '补齐九种训练主状态、幂等提交、资源预留、启动确认及16类故障；区分排队取消与运行停止。', '核对训练用例、状态表与故障表。'),
    ('智能辅助', '团队需求讨论', '保留4个智能辅助用例，补齐调用前检查、人工确认、过期与重复确认；采纳后生成新配置或新数据版本。', '核对AI用例、外发限制及结果采纳规则。'),
    ('验收与追踪', '文档一致性复核', '补齐14组验收条件与49个用例的对应关系，修订事件流、目录及表格说明。', '核对用例编号、验收条目及目录目标。'),
    ('图文保留', '团队修订约定', '现有图片内容与显示尺寸保持不变；新版文字细则由状态表、故障表与用例说明表达。', '对照图片资源及修订说明；图文完整同步待复核。'),
    ('配套提交材料', '提交材料核对', '新增建模阶段修改记录表、自查表和独立AI使用声明；登记SPEC、PPT及模型材料的待核事项。', '打开三份Word，核对记录与当前成果。'),
]


def change_record(stage):
    doc = make_doc(stage, '修改说明与版本记录表')
    doc.add_paragraph('本表记录本次修订及配套材料的变更。修改人与最终复核人由经办成员填写；教师或互评意见可在后续记录中补充原始反馈。')
    doc.add_paragraph('版本范围  2026年10月20日修订稿及本次新增表单')
    data = RESEARCH_CHANGES if stage == '需求调研' else MODELING_CHANGES
    rows = [(str(i), item, origin, content, '待签', '2026年\n10月20日', check) for i, (item, origin, content, check) in enumerate(data, 1)]
    table(doc, ['序号', '修改项', '反馈来源', '修改内容', '修改人', '修改日期', '验证方式'], rows,
          [1.1, 1.55, 1.8, 5.3, 1.55, 2.1, 4.59])
    doc.add_paragraph('后续记录', 'Heading 1')
    if stage == '需求调研':
        doc.add_paragraph('提交前需统一报告与PPT中的问卷题型数量、资源数量及验证范围，并更新压缩包。新增修改按同一字段继续登记。')
    else:
        doc.add_paragraph('提交前需将SPEC和PPT同步到SRS的任务状态、权限和智能辅助规则，并核对保留图片与新版文字的对应关系。')
    doc.add_paragraph('最终复核人  ______________    复核日期  ______________')
    return doc


def checklist(stage):
    research = stage == '需求调研'
    doc = make_doc(stage, '提交材料自查表')
    doc.add_paragraph('已备表示材料文件已具备；待核表示内容或签署仍需确认；另包表示随另一阶段成果提交。自查人逐项复核后填写姓名与最终结果。')
    common = [
        ('需求调研报告 Word', '已备' if research else '另包', '含平台、技术、67份问卷及两版原型验证。' if research else '随需求调研成果提交。'),
        ('需求调研汇报PPT', '待核' if research else '另包', '问卷题型数、资源数量和验证范围待与报告统一。' if research else '随需求调研成果提交。'),
        ('调研材料', '已备' if research else '另包', '平台记录、技术资料、问卷统计及两组原型源码已备。' if research else '随需求调研成果提交。'),
        ('系统需求规格说明书 SRS', '另包' if research else '已备', '随需求建模成果提交。' if research else '已放入2026年10月20日修订稿。'),
        ('核心模块开发规范 SPEC', '另包' if research else '待核', '随需求建模成果提交。' if research else '需同步九状态、取消与停止、权限及智能辅助规则。'),
        ('用例图 工程及导出图', '另包' if research else '待核', '随需求建模成果提交。' if research else '导出图已备；CodeArts Modeling工程与图文一致性待核。'),
        ('活动图 源文件及导出图', '另包' if research else '待核', '随需求建模成果提交。' if research else '导出图已备；可编辑模型工程与图文一致性待核。'),
        ('状态图 源文件及导出图', '另包' if research else '待核', '随需求建模成果提交。' if research else '导出图已备；模型工程和九状态文字对应关系待核。'),
        ('需求建模PPT及支撑材料', '另包' if research else '待核', '随需求建模成果提交。' if research else 'PPT已备；SPEC、智能辅助和失败处理展示待同步。'),
        ('修改说明与版本记录表', '已备', '本次已补；修改人与最终复核人待签名。'),
        ('AI使用声明', '待核', '独立Word已备；使用人核对版本、复核记录后签署。'),
        ('文件命名与目录层级', '待核', '主文件命名已统一；成果目录有同名重复层级。'),
        ('同版内容与导出文件', '待核', 'PPT与报告的数值和范围需统一；报告PDF由团队按需导出。' if research else 'SRS、SPEC、PPT与保留模型图需同版核对。'),
        ('最终压缩包', '待核', '现有ZIP仍是旧版；完成内容核对后重新打包。'),
    ]
    rows = [(str(i), item, status, '待填写', note) for i, (item, status, note) in enumerate(common, 1)]
    table(doc, ['序号', '材料', '是否完成', '自查人', '备注'], rows, [1.1, 4.4, 1.9, 1.65, 8.94])
    doc.add_paragraph('最终提交确认', 'Heading 1')
    doc.add_paragraph('本阶段待核项处理完毕后，由提交人确认最终文件与压缩包内容一致。另一阶段的材料保留在对应成果包内。')
    doc.add_paragraph('自查人  ______________    日期  ______________')
    doc.add_paragraph('提交人  ______________    日期  ______________')
    return doc


def ai_statement(stage):
    research = stage == '需求调研'
    doc = make_doc(stage, 'AI使用声明')
    doc.add_paragraph('本阶段使用AI辅助资料整理、内容分析和成果制作。各使用人核对下列登记、补充实际模型版本与复核记录后签署；最终提交内容由团队审核并承担责任。')
    doc.add_paragraph('两组使用登记', 'Heading 1')
    routes = [
        ('第一组', 'DeepSeek\n版本 __________', 'Claude Code', '国内商用平台与问卷调研' if research else '用户角色、操作场景、用户故事与系统用例'),
        ('第二组', '实际模型及版本\n________________', 'Codex', '国外商用平台、开源平台、技术资料与问卷分析' if research else '训练生命周期、活动流程、状态转换与异常处理'),
    ]
    table(doc, ['分组', '模型', '工具', '主要工作路线'], routes, [1.65, 4.55, 3.0, 8.79], 11)
    doc.add_paragraph('模型名称和版本以各组实际使用记录为准。Codex与Claude Code按工具登记；接入模型由使用人分别补充。')
    doc.add_paragraph('AI辅助内容', 'Heading 1')
    if research:
        content = [
            ('背景与平台调研', '辅助检索、归纳产品能力与差异，整理平台比较文字。', '平台调研记录、比较章节及部分PPT文字'),
            ('技术与可行性', '辅助整理模型、框架、数据集和异构算力的技术方案。', '技术调研与算力接入分析'),
            ('问卷分析', '辅助问卷题目设计、统计核对与需求归纳。', '问卷分析文字及统计展示'),
            ('原型与材料', '辅助制作原型界面、PDF提取工具、报告排版与提交表单。', '原型代码、验证说明和配套文档'),
        ]
        prompts = [
            '“pdf提取的工具以及代码可以写好一份，之后直接复用。pdf转为markdown之后就直接读markdown版本”',
            '“同时可以把咱们的原型验证部分也放需求调研文档里面，多截点图”',
        ]
    else:
        content = [
            ('需求与用例', '辅助梳理功能边界、前后置条件、事件流和备选流程。', 'SRS用例文字、业务规则和验收条目'),
            ('流程与模型', '辅助整理活动流程、任务状态、异常分支及绘图代码。', '模型描述、部分图稿和绘图代码'),
            ('新增规则', '辅助细化权限、资源释放、故障处理和智能辅助的人工确认规则。', 'SRS补充规则、故障表和状态表'),
            ('材料制作', '辅助整理SPEC及PPT初稿、检查文档一致性和生成提交表单。', '规范文字、PPT文字与配套文档'),
        ]
        prompts = [
            '“需求规格说明书的问题你帮我完整修改。但是最好不要修改以前的图片，可以改文档内容，但是不要改图。”',
            '“不要彩色的，做那种黑白论文级别的图片。不要堆叠，确定满足软工标准吧？”',
        ]
    table(doc, ['使用环节', '辅助方式', '涉及成果'], content, [2.6, 8.1, 7.29], 10.5)
    doc.add_paragraph('提示词摘录', 'Heading 1')
    for prompt in prompts:
        doc.add_paragraph(prompt)
    doc.add_paragraph('以上为任务提示词节选。各组补充本人实际使用的典型交互记录及生成内容，便于对应成果与修改过程。')

    doc.add_page_break()
    doc.add_paragraph('人工复核与责任确认', 'Heading 1')
    if research:
        checks = [
            ('平台与技术事实', '回到官方资料、实际调研记录及平台界面核对能力与限制。', '待成员确认'),
            ('问卷统计', '对照67份问卷统计核算人数和比例，统一报告与PPT的单选、多选题数量。', '待统一题型数'),
            ('原型验证', '区分前端演示、GPU接入与任务回传；训练结果仅据实际记录填写。', '待成员确认'),
            ('文字与引用', '完整阅读AI生成段落，检查引用、术语及结论是否有材料支持。', '待成员确认'),
        ]
    else:
        checks = [
            ('用例与业务规则', '逐项核对参与者、条件、事件步骤、权限、版本及验收对应关系。', '待成员确认'),
            ('任务状态与故障', '区分排队取消、运行停止、节点失联和资源清理；统一SRS、SPEC与PPT。', '待同步SPEC'),
            ('模型与图文', '人工检查UML语义、守卫条件及泳道职责，并核对保留图稿与新版规则。', '待模型复核'),
            ('智能辅助', '核对建议经人工确认后生成新配置或新数据版本；外发范围保持待确认。', '待成员确认'),
        ]
    table(doc, ['复核对象', '人工复核方法', '当前记录', '复核人及日期'],
          [(obj, method, status, '____________\n____________') for obj, method, status in checks],
          [2.9, 8.3, 2.5, 4.29], 11)
    doc.add_paragraph('典型人工修订记录', 'Heading 1')
    doc.add_paragraph('由实际经办人填写一项代表性记录，说明AI输出存在的问题、采用的核对依据及最后修改。可按实际情况复制增加。')
    doc.add_paragraph('涉及成果或位置  __________________________________________________')
    doc.add_paragraph('AI原输出及问题  __________________________________________________')
    doc.add_paragraph('核对依据与修改  __________________________________________________')
    doc.add_paragraph('修改人及日期    __________________________________________________')
    doc.add_paragraph('资料与使用范围', 'Heading 1')
    doc.add_paragraph('请使用人核对输入材料、脱敏情况及可公开范围。交互记录中隐藏账号凭据、API密钥和个人敏感信息。')
    doc.add_paragraph('实际输入材料及处理情况  __________________________________________')
    doc.add_paragraph('团队责任声明', 'Heading 1')
    doc.add_paragraph('我们对最终提交材料中的数据、引用、需求规则及模型含义进行人工审核，能够说明主要结论的依据和模型的业务含义，并对AI辅助内容的准确性及合规使用承担责任。')
    doc.add_paragraph('第一组使用人签名  __________________    日期  ______________')
    doc.add_paragraph('第二组使用人签名  __________________    日期  ______________')
    doc.add_paragraph('团队审核人签名    __________________    日期  ______________')
    return doc


def targets():
    result = []
    for prefix, stage in [('01', '需求调研'), ('02', '需求建模')]:
        name = TEAM + '-' + stage + '成果'
        folder = BASE / name / name
        if not folder.is_dir():
            raise FileNotFoundError(folder)
        for title, builder in [('修改说明与版本记录表', change_record), ('提交材料自查表', checklist), ('AI使用声明', ai_statement)]:
            result.append((folder / f'{prefix}-{title}-{TEAM}.docx', stage, builder))
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--render-only', action='store_true')
    parser.add_argument('--revise-generated', action='store_true')
    parser.add_argument('--render-folder', default='preview-final')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    items = targets()
    if args.revise_generated:
        # 只允许迭代本次生成且无人修改的六个文件，先保存可恢复副本。
        manifest = json.loads((args.work / 'render-manifest.json').read_text(encoding='utf-8'))
        expected = {entry['source']: entry['sha256'] for entry in manifest}
        for path, _, _ in items:
            assert digest(path) == expected[str(path)], '交付已被修改，停止覆盖：' + str(path)
        backup = args.work / 'first-draft'
        backup.mkdir(exist_ok=False)
        for idx, (path, stage, builder) in enumerate(items, 1):
            shutil.copy2(path, backup / f'doc-{idx}.docx')
            builder(stage).save(path)
        args.render_only = True
    if not args.render_only:
        # 先确认全部目标，避免部分覆盖；既有交付一律不覆盖。
        for path, _, _ in items:
            if path.exists():
                raise FileExistsError(path)
        before = {str(p): digest(p) for p in BASE.rglob('*') if p.is_file()}
        for path, stage, builder in items:
            builder(stage).save(path)
            print(json.dumps({'created': str(path)}, ensure_ascii=False), flush=True)
        for path, expected in before.items():
            assert digest(Path(path)) == expected, '既有材料发生变化：' + path
        (args.work / 'preserved-files.json').write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding='utf-8')

    spec = importlib.util.spec_from_file_location('native_renderer', ROOT / 'scripts/render_word_native.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.SKILL = SKILL
    results = []
    for idx, (path, _, _) in enumerate(items, 1):
        output = args.work / args.render_folder / f'doc-{idx}'
        result = renderer.render(path, output, args.work / 'temp')
        result.update({'source': str(path), 'sha256': digest(path)})
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    (args.work / 'render-manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
