"""从共同模型生成同版 TikZ 与 PlantUML，编译产物由命令行另行保存。"""
import argparse
import json
from pathlib import Path


def tex(text):
    mapping = {"\\": r"\textbackslash{}", "_": r"\_", "&": r"\&", "%": r"\%", "#": r"\#"}
    return "".join(mapping.get(c, c) for c in text)


def point(p):
    return "(" + ",".join(f"{v:.3f}" for v in p) + ")"


def normal(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = (dx * dx + dy * dy) ** .5
    return dx / length, dy / length


def export_tikz(data, folder):
    lines = [r"\documentclass[border=6mm]{standalone}",
             r"\usepackage{fontspec}", r"\setmainfont{Microsoft YaHei}",
             r"\usepackage{tikz}", r"\usetikzlibrary{calc}",
             r'\XeTeXlinebreaklocale "zh"', r"\XeTeXlinebreakskip=0pt plus 1pt",
             r"\begin{document}",
             r"\begin{tikzpicture}[x=1cm,y=1cm,font=\fontsize{9.4}{12}\selectfont]",
             r"\node[font=\fontsize{15}{18}\selectfont\bfseries] at (7,3.45) {MB01 核心业务类图};"]
    # 先画关系，交叉处留白区分，无节点连接点。
    overrides = {"R04": (3.7, -6.55), "R06": (5.6, -6.70),
                 "R13": (17.8, -10.27), "R24": (12.2, -5.94),
                 "R26": (10.6, -10.96), "R22": (5.3, -19.32),
                 "R20": (12.2, -18.65), "R25": (11, 2.55)}
    label_lines=[]
    for relation in data["relations"]:
        pts = relation["points"]
        path = " -- ".join(point(p) for p in pts)
        lines.append(r"\draw[line width=.55pt,preaction={draw=white,line width=2.2pt}] " + path + ";")
        if relation["kind"] in ("composition", "aggregation"):
            p = pts[0]
            dx, dy = normal(pts[0], pts[1])
            nx, ny = -dy, dx
            diamond = [p, [p[0]+dx*.16+nx*.10, p[1]+dy*.16+ny*.10],
                       [p[0]+dx*.32, p[1]+dy*.32],
                       [p[0]+dx*.16-nx*.10, p[1]+dy*.16-ny*.10]]
            fill = "black" if relation["kind"] == "composition" else "white"
            lines.append(r"\draw[fill=" + fill + ",line width=.55pt] " +
                         " -- ".join(point(p) for p in diamond) + " -- cycle;")
        for start, end, label in [(pts[0], pts[1], relation["ma"]),
                                  (pts[-1], pts[-2], relation["mb"])]:
            dx, dy = normal(start, end)
            if abs(dx) > .5:
                pos = [start[0]+dx*.25, start[1]+.21]
                anchor = "south"
            else:
                pos = [start[0]+.15, start[1]+dy*.24]
                anchor = "west"
            label_lines.append(r"\node[fill=white,inner sep=.3pt,anchor=" + anchor +
                         r",font=\fontsize{7.5}{8.5}\selectfont] at " + point(pos) +
                         " {" + label + "};")
        longest = max(zip(pts, pts[1:]), key=lambda ab: abs(ab[0][0]-ab[1][0])+abs(ab[0][1]-ab[1][1]))
        a, b = longest
        dx, dy = normal(a, b)
        mid = [(a[0]+b[0])/2, (a[1]+b[1])/2]
        show_name=len(pts)==2 and not (abs(dx)>.5 and len(relation["label"])>2)
        label = relation["id"] + (" " + relation["label"] if show_name else "")
        anchor = "east" if abs(dy) > .5 else "north"
        pos = [mid[0]-.16, mid[1]] if abs(dy) > .5 else [mid[0], mid[1]-.16]
        if relation["id"] in overrides:
            pos, anchor = overrides[relation["id"]], "center"
        label_lines.append(r"\node[fill=white,inner sep=.6pt,anchor=" + anchor +
                     r",font=\fontsize{7.3}{8}\selectfont] at " + point(pos) +
                     " {" + tex(label) + "};")
    # 文字晚于所有连线绘制，避免交叉线的留白覆盖标注。
    lines.extend(label_lines)
    for obj in data["classes"]:
        x, y = obj["x"], obj["y"]
        left, right = x-2.8, x+2.8
        top, bottom = y+1.4, y-1.4
        lines += [r"\fill[white] " + point([left,bottom]) + " rectangle " + point([right,top]) + ";",
                  r"\draw[line width=.7pt] " + point([left,bottom]) + " rectangle " + point([right,top]) + ";"]
        for separator in (y+.35, y-.75):
            lines.append(r"\draw[line width=.45pt] " + point([left,separator]) + " -- " + point([right,separator]) + ";")
        lines += [r"\node[anchor=north,font=\fontsize{10.1}{12}\selectfont\bfseries] at " + point([x,top-.10]) + " {"+tex(obj["name"])+"};",
                  r"\node[anchor=north,font=\fontsize{8.1}{10}\selectfont] at " + point([x,top-.52]) + " {"+obj["key"]+"};"]
        for n, attribute in enumerate(obj["diagramAttributes"]):
            lines.append(r"\node[anchor=west,inner sep=0pt] at " + point([left+.16,y+.02-n*.43]) + " {- "+tex(attribute)+"};")
        lines.append(r"\node[anchor=west,inner sep=0pt,font=\fontsize{8.8}{11}\selectfont] at " +
                     point([left+.16,y-1.08]) + " {+ "+tex(obj["diagramOperation"])+"};")
    lines += [r"\node[anchor=north west,align=left,font=\fontsize{8.6}{11}\selectfont] at (-4.4,-28.2) {普通关联：实线\quad 组合：实心菱形\quad 聚合：空心菱形\\R01--R27 对应关系说明；资源池为辅助类。已受理任务恰有一份配置快照。};",
              r"\end{tikzpicture}",r"\end{document}"]
    (folder / "MB01_核心业务类图.tex").write_text("\n".join(lines)+"\n",encoding="utf-8")


def export_plantuml(data, folder):
    lines = ["@startuml MB01", "skinparam monochrome true", "skinparam shadowing false",
             "skinparam classAttributeIconSize 0", "hide circle", "title MB01 核心业务类图"]
    for obj in data["classes"]:
        lines += [f'class "{obj["name"]}\\n{obj["key"]}" as {obj["key"]} {{',
                  *["  - "+a for a in obj["diagramAttributes"]],
                  "  + "+obj["diagramOperation"],"}"]
    symbols = {"association":"--", "composition":"*--", "aggregation":"o--"}
    for r in data["relations"]:
        lines.append(f'{r["a"]} "{r["ma"]}" {symbols[r["kind"]]} "{r["mb"]}" {r["b"]} : {r["id"]} {r["label"]}')
    lines += ["note bottom of TrainingTask : 已受理时配置快照数量为 1", "note bottom of ResourceAllocation : 执行所有者与推理服务所有者恰选其一", "@enduml"]
    (folder / "MB01_核心业务类图.puml").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=Path(__file__).with_name("core_model.json"))
    args=parser.parse_args()
    data=json.loads(args.source.read_text(encoding="utf-8"))
    export_tikz(data,args.source.parent)
    export_plantuml(data,args.source.parent)
    print(json.dumps({"classes":len(data["classes"]),"relations":len(data["relations"]),"source":str(args.source)},ensure_ascii=False))
