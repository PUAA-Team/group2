import { createFixtures, navigation, adminNavigation } from '../data.js';

export { navigation, adminNavigation };
export const systems = [
  { id: 'ali', name: '云管控型', reference: '紧凑列表 / 单一主面板', body: 14, title: 22, control: 32, row: 58, radius: 4, accent: '#2b5278' },
  { id: 'tencent', name: '团队协作型', reference: '分区操作 / 紧凑表单', body: 14, title: 24, control: 36, row: 64, radius: 4, accent: '#3268a8' },
];
export const pages = [['jobs', '训练任务'], ['detail', '任务详情'], ['resources', '资源管理'], ['components', '组件规范']];
export const taskPresets = {
  '文本分类': { models: ['Qwen3-0.6B', 'Qwen2.5-0.5B-Instruct'], datasets: ['客服意图语料 v3'], lr: '0.0002', epochs: 5, batch: 4, method: 'LoRA' },
  '图像分类': { models: ['ResNet18', 'MobileNetV3'], datasets: ['商品图像 v1'], lr: '0.001', epochs: 10, batch: 16, method: '全量训练' },
  '目标检测': { models: ['YOLOv8n'], datasets: ['安全帽样本 v2'], lr: '0.001', epochs: 50, batch: 8, method: '全量训练' },
};

export function fixtures() {
  const data = createFixtures();
  data.runs = data.runs.map((run, i) => ({ ...run, name: run.name.replace(' · ', ' - '), created: `2026-10-14 ${['10:24', '10:18', '09:42', '10:32', '09:10', '08:54'][i]}`, owner: i % 2 ? '视觉组' : '算法组' }));
  return data;
}
export function route(hash) {
  const [system, page] = hash.replace(/^#\/?/, '').split('/');
  return { system: systems.some(s => s.id === system) ? system : 'gallery', page: pages.some(p => p[0] === page) ? page : 'jobs' };
}
export function filterRuns(runs, { status = '全部', query = '', sort = 'newest' }) {
  return runs.filter(r => (status === '全部' || r.status === status) && `${r.id} ${r.name} ${r.project} ${r.model}`.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => sort === 'oldest' ? a.created.localeCompare(b.created) : b.created.localeCompare(a.created));
}
export function stopStatus(status) {
  return status === '运行中' ? '已停止' : status === '排队中' ? '已取消' : status;
}
export function validateJob(values) {
  const preset = taskPresets[values.task];
  if (!String(values.name || '').trim()) return '请输入任务名称';
  if (!preset || !preset.models.includes(values.model) || !preset.datasets.includes(values.dataset)) return '请选择与任务类型匹配的模型和数据集';
  if (!(Number(values.lr) > 0 && Number(values.lr) <= 1)) return '学习率须大于 0 且不超过 1';
  if (!Number.isInteger(Number(values.epochs)) || Number(values.epochs) < 1 || Number(values.epochs) > 100) return '训练轮次须为 1～100 的整数';
  if (!Number.isInteger(Number(values.batch)) || Number(values.batch) < 1 || Number(values.batch) > 64) return '批大小须为 1～64 的整数';
  return '';
}
export function nodeSummary(nodes) {
  const available = nodes.filter(n => ['空闲', '使用中'].includes(n.status));
  return { online: available.length, gpu: available.filter(n => n.id.startsWith('GPU')).length, idle: available.filter(n => n.status === '空闲' && n.id.startsWith('GPU')).length, pending: nodes.filter(n => n.status === '待审核').length };
}
