import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { FONT, text, surveyRatio, surveyAxes } from './slide-layout.mjs';
import { research } from './research-content.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const RUNTIME = 'C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const SKILL = 'C:/Users/lixu/.codex/plugins/cache/openai-primary-runtime/presentations/26.1009.11318/skills/presentations';
const TEMPLATE = path.join(ROOT, 'docs/需求调研+需求分析/大模型集成训练平台需求调研汇报.pptx');
const workspaceDir = process.argv[2] || 'D:/model-training-demo/style-samples-20261011';
const revision = process.argv[3] || 'v1';
const BLUE = '#1063A8', INK = '#172A3B', MUTED = '#536777';
process.env.RUNTIME_NODE_MODULES = `${RUNTIME}/node/node_modules`;

async function body(p, slide, index, title, chapter) {
  const byName = Object.fromEntries(slide.shapes.items.map(sh => [sh.name.replace(/\s/g, ''), sh]));
  const inspected = JSON.parse((await p.inspect({ select: `$.slides[${index}]`, include: ['elements.id', 'elements.name'] })).ndjson.trim()).elements;
  p.delete(['矩形23', '任意多边形11', '任意多边形13'].map(name => inspected.find(el => el.name.replace(/\s/g, '') === name)?.id).filter(Boolean));
  byName['矩形6'].position = { left: 100, top: 114, width: 1080, height: 574 };
  byName['矩形6'].fill = '#FAFBFC';
  byName['任意多边形16'].position = { left: 1096, top: 114, width: 84, height: 82 };
  const corner = byName['矩形12'];
  corner.position = { left: 1120, top: 131, width: 52, height: 38, rotation: 45 };
  corner.text = chapter;
  corner.text.style = { typeface: FONT, fontSize: 20, color: '#FFFFFF', bold: true, insets: 0, autoFit: 'none' };
  const heading = byName['标题1'];
  heading.position = { left: 136, top: 143, width: 936, height: 46 };
  heading.fill = 'none'; heading.line = { fill: 'none', width: 0 };
  heading.text = title;
  heading.text.style = { typeface: FONT, fontSize: 29, color: BLUE, bold: true, insets: 0, autoFit: 'none', wrap: 'none' };
}

async function sourceImage(slide, filename, alt, position, crop) {
  const blob = new Uint8Array(await fs.readFile(path.join(workspaceDir, 'assets', filename)));
  slide.images.add({ blob, contentType: 'image/png', alt, position, crop, fit: 'contain' });
}

function comparison(slide) {
  const values = [
    ['平台', '训练配置方式', '本次材料的核验范围'],
    ['BML', '算法、网络分开选择；手动超参与搜索', '配置、监控与评估页面'],
    ['PAI', 'Qwen3-0.6B；默认 SFT + LoRA', '编辑配置表单，未提交训练'],
    ['ModelArts', '预置精调；自定义镜像及启动命令', '控制台流程与文档研读'],
  ];
  const tb = slide.tables.add({ rows: 4, columns: 3, left: 136, top: 493, width: 1000, height: 164, values, columnWidths: [140, 465, 395] });
  tb.styleOptions = { headerRow: true, bandedRows: false };
  tb.borders.assign({ fill: '#D4DFE7', style: 'solid', width: 0.65 });
  for (let r = 0; r < 4; r++) {
    tb.rows[r].height = r === 0 ? 35 : 43;
    for (let c = 0; c < 3; c++) {
      const cell = tb.getCell(r, c);
      cell.fill = r === 0 ? BLUE : r % 2 ? '#FFFFFF' : '#F0F5F8';
      cell.text.style = { typeface: FONT, fontSize: 19, color: r === 0 ? '#FFFFFF' : INK, bold: r === 0 || c === 0, wrap: 'none', insets: 0, autoFit: 'none' };
    }
  }
  tb.cells.block({ row: 0, column: 0, rowCount: 4, columnCount: 3 }).assign({ margins: { left: 10, right: 10, top: 7, bottom: 7 } });
}

async function main() {
  const { PresentationFile, FileBlob } = await import(pathToFileURL(`${RUNTIME}/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs`).href);
  const { finalizePresentation, applyPresentationChartFont } = await import(pathToFileURL(`${SKILL}/container_tools/artifact_tool_utils.mjs`).href);
  const privateDir = path.join(workspaceDir, `private-${revision}`), outputDir = path.join(workspaceDir, `output-${revision}`);
  const finalPath = path.join(outputDir, '答辩PPT版式样张_修订版.pptx');
  await fs.mkdir(privateDir, { recursive: true }); await fs.mkdir(outputDir, { recursive: true });
  const templateSha = createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex');
  const p = await PresentationFile.importPptx(await FileBlob.load(TEMPLATE));
  p.slides.keep([1, 13]);
  const chapter = p.slides.items[0], platform = p.slides.items[1], survey = platform.duplicate();
  [chapter, platform, survey].forEach((s, i) => s.moveTo(i));
  const chapterShapes = Object.fromEntries(chapter.shapes.items.map(s => [s.name.replace(/\s/g, ''), s]));
  chapterShapes['矩形11'].text = '02';
  chapterShapes['矩形6'].text = '同类平台调研';
  chapterShapes['矩形6'].position = { left: 468, top: 318, width: 720, height: 72 };
  text(chapter, '商业平台：ModelArts · TI-ONE · PAI · BML · SageMaker · Azure ML\n开源平台：Crater · Kubeflow', 470, 423, 710, 55, 18, { color: '#FFFFFF' });
  chapter.speakerNotes.text = '';

  await body(p, platform, 1, '训练配置：预置模型与自定义作业如何组织', '平台');
  text(platform, 'BML 实际配置界面', 136, 207, 640, 26, 18, { bold: true });
  await sourceImage(platform, 'bml/page-07-image-01.png', 'BML 训练配置界面',
    { left: 136, top: 244, width: 635, height: 240 }, { left: 0, top: 0, right: 0.4, bottom: 0.51 });
  text(platform, '模型与网络分开选择', 813, 242, 320, 32, 23, { bold: true, color: BLUE });
  text(platform, '算法选 ResNet，网络选\nResNet18_vd；超参支持\n手动配置和搜索。', 813, 287, 320, 94, 21);
  text(platform, '保留不同训练入口', 813, 395, 320, 30, 23, { bold: true, color: BLUE });
  text(platform, '预置模型调参、Notebook\n建模、自定义作业分别组织。', 813, 431, 320, 53, 20);
  comparison(platform);
  platform.speakerNotes.text = '';

  await body(p, survey, 2, '问卷结果：算力获取与资源选择各有 45 人', '问卷');
  text(survey, 'Q5 训练中容易遇到的问题  ·  多选题  ·  有效样本 67 份', 136, 207, 990, 27, 19, { color: MUTED });
  text(survey, '原始统计报告', 136, 251, 448, 27, 19, { bold: true });
  await sourceImage(survey, 'survey-page-02.png', '问卷第 5 题完整统计',
    { left: 136, top: 287, width: 448, height: 245 }, { left: 0.098, top: 0.188, right: 0.098, bottom: 0.505 });
  text(survey, '图中列出选择人数最多的六项。', 136, 543, 448, 37, 15, { color: MUTED });
  const q5 = research.slides.find(s => s.chart?.title.startsWith('Q5')).chart;
  const categories = q5.labels.map((label, i) => `${label}（${q5.counts[i]}人）`).reverse();
  const chart = survey.charts.add('bar', {
    position: { left: 602, top: 248, width: 538, height: 330 },
    categories, series: [{ name: '占 67 份问卷的比例', values: q5.counts.map(surveyRatio).reverse(), fill: BLUE, valuesFormatCode: '0.00%' }],
    hasLegend: false, barOptions: { direction: 'bar', grouping: 'clustered', gapWidth: 80 },
    ...surveyAxes(17),
    dataLabels: { showValue: true, position: 'outEnd', numberFormatCode: '0.00%', numberFormatSourceLinked: false, textStyle: { fontSize: 16, fill: INK } },
    chartFill: '#FAFBFC', plotAreaFill: '#FAFBFC', chartLine: { fill: 'none', width: 0 }, plotAreaLine: { fill: 'none', width: 0 },
  });
  applyPresentationChartFont(chart, { fontFamily: FONT });
  text(survey, '资源入口：展示可用 GPU 与授权范围，保留自动和手动选择。\n任务详情：日志独立查看，显示训练参数和实时进度。', 136, 601, 1000, 63, 21);
  survey.speakerNotes.text = '';
  const candidatePath = path.join(privateDir, 'samples-candidate.pptx');
  await (await PresentationFile.exportPptx(p)).save(candidatePath);
  console.log('EXPORTED 3 slides');
  await finalizePresentation({
    workspaceDir, candidatePath, finalPath, explicitTotalSlideCount: 3,
    requiredNativeTableOwnerSlides: [2], requiredNativeChartOwnerSlides: [3], materializeLiteralChartWorkbooks: true,
    sourceTemplatePath: TEMPLATE, pythonExecutable: `${RUNTIME}/python/python.exe`,
    integrityValidatorPath: `${SKILL}/container_tools/inspect_presentation_package_integrity.py`,
    layoutValidatorPath: `${SKILL}/container_tools/inspect_presentation_layout_geometry.py`,
    layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit', '--require-native-table-slide', '2'],
    fontPolicy: { basis: 'reference', families: [FONT, 'Arial'], referencePath: TEMPLATE, referenceSha256: templateSha },
    verifyArtifactToolImport: true, receiptPath: path.join(privateDir, 'validation.json'),
  });
  const finalDeck = await PresentationFile.importPptx(await FileBlob.load(finalPath));
  const renderDir = path.join(privateDir, 'renders'); await fs.mkdir(renderDir, { recursive: true });
  for (let i = 0; i < 3; i++) {
    const blob = await finalDeck.export({ slide: finalDeck.slides.items[i], format: 'png', scale: 1 });
    await fs.writeFile(path.join(renderDir, `${i + 1}.png`), new Uint8Array(await blob.arrayBuffer()));
  }
  console.log(`COMPLETE ${finalPath}`);
}
main().catch(error => { console.error(error.stack); process.exitCode = 1; });
