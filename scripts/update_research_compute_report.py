"""局部补充需求调研报告的算力章节，保留其余正文、图表与模板。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


BLOCKS = [
    ('h2', '5.6 算力资源可行性分析'),
    ('p', '项目组拟采用自有算力与外部平台相结合的资源方案。现有CPU和笔记本GPU承担开发、小规模实验和重复测试，实验室GPU服务器与云端资源作为可扩展的执行环境。系统通过统一计算接口管理不同来源的节点与作业，用户按任务提出资源需求，后台完成权限检查、能力匹配和运行安排。已有真实训练Demo为模型与框架适配提供了实践基础，多来源资源的统一接入仍需在后续实现中验证。'),
    ('h3', '5.6.1 可使用的资源及适用任务'),
    ('p', '小组内已确认4张RTX 4060笔记本GPU和1张RTX 4070笔记本GPU，共5张GPU；同时可利用成员电脑及服务器的CPU资源。NVIDIA公布的这两种笔记本GPU标准显存配置均为8 GB，实际可用显存还受系统占用、驱动和运行环境影响，接入时应逐设备探测[6]。GPU数量用于说明可组织多个独立实验的资源基础，单个任务的显存上限按所分配的设备判断。'),
    ('caption', '表5-4　计算资源与接入路线'),
    ('table', [
        ['资源来源', '适用工作', '接入方式与主要条件'],
        ['CPU资源', '数据预处理、轻量分类训练、单元测试和小规模推理', '部署统一Worker，登记核心数、内存与运行时；按任务模板匹配CPU执行'],
        ['笔记本GPU\n4060×4、4070×1', '小型视觉模型训练、小参数量语言模型微调及重复实验', '部署GPU Worker，探测设备和可用显存；控制并发、温度、供电与在线时段'],
        ['实验室GPU服务器', '扩展训练容量，承接较长训练或更高显存需求', '在获授权的环境中部署同一Worker，纳入资源组与队列'],
        ['AutoDL', '按需租用GPU实例，补充本地不足的卡型和显存', '通过SSH进入实例部署Worker；实例计费与启停由管理员控制'],
        ['Lightning AI', '云端开发、训练与协作实验', '在Studio终端或SSH环境部署Worker；核对GPU额度、休眠及存储条件'],
        ['腾讯Cloud Studio', '浏览器内开发与GPU工作空间实验', '优先人工启动工作空间并在终端运行Worker；API权限按空间类型核对'],
        ['Modal', '按需启动的云端GPU任务', '通过Python SDK适配器提交远程函数，保存外部调用标识并回收结果'],
    ]),
    ('p', 'CPU适合对数据处理、任务执行、日志和产物流程进行低成本验证。笔记本GPU可用于小型视觉任务，以及Qwen等小参数量语言模型的参数高效微调。模型能否运行需要综合检查权重精度、训练方式、批量大小、序列长度、优化器状态与激活占用；LoRA或量化训练也应经过显存估算与小样本试跑。实验室和云端资源用于补足容量，任务目录同时保留文本与视觉两类任务。'),
    ('p', '笔记本属于非连续在线资源，应提供可用时段、暂停接单和维护状态，避免睡眠、断网或成员日常使用造成冲突。多台笔记本优先执行相互独立的任务，多机协同训练留到网络、框架和通信条件验证后扩展。统一接入方案应支持资源数量变化，使设备增减不影响训练任务的业务描述。'),
    ('h3', '5.6.2 平台接入方式'),
    ('p', '接入方式分为驻留Worker与平台API适配两类。能够运行自有程序的CPU主机、笔记本GPU、实验室服务器和云端实例使用同一Worker程序，完成注册、心跳、任务领取、执行与结果回传。平台差异主要落在安装权限、运行环境、网络访问和生命周期上，资源来源作为管理信息保留。'),
    ('p', 'AutoDL提供实例SSH登录，适合在实例内安装Worker，并通过守护进程维持运行[9]。Lightning AI支持Studio终端、SSH和脚本自动化，可采用相同路线[8]。这两类资源接入前仍需核对实例可用时段、持久存储、外网访问与账户额度。训练进程退出与云实例停止分别管理，任务完成后按管理员策略检查计费实例，避免空闲实例继续消耗预算。'),
    ('p', '腾讯Cloud Studio优先采用人工创建并启动GPU工作空间、在浏览器终端运行Worker的方式。其官方API提供工作空间管理能力，同时说明免费高性能空间的API调用受限；自动创建和启停必须结合账户及空间类型评估[10]。工作空间应具备运行Worker和主动访问控制服务的条件，关闭页面、休眠及空间回收等行为需要通过接入试验核实。'),
    ('p', 'Modal采用平台API适配器。其Python SDK可通过Function.spawn()异步提交函数调用，保存FunctionCall标识，随后获取结果、读取日志并取消调用[7]。适配器把统一任务描述转换为Modal函数、镜像、GPU规格、超时和存储配置，再将返回信息转换为平台的状态、日志与产物记录。API返回结果前的等待状态应如实展示；平台未提供或未采集的指标保留为缺失。ModelArts、PAI等平台后续可按照相同的接口边界增加适配。'),
    ('h3', '5.6.3 统一计算接口与资源抽象'),
    ('p', '系统划分控制平面与计算平面。控制平面负责身份与权限、数据及模型版本、训练任务、调度、监控索引和审计，初期可采用模块化单体；计算平面负责实际训练与推理。两者通过统一计算接口衔接，下面分别连接Worker适配器与平台API适配器。训练框架适配与资源来源适配保持独立：同一PyTorch训练模板可在满足条件的本地或云端环境执行，换用MindSpore时则通过相应训练模板和运行时处理。'),
    ('p', '统一接口至少覆盖能力查询、任务提交、状态查询、取消或停止、日志与指标读取，以及产物清单获取。各适配器声明支持的操作、设备类型、运行时和监控能力，保留外部作业编号和原始错误码。云端作业标识与本平台任务编号关联保存；重跑建立新任务并记录来源，保持已有任务及配置快照不变。'),
    ('p', '任务描述包括模型和数据版本、训练模板与运行环境版本、训练方式、超参数、资源需求、输出位置、时限和预算。资源需求表达设备类型、GPU数量、最低显存、CPU、内存及运行时要求。资源目录保存节点编号、来源、资源组、设备UUID与本机序号、软硬件版本、可用时段、健康和占用状态。用户可采用自动推荐或手动指定授权资源；界面展示规格、限制和成本信息，供提交前确认。'),
    ('p', '调度先检查权限、允许任务类型、设备和运行时兼容性、显存与配额，再按队列优先级及稳定的入队顺序安排合法任务。资源选择可优先使用满足条件的自有资源，在不足时展示经授权的云端候选。GPU分配与配额预留需要原子化或等效互斥机制，派发失败执行补偿；同一设备的实际占用与平台记录定期核对。云端按需容量同时受供应商配额、区域可用性和预算约束。'),
    ('h3', '5.6.4 节点接入与运行流程'),
    ('p', '管理员先为节点指定资源组、允许任务类型和接入范围，生成短期有效、一次性使用的注册凭证。节点所有者下载经过签名或校验和验证的Worker安装包，确认平台地址和权限后启动。管理页面可提供复制启动命令的入口；接入令牌通过受控输入或受限文件交付，避免进入共享命令记录、截图和日志。'),
    ('p', 'Worker在本机探测CPU、内存、GPU型号、数量、设备UUID、显存、驱动、CUDA及训练框架版本，并主动向控制平面发起HTTPS连接。注册信息进入待确认状态，经管理员核对后取得独立、可撤销的节点凭证，完成运行时检查后才进入可调度状态。主动连接方式适用于位于局域网中的笔记本和实验室节点，通常无需在节点开放公网SSH或配置入站端口映射。'),
    ('p', '节点按可配置周期发送心跳和资源摘要，并领取调度器已分配的任务。每次领取携带任务编号、执行标识和有效租约，启动前复核设备、授权、配额及快照。控制端与Worker均需识别重复派发，避免网络重试造成重复训练。训练过程中，Worker回传状态事件、指标和带序号的日志；连接恢复后从已确认位置续传。'),
    ('p', '训练结束后上传产物清单、校验和及结束事件，平台核对执行退出、产物完整性和资源清理结果，再登记模型版本并确认释放。节点心跳超时先暂停派发并触发状态核对；原执行尚未确认结束时保留占用记录，防止重复分配。取消、停止及终态回传均需幂等处理。平台API作业遵循同样的核对过程，将供应商侧执行状态和取消结果映射到本平台记录。'),
    ('h3', '5.6.5 安全与数据管理'),
    ('p', '控制服务与Worker之间采用HTTPS，校验证书和目标地址；长连接按需使用WSS。注册凭证与节点凭证分开管理，节点凭证具备独立身份、有效期、轮换和撤销机制，只允许访问本节点的授权任务。云平台密钥由服务端以受控秘密存储或加密方式保存，限制调用权限，避免进入浏览器、任务明文、镜像和训练日志[11][12]。'),
    ('p', '任务提交与执行前均检查用户、工作空间、资源组、用户组及个人授权，落实GPU范围、任务类型、并发和存储配额。任务执行使用经过审核的模板及参数，文件路径和挂载范围由平台约束。多用户共享环境采用非特权容器或其他具备实际隔离能力的执行环境，限制CPU、内存、GPU与网络访问；数据输入只读，任务输出目录独立。无容器的本地开发环境仅运行受信任模板，并限制到专用工作目录。'),
    ('p', '数据、模型权重和产物由统一文件或对象存储管理，执行节点仅保存必要缓存。跨节点访问通过版本标识、内容校验和与短期授权地址完成，数据库保存元数据和引用关系。大文件采用分片、续传及缓存校验，节点退出后仍能从统一存储取得已归档结果。CPU和单GPU验证可先采用本地或共享文件存储，多节点及云端接入逐步使用统一对象存储。'),
    ('p', '个人设备和外部云节点能够接触任务输入，资源分组必须同时考虑数据敏感级别与运行环境可信程度。公开或脱敏数据可用于个人和云端资源验证，敏感数据仅派发至获授权的受控环境，并遵守数据及模型许可证。注册、授权变更、任务派发、停止、凭证撤销与云端用量均保留审计记录；记录操作者、对象、时间和结果，同时对秘密字段脱敏。'),
    ('h3', '5.6.6 可行性判断与验证安排'),
    ('p', '现有CPU、5张笔记本GPU与已完成的真实训练Demo，为平台基础训练流程和多任务实验提供了实施起点。资源接入的主要工程问题集中在运行时兼容、节点在线稳定性、数据传输、可靠调度与安全隔离。首先将已有训练模板接入CPU及单个GPU Worker，验证注册、提交、指标、日志、模型产物和推理；随后加入其余笔记本及可接入的实验室服务器，再选择一种云端Worker环境和Modal适配器验证两类接入路线。'),
    ('p', '验证过程覆盖重复注册、重复派发、越权设备或任务类型、显存不足、断网及失联、任务停止、产物上传失败、凭证撤销和云预算耗尽等场景。分别检查页面反馈、控制端状态、真实执行和资源占用。云平台免费额度、试用资格、计费及库存以实际账户和最新官方政策为准，试验记录保存资源规格、运行时版本、数据规模、参数、耗时、峰值显存及异常情况。统一接入和跨平台调度在完成这些试验后再认定为可用能力。'),
]

REFERENCES = [
    '6. NVIDIA. Compare GeForce RTX Laptops（RTX 40系列笔记本GPU规格）。https://www.nvidia.com/en-us/geforce/laptops/compare/（访问日期：2026年10月13日）。',
    '7. Modal. Python SDK FunctionCall；Function invocation methods。https://modal.com/docs/sdk/py/latest/FunctionCall；https://modal.com/docs/guide/function-invocation-methods（访问日期：2026年10月13日）。',
    '8. Lightning AI. SSH access。https://api.lightning.ai/docs/platform/build/ai-studio/ssh-access（访问日期：2026年10月13日）。',
    '9. AutoDL. SSH远程连接。https://www.autodl.com/docs/ssh/（访问日期：2026年10月13日）。',
    '10. 腾讯云. Cloud Studio API简介；机时购买。https://cloud.tencent.com/document/product/1039/94098；https://cloud.tencent.com/document/product/1039/131894（访问日期：2026年10月13日）。',
    '11. OWASP. REST Security Cheat Sheet。https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html（访问日期：2026年10月13日）。',
    '12. OWASP. Secrets Management Cheat Sheet。https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html（访问日期：2026年10月13日）。',
]


def paragraph_before(doc, anchor, text, style, prototype=None):
    p = doc.add_paragraph(text, style=style)
    if prototype is not None and prototype._p.pPr is not None:
        p._p.insert(0, deepcopy(prototype._p.pPr))
        p.style = style
    anchor._p.addprevious(p._p)
    p.paragraph_format.keep_with_next = style.startswith('Heading')
    return p


def table_before(doc, anchor, rows):
    table = doc.add_table(rows=0, cols=3)
    table.autofit = False
    widths = [Cm(3.5), Cm(5.0), Cm(6.1)]
    for col, width in zip(table.columns, widths):
        col.width = width
    borders = OxmlElement('w:tblBorders')
    for edge in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        e = OxmlElement('w:' + edge)
        for key, value in {'val': 'single', 'sz': '4', 'color': 'D9D9D9'}.items():
            e.set(qn('w:' + key), value)
        borders.append(e)
    table._tbl.tblPr.append(borders)
    margins = OxmlElement('w:tblCellMar')
    for side, value in [('top', '90'), ('bottom', '90'), ('left', '90'), ('right', '90')]:
        e = OxmlElement('w:' + side)
        e.set(qn('w:w'), value)
        e.set(qn('w:type'), 'dxa')
        margins.append(e)
    table._tbl.tblPr.append(margins)
    for i, values in enumerate(rows):
        row = table.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        if i == 0:
            row._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        for cell, value, width in zip(row.cells, values, widths):
            cell.width = width
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.text = value
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.first_line_indent = Pt(0)
            for run in p.runs:
                run.font.size = Pt(10.5)
                run.bold = i == 0
            if i == 0:
                fill = OxmlElement('w:shd')
                fill.set(qn('w:fill'), 'E7E6E6')
                cell._tc.get_or_add_tcPr().append(fill)
    anchor._p.addprevious(table._tbl)
    return table


def supplement(source, output):
    if output.exists():
        raise ValueError(f'输出已存在：{output}')
    doc = Document(source)
    heading = next(p for p in doc.paragraphs if p.text == '5.6 技术调研结论')
    body = next(p for p in doc.paragraphs if p.text.startswith('本章对训练平台涉及的基础技术对象'))
    title = next(p for p in doc.paragraphs if p.text == '5 模型、训练框架与数据源技术调研')
    title.runs[-1].text = '模型、训练框架、数据与算力资源调研'
    body.runs[0].text = '本章对训练平台涉及的基础技术对象进行调查，重点说明模型、训练方法、训练框架、数据源与算力资源，以及它们之间的配合和接入条件。'
    heading.runs[0].text = '5.7 '
    for kind, content in BLOCKS:
        if kind == 'table':
            table_before(doc, heading, content)
        else:
            style = {'h2': 'Heading 2', 'h3': 'Heading 3'}.get(kind, 'Normal')
            p = paragraph_before(doc, heading, content, style, body if kind == 'p' else None)
            if kind == 'caption':
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.keep_with_next = True
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(6)
    conclusion = next(p for p in doc.paragraphs if p.text.startswith('调研表明，训练平台应将模型及其血缘'))
    paragraph_before(doc, next(p for p in doc.paragraphs if p.text == '6 用户问卷调查'),
                     '算力资源方面，项目拟将CPU、自有笔记本GPU、实验室服务器及云平台纳入统一计算接口，在保留各类资源能力和使用限制的基础上完成匹配、执行与结果归档。已有训练Demo作为基础验证，后续按Worker接入、平台API适配和安全验证分阶段实施。', 'Normal', body)
    for text in REFERENCES:
        p = doc.add_paragraph(text, style='Normal')
        p.paragraph_format.space_after = Pt(4)
    for row in doc.tables[2].rows:
        if row.cells[0].text == '模型、框架与数据源':
            row.cells[0].text = '模型、框架、数据源与算力资源'
            row.cells[2].text = '项目组技术调研、论文与官方文档研读、资源调查'
            row.cells[3].text = '聚焦模型训练适配和资源统一接入的可行性'
    history = doc.tables[1]
    row = next(r for r in history.rows[1:] if all(not c.text.strip() for c in r.cells))
    for cell, text in zip(row.cells, ['4', '20261013', '', '', '补充算力资源可行性分析，明确资源来源、统一接入、调度与安全方案。']):
        cell.text = text
    # 标题随首段分页，避免补充章节后出现新的孤立标题。
    for p in doc.paragraphs:
        if p.style.name.startswith('Heading'):
            p.paragraph_format.keep_with_next = True
    # 原稿两处孤立表题：连接标题、表题和表格首行。
    for prefix in ['4.2 ', '第13题']:
        p = next(p for p in doc.paragraphs if p.text.startswith(prefix))
        p.paragraph_format.keep_with_next = True
        element = p._p.getnext()
        while element.tag == qn('w:p'):
            element.get_or_add_pPr().append(OxmlElement('w:keepNext'))
            element = element.getnext()
        assert element.tag == qn('w:tbl')
        for p in element.find(qn('w:tr')).iter(qn('w:p')):
            p.get_or_add_pPr().append(OxmlElement('w:keepNext'))
    doc.save(output)
    with ZipFile(source) as old, ZipFile(output) as new:
        media = [n for n in old.namelist() if n.startswith('word/media/')]
        assert all(old.read(n) == new.read(n) for n in media), '原插图发生变化'
    return {'output': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'paragraphs': len(doc.paragraphs), 'tables': len(doc.tables), 'preserved_media': len(media),
            'original_training_conclusion_preserved': conclusion.text.startswith('调研表明')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(supplement(args.source, args.output), ensure_ascii=False))
