# Roo Code 规则

本仓库用于安装和管理 3X-UI 面板，并生成后台资料和客户节点资料。

请把 `AGENTS.md` 作为主规则文件。安装面板时调用 `scripts/setup_3xui.py`，添加客户时调用 `scripts/add_3xui_client.py`，不要临时改写一套新的部署或面板 API 流程。

必须遵守：

- 缺少 VPS IP/域名、SSH 用户名或 SSH 密码时，先询问用户。
- SSH 端口默认 `22`，用户提供其他端口时传入 `--ssh-port`。
- 优先使用 `VPS_PASSWORD` 环境变量传递密码。
- 不要提交或公开 `outputs/`、`clients/`、后台资料、客户资料、节点链接、二维码、日志、私钥、证书和 `.env` 文件。
- 添加客户失败时先检查面板登录、目标入站和输出日志。
