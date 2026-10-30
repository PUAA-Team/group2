"""复用 documents 的 PNG 渲染器，在 Windows 上由 Word 提供只读 PDF。"""
import argparse
from functools import partial
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

SKILL = Path('C:/Users/lixu/.codex/plugins/cache/openai-primary-runtime/documents/26.1011.11113/skills/documents')
POPPLER = 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'
POWERSHELL = 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'


def render(source, output, work, pdf=None):
    if output.exists():
        raise ValueError(f'预览目录已存在：{output}')
    work.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(work.resolve())
    spec = importlib.util.spec_from_file_location('document_renderer', SKILL / 'render_docx.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.convert_from_path = partial(renderer.convert_from_path, poppler_path=POPPLER)

    def native_pdf(input_path, user_profile, convert_tmp_dir, stem, verbose=False):
        if pdf is not None:
            return str(pdf.resolve()), '使用本轮 Word 导出的同版本 PDF'
        target = Path(convert_tmp_dir) / f'{stem}.pdf'
        helper = Path(__file__).with_name('finalize_word_report.ps1').resolve()
        safe_helper = str(helper).replace("'", "''")
        safe_source = str(Path(input_path).resolve()).replace("'", "''")
        safe_target = str(target).replace("'", "''")
        command = ("$ProgressPreference='SilentlyContinue'; "
                   f"& ([ScriptBlock]::Create([IO.File]::ReadAllText('{safe_helper}', [Text.Encoding]::UTF8))) "
                   f"-Source '{safe_source}' -OutputPdf '{safe_target}'")
        import base64
        encoded = base64.b64encode(command.encode('utf-16le')).decode('ascii')
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                                capture_output=True, encoding='utf-8', errors='replace', check=True)
        return str(target), result.stdout

    # 仅替换 PDF 转换步骤，沿用技能的栅格化、页码命名和临时目录清理。
    renderer.convert_to_pdf = native_pdf
    paths = renderer.rasterize(str(source), str(output), dpi=140, verbose=False, emit_pdf=True)
    return {'pages': len(paths), 'output': str(output), 'renderer': 'Word COM + documents.render_docx.rasterize'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--pdf', type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.source, args.output, args.work, args.pdf), ensure_ascii=False))
