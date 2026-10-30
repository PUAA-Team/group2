import { icon, button, status } from './components.js?v=palette-3';

export const palettes = [
  ['海军蓝', '#2b5278'], ['石墨灰', '#444b56'], ['深青绿', '#276d62'],
  ['湖蓝', '#0069a8'], ['砖红', '#8a433b'], ['橙色', '#c94c00'],
];
export const statusStyles = [['text', '纯文字'], ['outline', '线框标记'], ['icon', '图形符号']];
export const cornerStyles = [['square', '直角'], ['micro', '微圆角'], ['soft', '柔和圆角']];
export function defaults(system = 'ali') {
  return { color: system === 'ali' ? '#2b5278' : '#3268a8', status: 'text', corners: 'micro' };
}
export function normalizeAppearance(value, system) {
  const base = defaults(system);
  return {
    color: /^#[0-9a-f]{6}$/i.test(value?.color || '') ? value.color.toLowerCase() : base.color,
    status: statusStyles.some(([id]) => id === value?.status) ? value.status : base.status,
    corners: cornerStyles.some(([id]) => id === value?.corners) ? value.corners : base.corners,
  };
}
const rgb = color => [1, 3, 5].map(start => parseInt(color.slice(start, start + 2), 16));
export const luminance = color => rgb(color).map(c => {
  const v = c / 255;
  return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
}).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
export const contrast = (a, b) => (Math.max(luminance(a), luminance(b)) + .05) / (Math.min(luminance(a), luminance(b)) + .05);
const mix = (color, target, amount) => '#' + rgb(color).map(c => Math.round(c * (1 - amount) + target * amount).toString(16).padStart(2, '0')).join('');
export function paletteTokens(color, system) {
  // 浅色按钮自动选深色文字，链接保持对白底的可读对比度。
  const ink = contrast(color, '#ffffff') >= contrast(color, '#111111') ? '#ffffff' : '#111111';
  let link = color;
  for (let i = 0; contrast(link, '#ffffff') < 4.5 && i < 12; i++) link = mix(link, 0, .12);
  return {
    '--primary': color, '--primary-ink': ink, '--primary-border': contrast(color, '#ffffff') >= 3 ? color : link, '--primary-hover': mix(color, 0, .12), '--link': link,
    '--tab-active': link, '--nav-selected-text': link, '--running': link, '--progress-fill': link,
    '--chart-primary': link, '--chart-secondary': '#84909c', '--eval-dash': '5 3', '--brand': system === 'ali' ? mix(link, 255, .48) : link,
    '--focus-shadow': system === 'ali' ? 'none' : `0 0 0 3px ${mix(link, 255, .9)}`,
    '--selected-bg': mix(link, 255, .92), '--nav-selected-bg': mix(link, 255, .90),
    '--hover-bg': mix(link, 255, .97), '--running-bg': 'transparent',
  };
}
export function appearanceForm(settings, system) {
  const choices = (name, items, active) => `<div class="appearance-choices">${items.map(([id, label]) => `<label><input type="radio" name="appearance-${name}" value="${id}" data-appearance="${name}" ${id === active ? 'checked' : ''}><span>${label}</span></label>`).join('')}</div>`;
  return `<header class="modal-head"><h2 id="drawer-title">外观调节</h2><button class="icon-btn" data-action="close-drawer" aria-label="关闭外观调节">${icon('close')}</button></header><div class="drawer-body appearance-body"><fieldset><legend>主色</legend><div class="palette-grid">${palettes.map(([label, color]) => `<button type="button" class="palette-choice" data-action="palette" data-value="${color}" aria-pressed="${settings.color === color}"><i style="background:${color}"></i>${label}</button>`).join('')}</div><label class="custom-color"><span>自选颜色</span><input type="color" value="${settings.color}" data-custom-color aria-label="自选主色"><output id="color-value">${settings.color.toUpperCase()}</output></label></fieldset><fieldset><legend>状态显示</legend>${choices('status', statusStyles, settings.status)}<div class="appearance-status-preview">${['运行中', '排队中', '已完成', '失败', '已停止'].map(status).join('')}</div></fieldset><fieldset><legend>边角</legend>${choices('corners', cornerStyles, settings.corners)}<div class="corner-preview"><span>外层面板</span>${button('主要操作', 'appearance-example', 'primary')}</div></fieldset><div class="appearance-scope">${system === 'ali' ? '云管控型' : '团队协作型'} · 即时预览，自动保存</div></div><footer class="modal-footer">${button('恢复默认', 'appearance-reset')}${button('关闭', 'close-drawer', 'primary')}</footer>`;
}
