import { options } from "./components.js?v=stage15-1";

export function nodeOptions(nodes, jobKind, deviceKind, selected = "", keepSelection = true) {
  const dedicated = jobKind === "service" ? "inference" : "train_eval";
  const choices = [["", "自动选择"]];
  for (const node of nodes) {
    if (node.devices?.some(device => device.kind === deviceKind &&
      (device.selectable ?? (node.approved && !node.revoked && device.present)) &&
      (!device.purpose || device.purpose === "shared" || device.purpose === dedicated))) {
      choices.push([node.id, node.name]);
    }
  }
  if (keepSelection && selected && !choices.some(([id]) => id === selected)) {
    const name = nodes.find(node => node.id === selected)?.name || "原节点";
    choices.push([selected, `${name}（不可选）`]);
  }
  return options(choices, selected);
}

export function syncResourceNodes(deviceField, nodes) {
  const nodeField = deviceField.form?.elements.namedItem("node_id");
  if (nodeField) nodeField.innerHTML = nodeOptions(nodes, deviceField.dataset.resourceKind, deviceField.value, nodeField.value, false);
}
