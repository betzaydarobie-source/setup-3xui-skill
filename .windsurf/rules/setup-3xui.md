---
trigger: always_on
---

# Windsurf Cascade 规则

本仓库用于安装和管理 3X-UI 面板，并生成后台资料和客户节点资料。

请优先阅读并遵守 `AGENTS.md`。安装面板时使用 `scripts/setup_3xui.py`，添加客户时使用 `scripts/add_3xui_client.py`，重新生成后台文档时使用 `scripts/make_3xui_doc.py`。不要临时重写部署或面板 API 流程。

关键规则：

- 运行前确认用户提供必要的 VPS 或面板信息。
- 优先使用 `VPS_PASSWORD` 环境变量传递 SSH 密码。
- 不要提交 `outputs/`、`clients/`、后台资料、客户资料、节点链接、二维码、日志、私钥、证书或 `.env` 文件。
- 部署失败时先查看输出目录里的日志，再给出下一步排查建议。
