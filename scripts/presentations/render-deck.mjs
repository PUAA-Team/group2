import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

async function main() {
  const [input, output, selection] = process.argv.slice(2);
  if (!input || !output) throw new Error('用法：node render-deck.mjs 输入.pptx 输出目录 [1,2,3]');
  const { PresentationFile, FileBlob } = await import(pathToFileURL('C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs').href);
  const p = await PresentationFile.importPptx(await FileBlob.load(input));
  await fs.mkdir(output, { recursive: true });
  const indices = selection ? selection.split(',').map(n => Number(n) - 1) : p.slides.items.map((_, i) => i);
  for (const i of indices) {
    const blob = await p.export({ slide: p.slides.items[i], format: 'png', scale: 1 });
    await fs.writeFile(path.join(output, `${String(i + 1).padStart(2, '0')}.png`), new Uint8Array(await blob.arrayBuffer()));
    console.log(`RENDER ${i + 1}`);
  }
}
main().catch(error => { console.error(String(error.stack).slice(0, 1800)); process.exitCode = 1; });
