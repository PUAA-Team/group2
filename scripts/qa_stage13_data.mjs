import assert from "node:assert/strict";

export async function dataFlows({ fixture, run, go, fill, click, wait, capture, evaluate, report }) {
  const seeded = await evaluate(`(async()=>{
    const session=(await(await fetch('/api/v1/auth/session')).json()).data;
    const base='/api/v1/workspaces/'+${JSON.stringify(fixture.workspace_id)};
    async function post(path,body){const r=await fetch(path,{method:'POST',headers:body instanceof FormData?{'X-CSRF-Token':session.csrf_token}:{'X-CSRF-Token':session.csrf_token,'Content-Type':'application/json'},body:body instanceof FormData?body:JSON.stringify(body)});const j=await r.json();if(!r.ok)throw Error('验收数据准备失败 '+r.status);return j.data;}
    const dataset=await post(base+'/datasets',{name:'数据工作区验收 '+${run},task_type:'text_classification'});
    const form=new FormData();form.append('file',new Blob(['text,label\\n alpha ,yes\\nalpha,yes\\n'+Array.from({length:10},(_,i)=>'sample'+i+','+(i%2?'yes':'no')).join('\\n')+'\\n']), 'samples.csv');
    const version=await post(base+'/datasets/'+dataset.id+'/versions',form);
    const images=await post(base+'/datasets',{name:'图像增强验收 '+${run},task_type:'image_classification'});
    const zip=await(await fetch('/api/v1/dataset-templates/image-classification')).blob();const imageForm=new FormData();imageForm.append('file',zip,'images.zip');
    const imageVersion=await post(base+'/datasets/'+images.id+'/versions',imageForm);
    return {dataset:dataset.id,version:version.id,images:images.id,imageVersion:imageVersion.id};
  })()`);
  const save = async () => { await click('[role=dialog] [type=submit]'); await wait("!document.querySelector('[role=dialog]') && !document.querySelector('.live-loading')"); };
  const base = `/api/v1/workspaces/${fixture.workspace_id}`;
  const detail = () => evaluate(`(async()=>{const id=location.hash.split('/')[2].split('?')[0];return(await(await fetch(${JSON.stringify(base + "/data-operations/")}+id)).json()).data;})()`);
  await go(`/datasets/${seeded.dataset}/samples?version=${seeded.version}`, ".table");
  await click('[data-action="data-new-annotation"]'); await wait("!!document.querySelector('[name=assigned_to]')");
  await fill("name", "分类标注验收 " + run, '[data-form="dialog"]'); await fill("limit", "2", '[data-form="dialog"]'); await save();
  await wait("!!document.querySelector('.annotation-workbench')");
  const batchId = await evaluate("location.hash.split('/')[2].split('?')[0]");
  for (const [index, value] of [[0, "no"], [1, "yes"]]) {
    await go(`/annotation/${batchId}?sample=${index}`, ".annotation-workbench");
    await fill("value", value, '[data-form="annotation-result"]'); await click('[data-form="annotation-result"] [value=submit]');
    await wait("!document.querySelector('.live-loading') && document.querySelector('[data-form=annotation-result]')?.dataset.revision==='1'");
  }
  await capture("annotation-review-1440.png");
  await click('[data-action="annotation-review-page"]'); await wait("document.querySelector('.toolbar')?.textContent.includes('已审核 2/2')");
  await click('[data-action="annotation-confirm-publish"]'); await wait("!!document.querySelector('[role=dialog]')"); await save();
  await wait("!![...document.querySelectorAll('a')].find(a=>a.textContent==='已发布版本')");
  const annotated = await evaluate(`(async()=>{const b=(await(await fetch(${JSON.stringify(base + "/annotation-batches/" + batchId)})).json()).data;const r=(await(await fetch(${JSON.stringify(base + "/dataset-versions/")}+b.output_version_id+'/samples')).json()).data;return {version:b.output_version_id,labels:r.samples.slice(0,2).map(x=>x.label)};})()`);
  assert.deepEqual(annotated.labels, ["no", "yes"]); report.checks.push("页面人工标注、逐条保存提交、批量审核、发布真实新版本");
  await go(`/datasets/${seeded.dataset}`, ".table");
  await click(`[data-action="data-new-operation"][data-id="clean:${seeded.version}"]`); await wait("!!document.querySelector('[name=kind]')");
  await fill("name", "数据清洗验收 " + run, '[data-form="dialog"]'); await save();
  await wait("!!document.querySelector('[data-action=data-confirm-publish]')"); await capture("data-clean-review-1440.png");
  const clean = await detail(); assert.equal(clean.status, "review"); assert.equal(clean.candidates[0].sample_count, 11);
  await click('[data-action="data-confirm-publish"]'); await wait("!!document.querySelector('[role=dialog]')"); await save(); await wait("document.body.textContent.includes('已发布版本')");
  const cleaned = await detail(); assert.equal(cleaned.status, "published"); report.checks.push("独立CPU进程执行清洗、预览并发布，实际去重12→11条");
  await go("/augmentation", ".page-heading h1"); await click('[data-action="data-new-operation"]'); await wait("!!document.querySelector('[name=kind]')");
  await fill("name", "图片翻转验收 " + run, '[data-form="dialog"]'); await fill("version_id", seeded.imageVersion, '[data-form="dialog"]');
  assert.equal(await evaluate("document.querySelector('[name=methods][value=punctuation]').disabled"), true);
  await evaluate("document.querySelector('[name=methods][value=flip]').checked=true"); await save();
  await wait("!!document.querySelector('[data-action=data-confirm-publish]')");
  await wait("[...document.querySelectorAll('.data-thumbnail')].length>0 && [...document.querySelectorAll('.data-thumbnail')].every(i=>i.complete&&i.naturalWidth>0)");
  await capture("image-augmentation-review-1440.png");
  const augmentation = await detail(); assert.equal(augmentation.kind, "augment"); assert.ok(augmentation.candidates[0].sample_count > 1);
  const augmentationRoute = await evaluate("location.hash.slice(1)"); report.checks.push("真实图像增强任务、类型约束、鉴权图片候选预览");
  await go(`/datasets/${seeded.dataset}`, ".table"); await click(`[data-action="data-new-operation"][data-id="clean:${seeded.version}"]`); await wait("!!document.querySelector('[name=kind]')");
  await fill("name", "分层划分验收 " + run, '[data-form="dialog"]'); await fill("kind", "split", '[data-form="dialog"]'); await save();
  await wait("!!document.querySelector('[data-action=data-confirm-publish]')"); await capture("data-split-review-1440.png");
  await click('[data-action="data-confirm-publish"]'); await wait("!!document.querySelector('[role=dialog]')"); await save(); await wait("document.body.textContent.includes('已发布版本')");
  const split = await detail(); assert.equal(split.output_version_ids.length, 3);
  await go("/train/new", '[data-form="training-wizard"]');
  await fill("task_type", "text_classification"); await fill("name", "分区选择验收 " + run);
  await click('[data-action="wizard-next"]'); await wait("!!document.querySelector('[data-wizard-dataset]')");
  const available = await evaluate("[...document.querySelector('[data-wizard-dataset]').options].map(x=>x.value)");
  assert.ok(!available.includes(split.output_version_ids[1]) && !available.includes(split.output_version_ids[2]));
  report.checks.push("三份分区实际发布，训练向导排除验证和测试版本");
  const routes = [["/annotation", ".table"], [`/annotation/${batchId}`, ".annotation-workbench"], ["/augmentation", ".table"], ["/data-operations", ".table"], [augmentationRoute, ".data-thumbnail"], [`/datasets/${seeded.dataset}/samples?version=${annotated.version}`, ".table"], [`/datasets/${seeded.images}/samples?version=${seeded.imageVersion}`, ".data-thumbnail"]];
  return { routes, batchId, ...seeded, augmentationRoute };
}
