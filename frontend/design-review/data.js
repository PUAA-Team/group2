export const schemes = [
  { id: 'a', code: 'A', name: '精密工作台', description: '列表优先，结构清晰', reference: 'Linear', color: '#334d69' },
  { id: 'b', code: 'B', name: '实验室', description: '实验曲线与结果对照', reference: 'MLflow', color: '#245a50' },
  { id: 'c', code: 'C', name: '资源控制台', description: '设备、队列与执行状态', reference: 'Carbon / Grafana', color: '#295b87' },
  { id: 'd', code: 'D', name: '轻量工作室', description: '项目与数据资产预览', reference: 'Fluent / Model Hub', color: '#3c647a' },
];

export const pages = [
  { id: 'home', name: '工作台' },
  { id: 'run', name: '训练详情' },
  { id: 'resources', name: '资源管理' },
];

export const navigation = [
  { id: 'overview', name: '概览', icon: 'home', children: [['工作台', 'home'], ['用户空间', 'scope'], ['资源监控', 'resources']] },
  { id: 'data', name: '数据管理', icon: 'data', children: [['数据集', 'scope'], ['在线标注', 'scope'], ['数据增强', 'scope']] },
  { id: 'training', name: '模型训练', icon: 'training', children: [['训练项目', 'scope'], ['训练任务', 'run']] },
  { id: 'models', name: '模型管理', icon: 'model', children: [['模型仓库', 'scope'], ['模型评估', 'scope']] },
  { id: 'deploy', name: '部署服务', icon: 'service', children: [['在线服务', 'scope'], ['API KEY 管理', 'scope']] },
];

export const adminNavigation = ['统计面板', '资源管理', '数据管理', '模型管理', '作业管理', '用户管理', '操作记录', '系统设置'];

export function createFixtures() {
  return {
    runs: [
      { id: 'TRN-1048', name: '客服意图 · LoRA 04', project: '客服意图识别', task: '文本分类', model: 'Qwen3-0.6B', dataset: '客服意图语料 v3', status: '运行中', progress: 68, epoch: '3 / 5', score: '0.914', metric: '宏平均 F1', gpu: 'GPU 01', duration: '18 分 32 秒', lr: '2e-4', rank: 8, batch: 4, memory: 6.2 },
      { id: 'TRN-1047', name: '安全帽检测 · 基线 02', project: '安全帽检测', task: '目标检测', model: 'YOLOv8n', dataset: '安全帽样本 v2', status: '运行中', progress: 42, epoch: '21 / 50', score: '0.812', metric: 'mAP', gpu: 'GPU 02', duration: '25 分 08 秒', lr: '1e-3', batch: 8, memory: 5.4 },
      { id: 'TRN-1046', name: '客服意图 · LoRA 03', project: '客服意图识别', task: '文本分类', model: 'Qwen3-0.6B', dataset: '客服意图语料 v3', status: '已完成', progress: 100, epoch: '5 / 5', score: '0.902', metric: '宏平均 F1', gpu: 'GPU 03', duration: '26 分 14 秒', lr: '1e-4', rank: 8, batch: 4, memory: 5.9 },
      { id: 'TRN-1045', name: '客服意图 · LoRA 05', project: '客服意图识别', task: '文本分类', model: 'Qwen3-0.6B', dataset: '客服意图语料 v3', status: '排队中', progress: 0, epoch: '0 / 5', score: '—', metric: '宏平均 F1', gpu: 'GPU 队列', duration: '等待 4 分钟', lr: '2e-4', rank: 16, batch: 4, memory: 0 },
      { id: 'TRN-1044', name: '商品分类 · 基线 01', project: '商品图像分类', task: '图像分类', model: 'ResNet18', dataset: '商品图像 v1', status: '已完成', progress: 100, epoch: '10 / 10', score: '0.934', metric: '准确率', gpu: 'GPU 03', duration: '31 分 06 秒', lr: '1e-3', batch: 16, memory: 4.2 },
      { id: 'TRN-1043', name: '客服意图 · LoRA 02', project: '客服意图识别', task: '文本分类', model: 'Qwen3-0.6B', dataset: '客服意图语料 v2', status: '失败', progress: 23, epoch: '1 / 5', score: '—', metric: '宏平均 F1', gpu: 'GPU 01', duration: '4 分 11 秒', lr: '2e-4', rank: 8, batch: 4, memory: 0 },
    ],
    nodes: [
      { id: 'GPU 01', name: '开发节点 01', model: 'RTX 4060', source: '本地 Worker', status: '使用中', util: 78, memory: 6.2, total: 8, task: '客服意图 · LoRA 04', temperature: 64, cpu: 42 },
      { id: 'GPU 02', name: '开发节点 02', model: 'RTX 4060', source: '本地 Worker', status: '使用中', util: 66, memory: 5.4, total: 8, task: '安全帽检测 · 基线 02', temperature: 61, cpu: 35 },
      { id: 'GPU 03', name: '开发节点 03', model: 'RTX 4060', source: '本地 Worker', status: '空闲', util: 0, memory: 0.3, total: 8, task: '—', temperature: 39, cpu: 8 },
      { id: 'GPU 04', name: '开发节点 04', model: 'RTX 4060', source: '本地 Worker', status: '离线', util: 0, memory: 0, total: 8, task: '—', temperature: 0, cpu: 0 },
      { id: 'GPU 05', name: '笔记本节点', model: 'RTX 4070 Laptop', source: '本地 Worker', status: '空闲', util: 0, memory: 0.4, total: 8, task: '—', temperature: 41, cpu: 12 },
      { id: 'CPU 01', name: 'CPU 节点', model: 'CPU · 16 核', source: '本地 Worker', status: '空闲', util: 0, memory: 2.8, total: 32, task: '—', temperature: 36, cpu: 18 },
    ],
    datasets: [
      { id: 'text', name: '客服意图语料', task: '文本分类', count: '8,600 条', version: 'v3', format: 'JSONL', sample: '快递到了哪里？\n物流查询\n这个商品可以退换吗？\n售后咨询' },
      { id: 'image', name: '安全帽标注样本', task: '目标检测', count: '1,280 张', version: 'v2', format: 'COCO', sample: '图像 / 标注框' },
      { id: 'table', name: '用户流失样本', task: '表格分类', count: '4,200 行', version: 'v1', format: 'CSV', sample: 'visit_count, last_active, churn\n24, 3, 0\n2, 45, 1' },
    ],
  };
}

export function summarize(data) {
  return {
    running: data.runs.filter(x => x.status === '运行中').length,
    queued: data.runs.filter(x => x.status === '排队中').length,
    completed: data.runs.filter(x => x.status === '已完成').length,
    failed: data.runs.filter(x => x.status === '失败').length,
    gpu: data.nodes.filter(x => x.id.startsWith('GPU')).length,
    online: data.nodes.filter(x => ['使用中', '空闲'].includes(x.status)).length,
    idle: data.nodes.filter(x => x.id.startsWith('GPU') && x.status === '空闲').length,
  };
}

export function selectRuns(runs, filter = '全部', query = '') {
  const needle = query.toLocaleLowerCase().trim();
  return runs.filter(run => (filter === '全部' || run.status === filter) && `${run.name} ${run.model} ${run.project}`.toLocaleLowerCase().includes(needle));
}

export function parseRoute(hash) {
  const [scheme, page] = hash.replace(/^#\/?/, '').split('/');
  return { scheme: schemes.some(x => x.id === scheme) ? scheme : 'gallery', page: pages.some(x => x.id === page) ? page : 'home' };
}
