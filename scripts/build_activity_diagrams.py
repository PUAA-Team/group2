"""由核对后的流程生成黑白 TikZ 图，编译后按实际节点尺寸规划正交连线。"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import heapq
import json
from pathlib import Path
import re
import shutil
import subprocess

from activity_flows_iam import FLOWS

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/需求调研+需求分析/初步提交材料/用例活动图'
XELATEX = Path('C:/Users/lixu/AppData/Local/Programs/MiKTeX/miktex/bin/x64/xelatex.exe')
POPPLER = Path('C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
COLS = [1.35, 5.175, 9.675]
STEP = 1.72
PT_CM = 2.54 / 72.27

PREAMBLE = r'''\documentclass[tikz,border=2mm]{standalone}
\usepackage{fontspec}
\IfFontExistsTF{Microsoft YaHei}{\setmainfont{Microsoft YaHei}\setsansfont{Microsoft YaHei}}{\setmainfont{Noto Sans CJK SC}\setsansfont{Noto Sans CJK SC}}
\XeTeXlinebreaklocale "zh"
\XeTeXlinebreakskip=0pt plus 1pt
\usetikzlibrary{arrows.meta,shapes.geometric,calc}
\begin{document}
\begin{tikzpicture}[x=1cm,y=1cm,font=\sffamily\fontsize{9.5}{12.5}\selectfont,
action/.style={draw=black,line width=.5pt,rounded corners=2mm,fill=white,align=center,text width=3.05cm,inner xsep=1.4mm,inner ysep=1.5mm,minimum height=.72cm},
decision/.style={diamond,draw=black,line width=.5pt,fill=white,aspect=2,align=center,inner sep=1mm,font=\sffamily\fontsize{9}{11}\selectfont},
initial/.style={circle,draw=black,fill=black,minimum size=3.2mm,inner sep=0pt},
merge/.style={diamond,draw=black,fill=white,minimum size=3mm,inner sep=0pt},
final/.style={circle,draw=black,fill=white,minimum size=5mm,inner sep=0pt,line width=.5pt},
flow/.style={-{Straight Barb[length=1.7mm,width=1.4mm]},draw=black,line width=.5pt},
guard/.style={fill=white,inner sep=.5mm,font=\sffamily\fontsize{8.5}{10}\selectfont}]
'''


def load_flows():
    data = deepcopy(FLOWS)
    for name in ['flows-trn-mon.json', 'flows-mdl-inf-adm.json']:
        data.extend(json.loads((ASSETS / '源码' / name).read_text(encoding='utf-8')))
    # 多条备选返回同一动作时先合并控制流，避免形成隐式同步。
    for graph in data:
        if graph['id']=='UC-TRN-01':
            # 多种校验错误可同时出现，统一收集后由用户修改并重新校验。
            removed={'invalid','incompatible','restricted','retryMerge'}
            graph['nodes']=[n for n in graph['nodes'] if n['key'] not in removed]
            graph['edges']=[e for e in graph['edges'] if e['from'] not in removed and e['to'] not in removed]
            graph['nodes'].append(dict(key='errors',kind='action',col=2,row=6,
                text='标记缺项及越界\n说明不兼容及限制\n保留值并给建议'))
            graph['edges'].extend([
                dict(**{'from':'result','to':'errors'},guard='未通过',from_port='east',to_port='west'),
                dict(**{'from':'errors','to':'editMerge'},from_port='south',to_port='east')])
        if graph['id'] in ['UC-INF-02','UC-ADM-04']:
            for node in graph['nodes']:
                if node['key'] in ['keep', 'cancelEnd']:
                    node['col'] = 2
        keys = {n['key']: n for n in graph['nodes']}
        incoming = Counter(e['to'] for e in graph['edges'])
        for key, count in incoming.items():
            if count > 1 and keys[key]['kind'] not in ['merge', 'final']:
                node = keys[key]
                merge_key = 'join_' + key
                old_row = node['row']
                for other in graph['nodes']:
                    if other['row'] >= old_row:
                        other['row'] += .65
                for edge in graph['edges']:
                    if edge['to'] == key:
                        edge['to'] = merge_key
                        edge.pop('to_port', None)
                        if keys[edge['from']]['row'] > old_row:
                            edge['to_port'] = 'east' if keys[edge['from']]['col'] >= node['col'] else 'west'
                graph['nodes'].append(dict(key=merge_key,kind='merge',col=node['col'],row=old_row,text=''))
                graph['edges'].append(dict(**{'from':merge_key,'to':key}))
        graph['nodes'].sort(key=lambda n:(n['row'],n['col']))
    return sorted(data, key=lambda g:g['id'])


def validate(graph):
    keys = {n['key']:n for n in graph['nodes']}
    if len(keys) != len(graph['nodes']):
        raise ValueError(f"节点标识重复：{graph['id']}")
    ins, outs = Counter(), Counter()
    for edge in graph['edges']:
        assert edge['from'] in keys and edge['to'] in keys, graph['id']
        ins[edge['to']] += 1
        outs[edge['from']] += 1
    for key, node in keys.items():
        kind = node['kind']
        if kind == 'initial': assert ins[key] == 0 and outs[key] == 1, (graph['id'], key)
        elif kind == 'final': assert ins[key] >= 1 and outs[key] == 0, (graph['id'], key)
        elif kind == 'merge': assert ins[key] >= 2 and outs[key] == 1, (graph['id'], key)
        elif kind == 'decision':
            assert ins[key] == 1 and outs[key] >= 2, (graph['id'],key)
            guards = [e.get('guard') for e in graph['edges'] if e['from'] == key]
            assert all(guards) and len(set(guards)) == len(guards), (graph['id'],key)
        else: assert ins[key] == 1 and outs[key] == 1, (graph['id'],key,ins[key],outs[key])


def tex_escape(text):
    replacements = {'\\':r'\textbackslash{}','&':r'\&','%':r'\%','#':r'\#','_':r'\_','{':r'\{','}':r'\}'}
    return ''.join(replacements.get(c,c) for c in text).replace('\n',r'\\')


def node_source(graph):
    bottom = 1.0 + max(n['row'] for n in graph['nodes']) * STEP + .65
    out = [PREAMBLE, f'\\draw[line width=.5pt] (0,0) rectangle (11.7,{-bottom:.4f});',
           f'\\draw[line width=.45pt] (2.7,0) -- (2.7,{-bottom:.4f});',
           r'\draw[line width=.45pt] (0,-.66) -- (11.7,-.66);',
           f'\\node[anchor=west,font=\\sffamily\\bfseries\\fontsize{{10}}{{12}}\\selectfont] at (0,.45) {{{graph["id"]}\\quad {tex_escape(graph["title"])}}};',
           f'\\node[font=\\sffamily\\bfseries] at (1.35,-.33) {{{tex_escape(graph["actor"])}}};',
           r'\node[font=\sffamily\bfseries] at (7.2,-.33) {平台系统};']
    for node in graph['nodes']:
        style = node['kind']
        if style == 'action' and node['col'] == 0:
            style += ',text width=2.25cm,inner xsep=1mm'
        x, y = COLS[node['col']], -(1 + node['row'] * STEP)
        out.append(f'\\node[{style}] ({node["key"]}) at ({x},{y:.5f}) {{{tex_escape(node["text"])}}};')
        if node['kind'] == 'final': out.append(f'\\fill[black] ({node["key"]}.center) circle (1.45mm);')
    return out, bottom


def diagnostics(graph):
    lines = []
    for node in graph['nodes']:
        key=node['key']
        for port in ['north','south','east','west']:
            lines.append(f'\\path let \\p1=({key}.{port}) in \\pgfextra{{\\typeout{{BBOX {key} {port} X=\\x1 Y=\\y1}}}};')
    return lines


def compile_tex(path, build):
    result = subprocess.run([str(XELATEX),'--disable-installer','-no-shell-escape','-interaction=nonstopmode',
                             '-halt-on-error',f'--output-directory={build}',str(path)],
                            capture_output=True,encoding='utf-8',errors='replace')
    if result.returncode:
        raise RuntimeError(f'{path.name} 编译失败\n{result.stdout[-2500:]}\n{result.stderr[-500:]}')
    log=(build/(path.stem+'.log')).read_text(encoding='utf-8',errors='replace')
    if 'Missing character:' in log or 'Overfull \\hbox' in log:
        raise RuntimeError(f'{path.name} 出现缺失字符或文字溢出，请查看日志。')
    return log


def boxes_from_log(log):
    ports = defaultdict(dict)
    for key,port,x,y in re.findall(r'BBOX (\w+) (\w+) X=([-0-9.]+)pt Y=([-0-9.]+)pt',log):
        ports[key][port] = (float(x)*PT_CM,-float(y)*PT_CM)
    boxes={key:(p['west'][0],p['north'][1],p['east'][0],p['south'][1]) for key,p in ports.items()}
    return ports, boxes


def crosses_box(a,b,box,padding=0):
    left,top,right,bottom=box
    left-=padding;right+=padding;top-=padding;bottom+=padding
    if abs(a[0]-b[0])<1e-6:
        return left+1e-6<a[0]<right-1e-6 and max(min(a[1],b[1]),top)<min(max(a[1],b[1]),bottom)-1e-6
    return top+1e-6<a[1]<bottom-1e-6 and max(min(a[0],b[0]),left)<min(max(a[0],b[0]),right)-1e-6


def simplify(points):
    out=[]
    for point in points:
        if out and abs(out[-1][0]-point[0])+abs(out[-1][1]-point[1])<1e-5: continue
        if len(out)>1 and ((abs(out[-2][0]-point[0])<1e-5 and abs(out[-1][0]-point[0])<1e-5) or
                          (abs(out[-2][1]-point[1])<1e-5 and abs(out[-1][1]-point[1])<1e-5)):
            out[-1]=point
        else: out.append(point)
    return out


def route(a,b,boxes,bottom,existing):
    # 正交可见网格避开所有动作框；实际端点来自第一遍 XeLaTeX 编译。
    xs={.16,2.85,3.15,7.25,7.6,7.9,11.54,a[0],b[0]}
    ys={.84,bottom-.16,a[1],b[1]}
    for left,top,right,low in boxes.values():
        xs.update([max(.16,left-.14),min(11.54,right+.14)])
        ys.update([max(.84,top-.14),min(bottom-.16,low+.14)])
    xs=sorted(xs);ys=sorted(ys)
    start=(xs.index(a[0]),ys.index(a[1]),-1)
    goal=(xs.index(b[0]),ys.index(b[1]))
    queue=[(0,0,start)];cost={start:0};previous={}
    while queue:
        _,distance,current=heapq.heappop(queue)
        if distance>cost[current]+1e-8:continue
        i,j,d=current
        if (i,j)==goal:
            chain=[]
            while current in previous:
                chain.append((xs[current[0]],ys[current[1]]));current=previous[current]
            return simplify([a]+list(reversed(chain)))
        p=(xs[i],ys[j])
        for ni,nj,nd in [(i-1,j,0),(i+1,j,0),(i,j-1,1),(i,j+1,1)]:
            if not (0<=ni<len(xs) and 0<=nj<len(ys)):continue
            q=(xs[ni],ys[nj])
            if any(crosses_box(p,q,box,.04) for box in boxes.values()):continue
            length=abs(p[0]-q[0])+abs(p[1]-q[1])
            # 轻微惩罚复用同一路段，减少连线叠在一起。
            overlap=sum(.35 for e,f in existing if ((abs(p[0]-q[0])<1e-6 and abs(e[0]-f[0])<1e-6 and abs(p[0]-e[0])<.06 and max(min(p[1],q[1]),min(e[1],f[1]))<min(max(p[1],q[1]),max(e[1],f[1]))) or
                (abs(p[1]-q[1])<1e-6 and abs(e[1]-f[1])<1e-6 and abs(p[1]-e[1])<.06 and max(min(p[0],q[0]),min(e[0],f[0]))<min(max(p[0],q[0]),max(e[0],f[0])))))
            new=distance+length+(.45 if d not in [-1,nd] else 0)+overlap
            state=(ni,nj,nd)
            if new<cost.get(state,float('inf')):
                cost[state]=new;previous[state]=current
                estimate=abs(q[0]-b[0])+abs(q[1]-b[1])
                heapq.heappush(queue,(new+estimate,new,state))
    raise ValueError(f'无法找到无穿框连线：{a} -> {b}')


def routes(graph,ports,boxes,bottom):
    result=[];existing=[];merge_ports=defaultdict(set)
    kinds={n['key']:n['kind'] for n in graph['nodes']}
    for edge in graph['edges']:
        source,target=edge['from'],edge['to']
        scx=(boxes[source][0]+boxes[source][2])/2;tcx=(boxes[target][0]+boxes[target][2])/2
        scy=(boxes[source][1]+boxes[source][3])/2;tcy=(boxes[target][1]+boxes[target][3])/2
        horizontal=abs(scy-tcy)<.15
        sp=edge.get('from_port') or ('east' if tcx>scx else 'west') if horizontal else edge.get('from_port') or ('south' if tcy>scy else 'north')
        tp=edge.get('to_port') or ('west' if tcx>scx else 'east') if horizontal else edge.get('to_port') or ('north' if tcy>scy else 'south')
        if kinds[target]=='merge':
            preferred=('east' if scx>tcx+.1 else 'west' if scx<tcx-.1 else 'north' if scy<tcy else 'east')
            tp=next(p for p in [preferred,'north','east','west','south'] if p not in merge_ports[target])
            merge_ports[target].add(tp)
        a,b=ports[source][sp],ports[target][tp]
        if sp=='west' and a[0]<.35:
            sp='north' if tcy<scy else 'south';a=ports[source][sp]
        if tp=='west' and b[0]<.35:
            tp='north' if tcy>scy else 'south';b=ports[target][tp]
        directions={'north':(0,-1),'south':(0,1),'west':(-1,0),'east':(1,0)}
        da,db=directions[sp],directions[tp]
        aa=(a[0]+da[0]*.18,a[1]+da[1]*.18);bb=(b[0]+db[0]*.18,b[1]+db[1]*.18)
        path=simplify([a]+route(aa,bb,boxes,bottom,existing)+[b])
        for p,q in zip(path,path[1:]):
            for key,box in boxes.items():
                if key not in [source,target] and crosses_box(p,q,box):
                    raise ValueError(f'{graph["id"]} 连线穿过节点 {key}')
        existing.extend(zip(path,path[1:]))
        result.append((edge,path))
    return result


def edge_source(edge,path):
    points=[f'({x:.5f},{-y:.5f})' for x,y in path]
    guard=''
    if edge.get('guard'):
        # 条件紧跟判定的出边；短首段时标到第二段。
        segment=0
        if len(path)>2 and abs(path[0][0]-path[1][0])+abs(path[0][1]-path[1][1])<.5:segment=1
        p,q=path[segment],path[segment+1]
        side='above' if abs(p[1]-q[1])<1e-5 else 'right'
        guard=f' node[guard,{side},pos=.5] {{[{tex_escape(edge["guard"])}]}}'
    pieces=[points[0]]
    for i,point in enumerate(points[1:]):
        pieces.append(' --'+(guard if guard and i==segment else '')+' '+point)
    return '\\draw[flow] '+''.join(pieces)+';'


def build(graph,build_dir):
    validate(graph)
    target=build_dir/(graph['id']+'.tex')
    # 文字实际高度决定间距。半行布局必要时下移，避免判定节点与终点挤在一起。
    for attempt in range(8):
        source,bottom=node_source(graph)
        target.write_text('\n'.join(source+diagnostics(graph)+[r'\end{tikzpicture}',r'\end{document}']),encoding='utf-8')
        ports,boxes=boxes_from_log(compile_tex(target,build_dir))
        adjusted=False
        for col in range(3):
            ordered=[n for n in graph['nodes'] if n['col']==col]
            for upper,lower in zip(ordered,ordered[1:]):
                gap=boxes[lower['key']][1]-boxes[upper['key']][3]
                if gap<.35:
                    cutoff=lower['row'];delta=(.35-gap)/STEP+.01
                    for node in graph['nodes']:
                        if node['row']>=cutoff:node['row']+=delta
                    adjusted=True
                    break
            if adjusted:break
        if not adjusted:break
    else:raise ValueError(f'{graph["id"]} 节点间距无法满足要求')
    planned=routes(graph,ports,boxes,bottom)
    body=source+[edge_source(edge,path) for edge,path in planned]+diagnostics(graph)+[r'\end{tikzpicture}',r'\end{document}']
    target.write_text('\n'.join(body)+'\n',encoding='utf-8')
    compile_tex(target,build_dir)
    subprocess.run([str(POPPLER),'-png','-r','300','-singlefile',str(target.with_suffix('.pdf')),str(target.with_suffix(''))],check=True,capture_output=True)
    return dict(id=graph['id'],title=graph['title'],nodes=len(boxes),edges=len(planned),height_cm=bottom,
                coverage=graph['coverage'],boxes=boxes,routes=[dict(edge=e,points=p) for e,p in planned])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',required=True,type=Path)
    parser.add_argument('--ids',nargs='*')
    args=parser.parse_args();args.build.mkdir(parents=True,exist_ok=True)
    flows=load_flows()
    selected=[g for g in flows if not args.ids or g['id'] in args.ids]
    results=[]
    for graph in selected:
        print('BUILD',graph['id'],flush=True)
        result=build(graph,args.build);results.append(result)
        print('OK',graph['id'],flush=True)
        (args.build/'validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.build/'flows-normalized.json').write_text(json.dumps(flows,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
