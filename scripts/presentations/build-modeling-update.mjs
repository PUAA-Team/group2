import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { slides, filename, preservedSlides } from './modeling-update-content.mjs';
import { cleanModelingBody, layoutModeling } from './modeling-update-layout.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const RUNTIME = 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const SKILL = 'C:/Users/lixu/.codex/plugins/cache/openai-primary-runtime/presentations/26.1011.11113/skills/presentations';
const workspaceDir = process.argv[2] || 'D:/model-training-demo/modeling-ppt-update-20261012';
const revision = process.argv[3] || 'v1';
process.env.RUNTIME_NODE_MODULES = `${RUNTIME}/node/node_modules`;

async function main() {
  if (!/^[A-Za-z0-9_-]+$/.test(revision)) throw new Error('版本名不合法');
  const privateDir = path.join(workspaceDir, `private-${revision}`), outputDir = path.join(workspaceDir, `output-${revision}`);
  await fs.mkdir(privateDir, { recursive: false }); await fs.mkdir(outputDir, { recursive: false });
  const source = process.argv[5] || path.join(workspaceDir, 'source.pptx');
  const { PresentationFile, FileBlob } = await import(pathToFileURL(`${RUNTIME}/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs`).href);
  const { finalizePresentation } = await import(pathToFileURL(`${SKILL}/container_tools/artifact_tool_utils.mjs`).href);
  const modelPath = path.join(privateDir, 'modeling.pptx');
  let manifest;
  if (process.argv[4] && process.argv[4] !== '-') {
    // 合并或校验修复时，复用本轮已经导出的同内容章节，避免重复导入和字体导出。
    await fs.copyFile(process.argv[4], modelPath);
    manifest = slides.map((d, i) => ({ page: preservedSlides + i + 1, ...d, ...(d.rows ? { table: true } : {}) }));
  } else {
    const p = await PresentationFile.importPptx(await FileBlob.load(source));
    p.slides.keep([31, 32]);
    await cleanModelingBody(p, p.slides.items[1], 1);
    const [chapter, body] = p.slides.items;
    const seeds = (await p.inspect({ select: '$.slides[*]', include: ['id'] })).records.map(s => s.id);
    const created = slides.map(d => (d.kind === 'chapter' ? chapter : body).duplicate());
    p.delete(seeds); created.forEach((s, i) => s.moveTo(i));
    manifest = [];
    for (const [i, definition] of slides.entries()) {
      const record = await layoutModeling(created[i], definition, path.join(ROOT, 'docs/需求调研+需求分析/图片'));
      manifest.push({ page: preservedSlides + i + 1, ...definition, ...record });
    }
    await (await PresentationFile.exportPptx(p)).save(modelPath);
  }
  console.log(`MODELING ${slides.length} slides`);
  const candidatePath = path.join(privateDir, 'candidate.pptx');
  const merged = spawnSync(`${RUNTIME}/python/python.exe`, [path.join(ROOT, 'scripts/presentations/merge-modeling-deck.py'), source, modelPath, candidatePath], { encoding: 'utf8', env: { ...process.env, PYTHONUTF8: '1' } });
  if (merged.status !== 0) throw new Error(merged.stderr || merged.stdout);
  console.log(merged.stdout.trim());
  const tables = manifest.filter(r => r.table).map(r => r.page);
  const finalPath = path.join(outputDir, filename);
  await finalizePresentation({ workspaceDir, candidatePath, finalPath, explicitTotalSlideCount: preservedSlides + slides.length,
    requiredNativeTableOwnerSlides: tables, requiredNativeChartOwnerSlides: [],
    sourceTemplatePath: source, pythonExecutable: `${RUNTIME}/python/python.exe`,
    integrityValidatorPath: `${SKILL}/container_tools/inspect_presentation_package_integrity.py`,
    layoutValidatorPath: `${SKILL}/container_tools/inspect_presentation_layout_geometry.py`,
    layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit', ...tables.flatMap(n => ['--require-native-table-slide', String(n)])],
    fontPolicy: { basis: 'reference', families: ['微软雅黑', 'Calibri', '黑体', 'Arial', '等线'], referencePath: source,
      referenceSha256: createHash('sha256').update(await fs.readFile(source)).digest('hex') },
    verifyArtifactToolImport: true, receiptPath: path.join(privateDir, 'validation.json'),
  });
  const deck = await PresentationFile.importPptx(await FileBlob.load(finalPath));
  const renders = path.join(privateDir, 'renders'); await fs.mkdir(renders);
  for (let i = 0; i < deck.slides.items.length; i++) {
    const blob = await deck.export({ slide: deck.slides.items[i], format: 'png', scale: 1 });
    await fs.writeFile(path.join(renders, `${String(i + 1).padStart(2, '0')}.png`), new Uint8Array(await blob.arrayBuffer()));
    if (i >= preservedSlides) {
      const layout = await deck.slides.items[i].export({ format: 'layout' });
      await fs.writeFile(path.join(renders, `${String(i + 1).padStart(2, '0')}.layout.json`), await layout.text());
    }
    console.log(`RENDER ${i + 1}`);
  }
  await fs.writeFile(path.join(privateDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(`COMPLETE ${finalPath}`);
}
main().catch(e => { console.error(e.stack); process.exitCode = 1; });
