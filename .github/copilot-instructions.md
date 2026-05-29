# GitHub Copilot 仓库说明

本仓库用于安装和管理 3X-UI 面板，并生成后台资料和客户节点资料。

请优先阅读 `AGENTS.md`，并把它作为完整执行规范。本文只给 GitHub Copilot 提供仓库级入口。

关键要求：

- 安装面板必须调用 `scripts/setup_3xui.py`。
- 添加客户必须调用 `scripts/add_3xui_client.py`。
- 重新生成后台文档必须调用 `scripts/make_3xui_doc.py`。
- 运行前确认用户提供必要的 VPS 或面板信息。
- 优先使用 `VPS_PASSWORD` 环境变量，不要把密码写进文件。
- 不要提交 `outputs/`、`clients/`、后台资料、客户资料、节点链接、二维码、日志、私钥、证书或 `.env` 文件。
- 成功后只返回必要产物，并提醒后台凭据只给管理员，客户只接收自己的节点或订阅资料。
