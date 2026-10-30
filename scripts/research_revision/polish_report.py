"""对新增图表分页及报告内优先级做局部整理。"""
import argparse
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt
from PIL import Image


def polish(doc):
    in_validation = False
    for p in doc.paragraphs:
        if p.text == '6.3 完整业务流程原型验证':
            in_validation = True
        elif p.text == '7 需求点与可借鉴创新点':
            in_validation = False
        if p.style.name == 'Normal' and len(p.text) > 70:
            visible = [r for r in p.runs if r.text.strip()]
            if visible and all(r.bold for r in visible):
                for run in visible:
                    run.bold = False
            if in_validation or p.text.startswith(('背景资料研读覆盖', '调研工作于2026')):
                p.paragraph_format.first_line_indent = Pt(24)
        if p.text == '表6-1　GPU接入与计算执行检查结果':
            p.paragraph_format.page_break_before = True
            p.paragraph_format.keep_with_next = True
        if p.text.startswith('图6-11　'):
            drawing = p._p.getprevious()
            rid = drawing.xpath('.//a:blip/@r:embed')[0]
            w, h = Image.open(BytesIO(doc.part.related_parts[rid].blob)).size
            cy = int(Cm(15.5 * h * .8 / w))
            for extent in drawing.xpath('.//wp:extent | .//a:xfrm/a:ext'):
                extent.set('cy', str(cy))
            fill = drawing.xpath('.//pic:blipFill')[0]
            rects = fill.xpath('./a:srcRect')
            rect = rects[0] if rects else OxmlElement('a:srcRect')
            rect.set('b', '20000')
            if not rects:
                fill.insert(1, rect)
        replacement = None
        if p.text.startswith('（6）断点续训按'):
            replacement = '（6）检查点恢复。平台提供检查点目录与保存频率的模板约定，保留模型、数据、优化器和训练步数信息。用户选择完整检查点，校验基础模型、数据版本、训练方法和参数兼容性后创建新的恢复任务，并保留来源与恢复记录。功能列为P1；失联执行先核查，确认原进程结束后再恢复。'
        elif p.text.startswith('（7）多模型评测与对比。'):
            replacement = '（7）模型评测与同条件比较。基础范围保留评测报告及模型、测试数据和指标定义的绑定。P1增加项目内多任务对比、基线阈值检查和样本结果比较；只有测试条件一致的报告参与直接比较，条件不同时明确列出差异。'
        elif p.text.startswith('（8）训练完成/失败通知。'):
            replacement = '（8）训练完成与失败通知。任务结果先生成站内通知，保留事件标识和任务关联，并按事件去重；邮件等外部通知作为P1扩展。发送失败单独记录，不影响训练结果。'
        elif p.text.startswith('（10）模型与数据集下载通道。'):
            replacement = '（10）模型与数据集下载通道。参考Crater，支持从HuggingFace、ModelScope登记下载来源，按仓库与版本复用公共资源，并设置并发、白名单和额度。该能力列为P1；基础版本可由管理员预先登记完整模型和数据，后续接入下载任务及完整性校验。'
        elif p.text.startswith('以下创新点均来自平台调研的成熟做法与问卷证据'):
            replacement = '结合平台调研与问卷结果，提出资源协作、智能辅助、训练可视化与结果复用等改进方向，按业务价值、实现条件及依赖关系安排实施顺序。'
        if replacement:
            p.text = replacement
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if '4060×4' in cell.text:
                    cell.text = '笔记本GPU\nRTX 4060、RTX 4070'
                if '训练完成/失败站内信+邮件通知' in cell.text:
                    cell.text = cell.text.replace('训练完成/失败站内信+邮件通知', '训练完成/失败站内通知；邮件通知作为增强项')
                if '不可变配置快照、克隆重跑' in cell.text and '提交前配置摘要与缺项校验' not in cell.text:
                    cell.text = cell.text.replace('不可变配置快照、克隆重跑', '提交前配置摘要与缺项校验、不可变配置快照、克隆重跑')
                if cell.text.startswith('训练可视化'):
                    cell.text = cell.text.replace('配置摘要与缺项清单、', '')
                if cell.text.startswith('作业状态机含排队、准入前'):
                    cell.text = '主状态统一为草稿、提交中、排队中、运行中、停止中、成功、失败、已取消和已停止；准备与上传等执行阶段、资源清理状态分别记录'
        # 同一优先级连续排列，便于直接用于后续范围确认。
        rows = list(table.rows)
        if any('不可变配置快照' in r.cells[1].text for r in rows if len(r.cells) > 1):
            for label in ('一期必做', '增强项', '后置/演进'):
                for row in rows[1:]:
                    if row.cells[0].text == label:
                        table._tbl.append(row._tr)
    return doc


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    polish(Document(args.source)).save(args.output)
