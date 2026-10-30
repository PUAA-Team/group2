"""整理通过核对的活动图、独立源码与文字阅读版，不覆盖已有样图。"""
import argparse
import json
from pathlib import Path
import shutil
from build_activity_diagrams import ASSETS, load_flows


def package(work):
    source=work/'figures-final';fix=work/'figures-return-fix';detail=work/'figures-detail-fix'
    target=work/'figures-delivery';target.mkdir(exist_ok=False)
    selected={}
    for directory in [source,fix,detail]:
        for pdf in directory.glob('UC-*.pdf'):selected[pdf.stem]=directory
    records={}
    for directory in [source,fix,detail]:
        for record in json.loads((directory/'validation.json').read_text(encoding='utf-8')):
            records[record['id']]=record
    for identifier,directory in selected.items():
        for suffix in ['.tex','.pdf','.png','.log']:
            shutil.copy2(directory/(identifier+suffix),target/(identifier+suffix))
    shutil.copy2(source/'flows-normalized.json',target/'flows-normalized.json')
    (target/'validation.json').write_text(json.dumps(list(records.values()),ensure_ascii=False,indent=2),encoding='utf-8')
    # 已确认样图原样复用。
    for suffix in ['.pdf','.png']:
        shutil.copy2(ASSETS/'图片'/('UC-TRN-06'+suffix),target/('UC-TRN-06'+suffix))
    shutil.copy2(ASSETS/'源码/UC-TRN-06.tex',target/'UC-TRN-06.tex')
    for graph in load_flows():
        identifier=graph['id']
        tex=ASSETS/'源码'/(identifier+'.tex')
        if tex.exists():raise ValueError(f'正式源码已存在：{tex}')
        shutil.copy2(target/(identifier+'.tex'),tex)
        for suffix in ['.pdf','.png']:
            path=ASSETS/'图片'/(identifier+suffix)
            if path.exists():raise ValueError(f'正式图片已存在：{path}')
            shutil.copy2(target/(identifier+suffix),path)
        actions=[n['text'].replace('\n','，') for n in graph['nodes'] if n['kind']=='action']
        guards=list(dict.fromkeys(e['guard'] for e in graph['edges'] if e.get('guard')))
        body=f'# {identifier} {graph["title"]}\n\n![{graph["title"]}活动图](./{identifier}.png)\n\n'
        body+='参与者：'+graph['actor']+'。平台系统负责系统泳道中的处理。\n\n'
        body+='## 动作\n\n'+''.join('- '+action+'。\n' for action in actions)
        body+='\n## 分支条件\n\n'+('、'.join(guards))+'。\n\n'
        body+=f'[TikZ 源码](../源码/{identifier}.tex) · [矢量 PDF](./{identifier}.pdf) · [目录](../ReadMe.md)\n'
        (ASSETS/'图片'/(identifier+'.md')).write_text(body,encoding='utf-8')
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args();print(package(args.work))
