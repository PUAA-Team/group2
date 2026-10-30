import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { researchV3 } from './research-v3-content.mjs';
import { layoutResearch } from './research-v3-layout.mjs';
import { cleanBody } from './defense-v2-layout.mjs';
import { FONT } from './slide-layout.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const RUNTIME = 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const SKILL = 'C:/Users/lixu/.codex/plugins/cache/openai-primary-runtime/presentations/26.1011.11113/skills/presentations';
const TEMPLATE = path.join(ROOT, 'docs/需求调研+需求分析/大模型集成训练平台需求调研汇报.pptx');
const workspaceDir = process.argv[2] || 'D:/model-training-demo/research-ppt-update-20261012';
const revision = process.argv[3] || 'v1';
process.env.RUNTIME_NODE_MODULES = `${RUNTIME}/node/node_modules`;
const assetPath = file => path.join(file.startsWith('modelarts/') ? `${workspaceDir}/assets` : 'D:/model-training-demo/style-samples-20261011/assets', file);

async function main() {
  if (!/^[A-Za-z0-9_-]+$/.test(revision)) throw new Error('版本名非法');
  const { PresentationFile, FileBlob } = await import(pathToFileURL(`${RUNTIME}/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs`).href);
  const { finalizePresentation, applyPresentationChartFont } = await import(pathToFileURL(`${SKILL}/container_tools/artifact_tool_utils.mjs`).href);
  const privateDir = path.join(workspaceDir, `private-${revision}`), outputDir = path.join(workspaceDir, `output-${revision}`);
  await fs.mkdir(privateDir, { recursive: true }); await fs.mkdir(outputDir, { recursive: true });
  const finalPath = path.join(outputDir, researchV3.filename);
  try { await fs.access(finalPath); throw new Error(`输出已存在：${finalPath}`); } catch (e) { if (e.code !== 'ENOENT') throw e; }
  const templateSha = createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex');
  const p = await PresentationFile.importPptx(await FileBlob.load(TEMPLATE));
  p.slides.keep([0, 1, 2, 13]);
  const [cover, chapter, methods, body] = p.slides.items;
  await cleanBody(p, body, 3);
  const anchors = (await p.inspect({ select: '$.slides[1,2,3]', include: ['id'] })).ndjson.trim().split('\n').map(row => JSON.parse(row).id);
  const slides = researchV3.slides.map(d => d.kind === 'cover' ? cover : (d.kind === 'chapter' ? chapter : d.kind === 'methods' ? methods : body).duplicate());
  p.delete(anchors); slides.forEach((s, i) => s.moveTo(i));
  const manifest = [];
  for (const [i, d] of researchV3.slides.entries()) {
    const record = { page: i + 1, title: d.title, kind: d.kind, main: d.main };
    await layoutResearch(slides[i], d, researchV3, assetPath, applyPresentationChartFont, record);
    manifest.push(record);
  }
  const candidatePath = path.join(privateDir, 'candidate.pptx');
  await (await PresentationFile.exportPptx(p)).save(candidatePath);
  console.log(`EXPORTED ${slides.length} slides`);
  const tables = manifest.filter(r => r.kind === 'table').map(r => r.page);
  const charts = manifest.filter(r => r.kind.startsWith('survey')).map(r => r.page);
  await finalizePresentation({ workspaceDir, candidatePath, finalPath, explicitTotalSlideCount: slides.length,
    requiredNativeTableOwnerSlides: tables, requiredNativeChartOwnerSlides: charts, materializeLiteralChartWorkbooks: true,
    sourceTemplatePath: TEMPLATE, pythonExecutable: `${RUNTIME}/python/python.exe`,
    integrityValidatorPath: `${SKILL}/container_tools/inspect_presentation_package_integrity.py`,
    layoutValidatorPath: `${SKILL}/container_tools/inspect_presentation_layout_geometry.py`,
    layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit', ...tables.flatMap(n => ['--require-native-table-slide', String(n)])],
    fontPolicy: { basis: 'reference', families: [FONT, 'Arial', 'Calibri', '黑体'], referencePath: TEMPLATE, referenceSha256: templateSha },
    verifyArtifactToolImport: true, receiptPath: path.join(privateDir, 'validation.json'),
  });
  const deck = await PresentationFile.importPptx(await FileBlob.load(finalPath));
  const renders = path.join(privateDir, 'renders'); await fs.mkdir(renders, { recursive: true });
  for (let i = 0; i < slides.length; i++) {
    const blob = await deck.export({ slide: deck.slides.items[i], format: 'png', scale: 1 });
    await fs.writeFile(path.join(renders, `${String(i + 1).padStart(2, '0')}.png`), new Uint8Array(await blob.arrayBuffer()));
  }
  await fs.writeFile(path.join(privateDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(`COMPLETE ${finalPath}`);
}
main().catch(e => { console.error(e.stack); process.exitCode = 1; });
