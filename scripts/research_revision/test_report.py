"""核对修订范围、原始统计、图片与真实验证记录。"""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from docx import Document

ROOT = Path(__file__).resolve().parents[2] / 'docs/需求调研+需求建模/初步提交材料'
OLD = ROOT / '需求调研报告_修订版_20261019.docx'
NEW = ROOT / '需求调研报告_完整修订版_20261020.docx'
SUPPORT = ROOT / '支撑材料/原型验证_20261020'


def appendix(doc):
    body = list(doc.element.body)
    start = next(p for p in doc.paragraphs if p.style.name == 'Heading 1' and p.text.startswith('附录A'))
    end = next(p for p in doc.paragraphs if p.text == '资料来源')
    return [text for element in body[body.index(start._p):body.index(end._p)]
            for text in element.xpath('.//w:t/text()')]


def check(name, passed):
    if not passed:
        raise AssertionError(name)
    print('PASS', name)


old, new = Document(OLD), Document(NEW)
# Word 原生保存会拆分文字运行；按段落还原后再检查正文。
text = '\n'.join(''.join(p.xpath('.//w:t/text()'))
                 for p in new.element.body.xpath('.//w:p'))
check('原始67份问卷统计保持一致', appendix(old) == appendix(new))
check('完整流程与接入章节齐全', all(s in text for s in ['6.3 完整业务流程原型验证', '6.4 GPU接入与计算执行可行性验证', '6.4.5 可行性判断与接入方案']))
check('21张流程与接入图有图题', all(f'图6-{i}　' in text for i in range(1, 22)))
check('清除课程及制作口径', not any(s in text for s in ['课程要求', '老师要求', '任务书', '前端演示', '只观察了第一步', '2026-10-19统一约定']))
check('数据概况结果未冒充训练准确率', '该任务用于验证调度与结果交接' in text and '本轮接入复核未加载Qwen权重' in text)
check('资源数量与通知优先级一致', '4060×4' not in text and '训练完成/失败站内信+邮件通知' not in text)
evidence = json.loads((SUPPORT / 'GPU接入验证记录.json').read_text(encoding='utf-8'))
check('15项真实接口与节点检查通过', len(evidence['checks']) == 15 and all(c['passed'] for c in evidence['checks']))
preparation = json.loads((SUPPORT / '运行环境与原包校验.json').read_text(encoding='utf-8'))
check('同学原ZIP未改动', preparation['source_sha256'] == hashlib.sha256((ROOT / '支撑材料/worker_agent.zip').read_bytes()).hexdigest())
check('原图与新增截图独立保存', len(list((SUPPORT / '图片').glob('F6-*.jpg'))) == 16 and len(list((SUPPORT / '图片').glob('W*.png'))) == 6)
with ZipFile(OLD) as before, ZipFile(NEW) as after:
    hashes = lambda z: {hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
    check('原平台与原型图片内容保留', hashes(before).issubset(hashes(after)))
print('ALL 10 CHECKS PASSED')
