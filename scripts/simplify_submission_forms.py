"""精简四份提交文档，版本记录严格取自对应正式Word。"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

from docx import Document
from docx.shared import Pt

from build_submission_forms import BASE, ROOT, SKILL, TEAM, make_doc, table


CONTENT = {
    '需求调研': [
        ('', '本项目在需求调研阶段使用AI辅助资料检索、内容分析和文字整理。第一组主要使用DeepSeek及Claude Code，围绕国内商用平台和问卷开展调研；第二组主要使用Codex，围绕国外商用平台、开源项目和技术可行性开展调研。两组交流各自发现，形成项目的调研结论与需求范围。'),
        ('使用内容', 'AI辅助归纳平台的数据管理、训练配置、资源调度、模型管理与推理服务能力，整理模型、框架、数据集及算力接入方案，并协助形成平台比较和技术可行性分析文字。相关能力与限制结合官方资料、团队平台调研记录和实际体验核对。'),
        ('', '问卷调研中，AI参与部分题目设计、统计结果解释和用户需求归纳。问卷发放与回收由团队完成，分析依据为67份有效问卷的统计结果。原型验证中，AI辅助原型程序与界面制作、流程整理和说明文字编写；报告及PPT的部分文字使用AI进行结构调整和语言润色。'),
        ('团队工作', '团队确定调研对象、组织问卷、体验平台并运行原型，对AI提供的资料和建议进行筛选。核对重点包括资料来源、平台能力、问卷人数与比例、方案适用条件，以及原型实际验证的范围。团队通过阅读与讨论修订需求理解偏差、缺乏依据的推断和冗余表达。'),
        ('责任说明', 'AI辅助内容用于支持调研与表达，项目需求和方案取舍由团队讨论确定。我们对最终提交材料的数据、引用及调研结论承担责任，并遵守资料使用与个人信息保护要求。'),
    ],
    '需求建模': [
        ('', '本项目在需求建模阶段使用AI辅助梳理业务场景、完善用例文字及检查需求规则。第一组主要使用DeepSeek及Claude Code，从用户角色和操作场景出发梳理用户故事与系统用例；第二组主要使用Codex，从训练任务生命周期出发分析活动流程、状态转换和异常处理。两组讨论后统一主要业务规则。'),
        ('使用内容', 'AI辅助整理参与者、功能边界、用例前后置条件、基本事件流和备选流程，补充数据与模型版本、用户组与个人权限、任务提交和资源分配等规则，并协助形成SRS与SPEC的部分文字。'),
        ('', '在需求细化中，AI协助分析排队取消、运行停止、节点失联、训练故障和资源清理的处理条件，以及外部大模型辅助解释日志、推荐参数和辅助标注的功能约束。建议采纳后生成新配置或新数据版本，相关业务决定由团队确定。文档制作中，AI还辅助整理章节、统一术语、润色部分文字，并检查SRS、SPEC和PPT之间的表述差异。'),
        ('团队工作', '团队结合调研结果与原型流程确定功能范围，讨论AI建议并修订需求表达。复核重点包括用例条件与步骤是否衔接、权限和配额规则是否清楚、任务状态与故障处理是否一致，以及验收条目能否对应具体用例。对需求理解错误、范围扩张和重复表达进行人工调整。'),
        ('责任说明', '项目需求、业务规则及最终取舍由团队负责。我们应能够解释所提交材料的业务含义、关键约束与验收依据，并对AI辅助内容的准确性和合规使用承担责任。'),
    ],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def minimal_document(stage, title):
    doc = make_doc(stage, title)
    # 保留已验收的黑白样式，去掉元信息与任何填写栏。
    for para in list(doc.paragraphs)[1:]:
        para._p.getparent().remove(para._p)
    doc.styles['Normal'].font.size = Pt(12)
    doc.styles['Normal'].paragraph_format.line_spacing = 1.3
    doc.styles['Normal'].paragraph_format.space_after = Pt(8)
    return doc


def original_records(source):
    for tbl in Document(source).tables:
        values = [[c.text for c in row.cells] for row in tbl.rows]
        if values and values[0] == ['版本', '提交日期', '主要编制人', '审核人', '版本说明']:
            return [row for row in values if any(t.strip() for t in row)]
    raise ValueError('没有找到原始版本记录表：' + str(source))


def files():
    result = []
    for prefix, stage in [('01', '需求调研'), ('02', '需求建模')]:
        name = TEAM + '-' + stage + '成果'
        folder = BASE / name / name
        sources = [('需求调研报告', folder / f'01-需求调研报告-{TEAM}.docx')] if prefix == '01' else [
            ('系统需求规格说明书', folder / f'02-SRS-{TEAM}.docx'),
            ('核心模块开发规范', folder / f'02-SPEC-{TEAM}.docx'),
        ]
        result.append({
            'stage': stage, 'sources': sources,
            'record': folder / f'{prefix}-修改说明与版本记录表-{TEAM}.docx',
            'ai': folder / f'{prefix}-AI使用声明-{TEAM}.docx',
            'checklist': folder / f'{prefix}-提交材料自查表-{TEAM}.docx',
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    items = files()
    originals = [p for entry in items for key in ['record', 'ai', 'checklist'] for p in [entry[key]]]
    originals.append(ROOT / 'docs/ReadMe.md')
    for p in originals:
        if not p.resolve().is_relative_to(ROOT.resolve()) or not p.is_file():
            raise ValueError('目标路径异常：' + str(p))
    records = {str(src): original_records(src) for item in items for _, src in item['sources']}
    args.work.mkdir(parents=True, exist_ok=True)
    backup = args.work / 'backup'
    backup.mkdir(exist_ok=False)
    for p in originals:
        target = backup / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        assert sha(p) == sha(target)
    untouched = {str(p): sha(p) for p in BASE.rglob('*') if p.is_file() and p not in originals}
    outputs = []
    for item in items:
        stage = item['stage']
        doc = minimal_document(stage, '版本记录')
        for label, source in item['sources']:
            if len(item['sources']) > 1:
                doc.add_paragraph(label, 'Heading 1')
            values = records[str(source)]
            table(doc, values[0], values[1:], [1.4, 2.7, 2.3, 2.0, 9.59], 11)
        doc.save(item['record'])
        copied = [[[c.text for c in r.cells] for r in t.rows] for t in Document(item['record']).tables]
        assert copied == [records[str(src)] for _, src in item['sources']]
        doc = minimal_document(stage, 'AI使用声明')
        for heading, text in CONTENT[stage]:
            if heading:
                doc.add_paragraph(heading, 'Heading 1')
            doc.add_paragraph(text)
        doc.save(item['ai'])
        text = '\n'.join(p.text for p in Document(item['ai']).paragraphs)
        assert not any(s in text for s in ['图片', '绘图', '图稿', '手工', '提示词', '审核人', '审核员', '签名', '待填写', '___'])
        outputs.extend([item['record'], item['ai']])
    assert all(sha(Path(p)) == value for p, value in untouched.items())
    (args.work / 'preserved-files.json').write_text(json.dumps(untouched, ensure_ascii=False, indent=2), encoding='utf-8')
    print('BACKUP ' + str(backup), flush=True)
    print('VERSION_RECORDS_EXACT_COPY', [len(records[str(src)]) - 1 for item in items for _, src in item['sources']], flush=True)
    spec = importlib.util.spec_from_file_location('native_renderer', ROOT / 'scripts/render_word_native.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.SKILL = SKILL
    results = []
    for idx, path in enumerate(outputs, 1):
        result = renderer.render(path, args.work / f'doc-{idx}', args.work / 'temp')
        result['source'] = str(path)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    (args.work / 'render-manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
