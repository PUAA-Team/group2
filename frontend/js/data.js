const number = (name, label, value, min, max, step = 1) => ({ name, label, value, min, max, step });

export const TASKS = [
  {
    id: "image-classification", group: "图像", name: "图像分类", format: "图片文件夹 + labels.csv", metric: "准确率",
    models: [{ id: "mobilenet", name: "MobileNetV3", kind: "预置模型" }, { id: "resnet18", name: "ResNet18", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 20, 1, 200), number("batch", "批大小", 16, 1, 128), number("lr", "学习率", 0.001, 0.000001, 1, 0.0001)],
    template: "filename,label\nhelmet_001.jpg,helmet\nhelmet_002.jpg,no_helmet\n", processing: ["图片尺寸检查", "类别统计", "训练/验证集划分"]
  },
  {
    id: "object-detection", group: "图像", name: "目标检测", format: "图片 + COCO 标注 JSON", metric: "mAP",
    models: [{ id: "yolov8n-pre", name: "YOLOv8n", kind: "预置模型" }, { id: "yolov8n-net", name: "YOLOv8n 网络", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 50, 1, 300), number("batch", "批大小", 8, 1, 64), number("lr", "学习率", 0.001, 0.000001, 1, 0.0001)],
    template: '{"images":[{"id":1,"file_name":"image_001.jpg"}],"annotations":[{"image_id":1,"category_id":1,"bbox":[10,20,80,90]}],"categories":[{"id":1,"name":"helmet"}]}\n', processing: ["标注检查", "类别统计", "训练/验证集划分"]
  },
  {
    id: "instance-segmentation", group: "图像", name: "实例分割", format: "图片 + COCO 分割标注", metric: "分割 mAP",
    models: [{ id: "maskrcnn-pre", name: "Mask R-CNN", kind: "预置模型" }, { id: "unet-net", name: "U-Net 网络", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 30, 1, 200), number("batch", "批大小", 4, 1, 64), number("lr", "学习率", 0.0005, 0.000001, 1, 0.0001)],
    template: '{"images":[{"id":1,"file_name":"image_001.jpg"}],"annotations":[{"image_id":1,"category_id":1,"segmentation":[[10,20,80,20,80,90,10,90]]}],"categories":[{"id":1,"name":"object"}]}\n', processing: ["掩码检查", "类别统计", "训练/验证集划分"]
  },
  {
    id: "text-classification", group: "文本", name: "文本分类", format: "CSV：text,label", metric: "F1 分数",
    models: [{ id: "bert-text", name: "中文 BERT", kind: "预置模型" }, { id: "qwen25-05b", name: "Qwen2.5-0.5B-Instruct", kind: "预置模型", method: "LoRA / SFT", description: "按指令生成分类标签" }, { id: "textcnn", name: "TextCNN", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 8, 1, 100), number("batch", "批大小", 16, 1, 128), number("lr", "学习率", 0.00002, 0.000001, 1, 0.00001)],
    template: "text,label\n如何修改收货地址,售后咨询\n商品什么时候发货,物流咨询\n", processing: ["空文本检查", "重复文本去除", "训练/验证集划分"]
  },
  {
    id: "llm-instruction", group: "大语言模型", name: "指令微调", format: "JSONL：instruction,input,output", metric: "验证损失",
    models: [{ id: "qwen25-05b-sft", name: "Qwen2.5-0.5B-Instruct", kind: "预置模型", method: "LoRA / SFT", description: "轻量参数微调演示" }],
    params: [number("epochs", "训练轮次", 3, 1, 20), number("batch", "批大小", 2, 1, 32), number("lr", "学习率", 0.0002, 0.000001, 0.01, 0.0001)],
    template: '{"instruction":"判断用户咨询类别，只输出类别名称","input":"商品什么时候发货？","output":"物流咨询"}\n', processing: ["JSONL 字段检查", "空样本检查", "训练/验证集划分"]
  },
  {
    id: "text-similarity", group: "文本", name: "短文本相似度", format: "CSV：text_a,text_b,label", metric: "准确率",
    models: [{ id: "sbert-pre", name: "Sentence-BERT", kind: "预置模型" }, { id: "siamese-net", name: "双塔网络", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 8, 1, 100), number("batch", "批大小", 16, 1, 128), number("lr", "学习率", 0.00002, 0.000001, 1, 0.00001)],
    template: "text_a,text_b,label\n如何退款,怎么申请退货,1\n修改地址,查询物流,0\n", processing: ["空文本检查", "重复样本去除", "训练/验证集划分"]
  },
  {
    id: "named-entity", group: "文本", name: "实体抽取", format: "JSONL：text,entities", metric: "实体 F1",
    models: [{ id: "bert-crf-pre", name: "BERT-CRF", kind: "预置模型" }, { id: "bilstm-crf", name: "BiLSTM-CRF", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 10, 1, 100), number("batch", "批大小", 16, 1, 128), number("lr", "学习率", 0.00002, 0.000001, 1, 0.00001)],
    template: '{"text":"北京航空航天大学位于北京","entities":[{"start":0,"end":8,"label":"机构"}]}\n', processing: ["标注范围检查", "标签统计", "训练/验证集划分"]
  },
  {
    id: "tabular-binary", group: "表格", name: "二分类", format: "CSV：特征列 + target", metric: "AUC",
    models: [{ id: "xgboost-binary", name: "XGBoost", kind: "预置模型" }, { id: "mlp-binary", name: "多层感知机", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 30, 1, 200), number("batch", "批大小", 32, 1, 256), number("lr", "学习率", 0.001, 0.000001, 1, 0.0001)],
    template: "age,usage_days,target\n25,18,0\n41,3,1\n", processing: ["缺失值检查", "重复行去除", "训练/验证集划分"]
  },
  {
    id: "tabular-multiclass", group: "表格", name: "多分类", format: "CSV：特征列 + target", metric: "宏平均 F1",
    models: [{ id: "xgboost-multi", name: "XGBoost 多分类", kind: "预置模型" }, { id: "mlp-multi", name: "多层感知机", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 30, 1, 200), number("batch", "批大小", 32, 1, 256), number("lr", "学习率", 0.001, 0.000001, 1, 0.0001)],
    template: "feature_a,feature_b,target\n0.3,12,A\n0.7,8,B\n", processing: ["缺失值检查", "类别分布", "训练/验证集划分"]
  },
  {
    id: "tabular-regression", group: "表格", name: "回归预测", format: "CSV：特征列 + target", metric: "均方误差",
    models: [{ id: "xgboost-reg", name: "XGBoost 回归", kind: "预置模型" }, { id: "mlp-reg", name: "多层感知机", kind: "网络训练" }],
    params: [number("epochs", "训练轮次", 30, 1, 200), number("batch", "批大小", 32, 1, 256), number("lr", "学习率", 0.001, 0.000001, 1, 0.0001)],
    template: "area,rooms,target\n89,2,120.5\n110,3,165.0\n", processing: ["缺失值检查", "异常值预览", "训练/验证集划分"]
  }
];

export const taskById = id => TASKS.find(task => task.id === id);
export const modelById = id => TASKS.flatMap(task => task.models.map(model => ({ ...model, taskId: task.id }))).find(model => model.id === id);

export const SEED_STATE = {
  datasets: [
    { id: "ds-helmet", name: "安全帽标注样本", type: "图像", taskId: "object-detection", format: "COCO JSON", count: 1280, size: "482 MB", version: 2, status: "可训练", updated: "09-27", sample: "图片 1,280 张 · 标注 2,614 条", files: [] },
    { id: "ds-intent", name: "客服意图语料", type: "文本", taskId: "text-classification", format: "CSV", count: 8600, size: "9.4 MB", version: 3, status: "可训练", updated: "09-26", sample: "售后咨询、物流咨询、商品咨询", files: [] },
    { id: "ds-churn", name: "用户流失样本", type: "表格", taskId: "tabular-binary", format: "CSV", count: 4200, size: "1.8 MB", version: 1, status: "待处理", updated: "09-25", sample: "18 个特征列 · 1 个目标列", files: [] }
  ],
  projects: [
    { id: "pr-helmet", name: "安全帽检测", taskId: "object-detection", description: "识别作业现场是否佩戴安全帽", updated: "09-28" },
    { id: "pr-intent", name: "客服意图识别", taskId: "text-classification", description: "区分售后、物流与商品咨询", updated: "09-27" },
    { id: "pr-churn", name: "用户流失预测", taskId: "tabular-binary", description: "根据行为特征识别流失风险", updated: "09-25" }
  ],
  runs: [
    { id: "run-1042", name: "安全帽检测 · 基线 02", projectId: "pr-helmet", datasetId: "ds-helmet", taskId: "object-detection", modelId: "yolov8n-pre", status: "运行中", progress: 68, metric: "mAP", score: "0.812", duration: "18 分钟", started: "09-28 14:32", gpu: "GPU 01", epochs: 50, batch: 8, lr: 0.001 },
    { id: "run-1038", name: "安全帽检测 · 基线 01", projectId: "pr-helmet", datasetId: "ds-helmet", taskId: "object-detection", modelId: "yolov8n-pre", status: "已完成", progress: 100, metric: "mAP", score: "0.786", duration: "42 分钟", started: "09-27 10:08", gpu: "GPU 02", epochs: 40, batch: 8, lr: 0.001 },
    { id: "run-1035", name: "客服意图 · 微调 03", projectId: "pr-intent", datasetId: "ds-intent", taskId: "text-classification", modelId: "bert-text", status: "已完成", progress: 100, metric: "F1 分数", score: "0.914", duration: "26 分钟", started: "09-26 16:20", gpu: "GPU 01", epochs: 8, batch: 16, lr: 0.00002 },
    { id: "run-1030", name: "用户流失 · 实验 01", projectId: "pr-churn", datasetId: "ds-churn", taskId: "tabular-binary", modelId: "xgboost-binary", status: "失败", progress: 23, metric: "AUC", score: "—", duration: "4 分钟", started: "09-25 11:42", gpu: "CPU 队列", epochs: 30, batch: 32, lr: 0.001 }
  ],
  services: [
    { id: "svc-intent", name: "客服意图识别服务", runId: "run-1035", status: "运行中", version: "v1", resource: "CPU · 2 核 4 GB", calls: 1268, created: "09-27", history: [
      { time: "09-28 15:42", result: "已完成", latency: "184 ms", source: "在线测试" },
      { time: "09-28 15:38", result: "已完成", latency: "201 ms", source: "接口调用" }
    ] }
  ],
  resources: [
    { id: "gpu-01", name: "GPU 01", model: "RTX 4090", memory: "24 GB", status: "使用中", owner: "安全帽检测", util: 76 },
    { id: "gpu-02", name: "GPU 02", model: "RTX 4090", memory: "24 GB", status: "空闲", owner: "—", util: 0 },
    { id: "gpu-03", name: "GPU 03", model: "A100", memory: "40 GB", status: "维护中", owner: "—", util: 0 }
  ],
  users: [
    { id: "user-admin", name: "平台管理员", account: "admin@example.test", role: "管理员", groupId: "group-admin", status: "启用", grants: [], denies: [], quota: {} },
    { id: "user-lin", name: "林舟", account: "lin@example.test", role: "开发者", groupId: "group-dev", status: "启用", grants: [], denies: [], quota: {} },
    { id: "user-zhou", name: "周宁", account: "zhou@example.test", role: "开发者", groupId: "group-dev", status: "启用", grants: [], denies: ["services.deploy"], quota: { gpu: 1, jobs: 2 } },
    { id: "user-guest", name: "观察员", account: "viewer@example.test", role: "只读", groupId: "group-viewer", status: "启用", grants: [], denies: [], quota: {} }
  ],
  groups: [
    { id: "group-admin", name: "平台管理组", permissions: ["datasets.read", "datasets.write", "train.submit", "models.manage", "services.deploy", "keys.manage", "resources.view"], quota: { gpu: 8, jobs: 20 } },
    { id: "group-dev", name: "研发组", permissions: ["datasets.read", "datasets.write", "train.submit", "models.manage", "services.deploy", "keys.manage", "resources.view"], quota: { gpu: 2, jobs: 4 } },
    { id: "group-viewer", name: "观察组", permissions: ["datasets.read", "resources.view"], quota: { gpu: 0, jobs: 0 } }
  ],
  apiKeys: [],
  nodes: [
    { id: "node-a", name: "训练节点 A", address: "gpu-node-a", status: "已接入", gpus: "RTX 4090 × 2", cpu: "32 核", memory: "128 GB" },
    { id: "node-b", name: "训练节点 B", address: "gpu-node-b", status: "已接入", gpus: "A100 × 1", cpu: "48 核", memory: "256 GB" }
  ],
  annotations: [],
  augmentations: [],
  settings: { registration: true, defaultGroupId: "group-dev", jobLimit: 4, storageLimit: 500 },
  audit: [
    { time: "09-28 14:32", actor: "林舟", action: "提交训练", target: "安全帽检测 · 基线 02", result: "成功" },
    { time: "09-27 10:08", actor: "林舟", action: "提交训练", target: "安全帽检测 · 基线 01", result: "成功" },
    { time: "09-26 16:20", actor: "平台管理员", action: "发布模型", target: "客服意图识别 v1", result: "成功" }
  ]
};
