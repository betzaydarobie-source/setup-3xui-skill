# Aider 使用约定

本仓库用于安装和管理 3X-UI 面板，并生成后台资料和客户节点资料。

Aider 使用本项目时，请同时阅读 `AGENTS.md`。本文件用于让 Aider 在每次会话中保持这些约定：

- 使用 `scripts/setup_3xui.py` 安装面板，不要临时重写安装脚本。
- 使用 `scripts/add_3xui_client.py` 添加客户，不要临时重写面板 API 逻辑。
- 使用 `scripts/make_3xui_doc.py` 重新生成后台 Word 文档。
- 运行前确认必要的 VPS 或面板信息。
- 优先用 `VPS_PASSWORD` 环境变量传递 SSH 密码。
- 不要提交 `outputs/`、`clients/`、后台资料、客户资料、节点链接、二维码、日志、私钥、证书或 `.env` 文件。
- 修改脚本后至少运行 `python3 -m py_compile scripts/*.py`。
- 修改说明后保持 `README.md`、`AGENTS.md`、`SKILL.md` 的核心流程一致。
