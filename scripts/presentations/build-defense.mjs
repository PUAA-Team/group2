import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { research } from './research-content.mjs';
import { analysis } from './analysis-content.mjs';
import { FONT, prepareBody, editCover, addTable, addColumns, addCharts, addDiagram } from './slide-layout.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const RUNTIME = 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies';
// 仅为当前制作进程及其校验子进程指定随附运行时，不修改系统环境。
process.env.RUNTIME_NODE_MODULES = `${RUNTIME}/node/node_modules`;
const SKILL = 'C:/Users/lixu/.codex/plugins/cache/openai-primary-runtime/presentations/26.1009.11318/skills/presentations';
const TEMPLATE = path.join(ROOT, 'docs/需求调研+需求分析/大模型集成训练平台需求调研汇报.pptx');
const workspaceDir = process.argv[2] || 'D:/model-training-demo/defense-ppt-20261011';
const revision = process.argv[3] || 'v1';

async function main() {
  const { PresentationFile, FileBlob } = await import(pathToFileURL(`${RUNTIME}/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs`).href);
  const { applyPresentationChartFont, finalizePresentation } = await import(pathToFileURL(`${SKILL}/container_tools/artifact_tool_utils.mjs`).href);
  const privateDir = path.join(workspaceDir, `private-${revision}`);
  const outputDir = path.join(workspaceDir, `output-${revision}`);
  await fs.mkdir(privateDir, { recursive: true });
  await fs.mkdir(outputDir, { recursive: true });
  const templateSha = createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex');
  const manifest = [];
  const selectedDeck = process.argv[4];
  for (const deck of [research, analysis].filter(d => !selectedDeck || d.key === selectedDeck)) {
    console.log(`IMPORT ${deck.key}`);
    const p = await PresentationFile.importPptx(await FileBlob.load(TEMPLATE));
    p.slides.keep([0, 13]);
    const cover = p.slides.items[0];
    const originalBody = p.slides.items[1];
    const bodyAnchor = JSON.parse((await p.inspect({ select: '$.slides[1]', include: ['id'] })).ndjson.trim()).id;
    const bodySlides = deck.slides.slice(1).map(() => originalBody.duplicate());
    p.delete([bodyAnchor]);
    const slides = [cover, ...bodySlides];
    slides.forEach((slide, index) => slide.moveTo(index));
    editCover(cover, deck.slides[0], deck);
    const records = [{ index: 1, title: deck.slides[0].title, kind: 'cover', hidden: false }];
    for (let i = 1; i < slides.length; i++) {
      const slide = slides[i], definition = deck.slides[i];
      await prepareBody(p, slide, definition, deck, i);
      const record = { index: i + 1, title: definition.title, kind: definition.kind, hidden: i >= deck.mainCount };
      if (definition.kind === 'table') addTable(slide, definition, record);
      else if (definition.kind === 'columns') addColumns(slide, definition);
      else if (definition.kind === 'diagram') addDiagram(slide, definition);
      else addCharts(slide, definition, applyPresentationChartFont);
      records.push(record);
    }
    const tables = records.filter(r => r.kind === 'table').map(r => r.index);
    const charts = records.filter(r => r.kind === 'charts' || r.kind === 'chartAside').map(r => r.index);
    const candidatePath = path.join(privateDir, `${deck.key}-candidate.pptx`);
    const finalPath = path.join(outputDir, deck.filename);
    await (await PresentationFile.exportPptx(p)).save(candidatePath);
    console.log(`EXPORTED ${deck.key} ${slides.length} slides`);
    await fs.writeFile(path.join(privateDir, `${deck.key}-manifest.json`), JSON.stringify(records, null, 2));
    const result = await finalizePresentation({
      workspaceDir, candidatePath, finalPath,
      explicitTotalSlideCount: deck.slides.length,
      requiredNativeTableOwnerSlides: tables, requiredNativeChartOwnerSlides: charts,
      materializeLiteralChartWorkbooks: charts.length > 0,
      sourceTemplatePath: TEMPLATE,
      pythonExecutable: `${RUNTIME}/python/python.exe`,
      integrityValidatorPath: `${SKILL}/container_tools/inspect_presentation_package_integrity.py`,
      layoutValidatorPath: `${SKILL}/container_tools/inspect_presentation_layout_geometry.py`,
      layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit', ...tables.flatMap(n => ['--require-native-table-slide', String(n)])],
      fontPolicy: { basis: 'reference', families: [FONT, 'Arial'], referencePath: TEMPLATE, referenceSha256: templateSha },
      verifyArtifactToolImport: true,
      receiptPath: path.join(privateDir, `${deck.key}-validation.json`),
    });
    console.log(`FINALIZED ${deck.key} ${finalPath}`);
    const renderDir = path.join(privateDir, `${deck.key}-renders`);
    await fs.mkdir(renderDir, { recursive: true });
    // 校验后的最终文件重新导入，渲染范围包含默认隐藏的附录。
    const finalDeck = await PresentationFile.importPptx(await FileBlob.load(finalPath));
    for (let i = 0; i < finalDeck.slides.items.length; i++) {
      const slide = finalDeck.slides.items[i];
      const blob = await finalDeck.export({ slide, format: 'png', scale: 1 });
      await fs.writeFile(path.join(renderDir, `${String(i + 1).padStart(2, '0')}.png`), new Uint8Array(await blob.arrayBuffer()));
      const layout = await slide.export({ format: 'layout' });
      await fs.writeFile(path.join(renderDir, `${String(i + 1).padStart(2, '0')}.layout.json`), typeof layout === 'string' ? layout : JSON.stringify(layout));
    }
    manifest.push({ key: deck.key, finalPath, renderDir, slideCount: deck.slides.length, mainCount: deck.mainCount, records, result });
    console.log(`RENDERED ${deck.key}`);
  }
  await fs.writeFile(path.join(privateDir, 'build-manifest.json'), JSON.stringify(manifest, null, 2));
  console.log('BUILD COMPLETE');
}
main().catch(error => { console.error(`BUILD ERROR: ${error.message}\n${String(error.stack).slice(0, 2200)}`); process.exitCode = 1; });
