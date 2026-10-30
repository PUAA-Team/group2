# Linux 部署与本机 GPU 联调

2026-10-29，当前版本已通过 Docker Compose 部署到北京 Linux 服务器，已连接本机 RTX4060 并完成一次真实图像分类 GPU 训练。缓存优先调度、OSS 和传输路径优化留在后续待办。

- [部署与验收计划](./部署与验收计划.md)：部署范围、连接方式、文件归属、GPU 交接和通过条件。
- [运行与验收](./运行与验收.md)：网址、账号方式、重启、Worker、备份恢复、证书和已知限制。
- [服务器监控](./服务器监控.md)：Komari Agent安装、自动发现、禁用远程控制及服务操作。
- [验收结果](./验收结果.json)、[页面实拍](./previews/ReadMe.md)：真实CUDA训练、版本、权限、63项Windows及63项Linux后端测试、85项前端测试和12项浏览器检查。
- [部署包构建脚本](../../scripts/package_server_release.py)：仅打包控制端、真实前端、Worker 源码及必要运行文件，并生成文件摘要。
- [Compose配置](../../deploy/server/compose.yaml)、[应用镜像](../../deploy/server/Dockerfile)、[证书续期](../../deploy/server/renew_certificate.py)。
- 当前 API 继续使用 [stage11 OpenAPI](../stage11/openapi.json)，本阶段准备工作不新增接口或数据库结构。

## 当前状态

网站：`https://47.93.115.188:5488/`；管理员账号 `lixu`，初始密码保存在操作员本机 D 盘私有登录文件，不写入文档和发布包。当前账号由管理员创建，自助注册尚未实现。

本机 SSH 别名 `training-demo`，已有 Ed25519 公钥登录通过。宿主为 Debian13.4、4核、约15GiB内存、40GB根盘；当前约34GB可用。Docker26.1.5、Compose2.26.1、Buildx0.13.1；应用镜像Python3.12.16，PostgreSQL17.11，迁移0003_jobs。正式发布目录 `/srv/model-platform/releases/20261029-04`，`current` 指向该目录。数据库只在容器内部开放，应用回环端口18000，公网入口5488使用可信IP证书。

云端节点 `nod_0d8d563dfbaf44179badcf17b3848d54` 已在线，Worker使用D盘独立目录及既有LLM环境。任务 `job_db847a8e9ad54ddfad8d1933938a3daa` 实际使用CUDA，18条训练、6条验证、3个epoch，模型产物回传并校验，任务结束后GPU占用释放。教学几何样本用于验收流程，准确率0.5不代表业务模型效果。

本机8000应用和8765原型保留。旧Worker35956及Qwen子进程35640已通过CIM核实不存在；旧节点暂停，旧服务保留停止中和失联占用，未伪造回执或自动清理历史执行。

## 本轮记录

准备目录：`D:/model-training-demo/server-deploy-prep-20261029`。索引与待办修改前备份在其 `backups/20261029-163235`。

本机SSH配置和known_hosts修改前备份在同目录 `ssh-backup-20261029`。只追加training-demo条目，保留其他主机；服务器authorized_keys追加公钥，若原文件存在则备份为同目录authorized_keys.before-training-demo-20261029。服务器Ed25519主机指纹为 `SHA256:wHjR/TUfvFQAzWy+1pFT4/NjJhRnxO9QwkO/zKsFtfw`，首次使用记录后再次核对。

数据库与存储备份仅保留服务器 `/srv/model-platform/backups/post-first-gpu-20261029`，用户明确选择不下载本机。部署包、公开镜像、校验安装包和本机验收记录保留在准备目录；没有安装本机Docker、升级Anaconda或修改驱动。

IP证书有效至2026-11-05，已通过续期演练并启用每天两次的定时检查。初次签发曾因服务器外网超时使用受限临时转发，后续直连演练通过；临时本机代理及SSH通道已关闭。多Worker并行、长期稳定性、整机回收恢复、智能辅助及自助注册仍未验收或实现。
