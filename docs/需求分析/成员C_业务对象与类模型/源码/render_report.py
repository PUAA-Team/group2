"""Word PDF 复用当前 documents 技能渲染，临时文件放 D 盘。"""
import argparse
from functools import partial
import importlib.util
from pathlib import Path
import tempfile

SKILL=Path("C:/Users/lixu/.codex/plugins/cache/openai-primary-runtime/documents/26.1017.11052/skills/documents")
POPPLER="C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin"


def render(source,pdf,output,work):
    if output.exists(): raise ValueError("预览目录已存在，请使用新目录")
    work.mkdir(parents=True,exist_ok=True)
    tempfile.tempdir=str(work.resolve())
    spec=importlib.util.spec_from_file_location("document_renderer",SKILL/"render_docx.py")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.convert_from_path=partial(module.convert_from_path,poppler_path=POPPLER)
    module.convert_to_pdf=lambda *a,**kw:(str(pdf.resolve()),"同版 Word 只读导出 PDF")
    paths=module.rasterize(str(source),str(output),dpi=140,verbose=False,emit_pdf=False)
    print("RENDERED",len(paths),output)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("source","pdf","output","work"): p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args(); render(a.source,a.pdf,a.output,a.work)
