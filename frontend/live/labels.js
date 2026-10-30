const actions = {
  "auth.login": "登录", "auth.logout": "退出登录", "auth.register": "邀请注册", "users.profile": "修改个人资料", "users.password": "修改密码",
  "users.create": "新增用户", "users.update": "配置用户", "groups.create": "新增用户组", "groups.update": "配置用户组", "invitations.create": "创建注册邀请",
  "workspaces.create": "创建空间", "workspaces.update": "修改空间", "members.update": "调整空间成员", "members.remove": "移除空间成员",
  "models.create": "登记模型", "models.update": "修改模型", "model_versions.create": "登记模型版本", "datasets.create": "新增数据集", "datasets.update": "修改数据集", "dataset_versions.create": "导入数据版本",
  "projects.create": "新建项目", "jobs.create": "创建作业", "jobs.update": "编辑草稿", "jobs.submit": "提交作业", "jobs.stop": "停止作业", "presets.create": "添加示例资产",
  "resources.enrollment.create": "生成接入命令", "resources.enrollment.revoke": "撤销接入码", "resources.register": "计算节点接入", "resources.update": "配置节点", "resources.probe": "探测硬件", "resources.revoke": "撤销节点", "resources.local.stop": "停止本机Worker",
  "settings.update": "修改系统设置", "model_connections.create": "新增模型连接", "model_connections.update": "配置模型连接", "model_connections.test": "测试模型连接", "service_keys.create": "创建API密钥", "service_keys.revoke": "撤销API密钥",
};
export const actionLabel = action => actions[action] || action;
