# Setup 3X-UI 智能体执行说明

这是给 AI 智能体读取的执行规范。Codex、Claude Code、Hermes、OpenCloud、Cursor 或其他代码智能体在处理本仓库时，都应该优先遵守这份文件。

## 任务目标

本仓库用于在 VPS 上安装和管理 3X-UI 面板，创建 VLESS Reality 入站，生成后台资料，并给客户添加节点、导出链接和二维码。

只有当用户明确提出下面这类需求时，才使用这个工作流：

- 安装 3X-UI 或 X-UI 面板。
- 搭建 3X-UI 后台。
- 生成 3X-UI 后台管理 Word 文档。
- 创建或检查 VLESS Reality 入站。
- 给客户新增 3X-UI 客户端。
- 生成 VLESS 链接、订阅链接或二维码。
- 把客户节点资料导出成 Word 文档。

如果用户只是询问普通 Linux 运维、网站部署、数据库安装、Docker 服务或旧版一键 VLESS 脚本，不要默认使用本工作流，除非用户明确要求 3X-UI 面板。

## 必要输入

安装面板前必须确认用户已经提供：

- VPS 主机地址，可以是 IP 或域名。
- SSH 用户名，通常是 `root`。
- SSH 密码。
- SSH 端口，默认 `22`。
- 系统版本或系统名称。

添加客户前必须确认：

- `3xui-panel-info.json` 的路径，或者已有面板的后台地址、用户名和密码。
- 客户名称。
- 需要绑定的入站，默认优先使用 VLESS `443`。

可以询问但不是必须的信息：

- 服务器名称。
- 客户或项目名称。
- 客户有效期。
- 客户流量限制。
- 客户备注或分组。
- 输出目录。

如果缺少必要输入，先向用户询问，不要猜测密码、主机、用户名或客户名称。

## 安全边界

这个工作流会修改远程服务器，包括安装 3X-UI、创建面板配置、创建 VLESS Reality 入站，以及在面板中新增客户。

执行前应当让用户知道这是一次真实服务器变更，不是单纯生成文件。

必须把以下内容视为敏感信息：

- SSH 密码。
- VPS 真实 IP 或域名。
- 3X-UI 后台地址、用户名、密码、API token。
- `3xui-panel-info.json`。
- `3xui-management.docx`。
- 客户节点链接。
- 客户订阅链接。
- 节点二维码和订阅二维码。
- `client-summary.json`。
- `client-node.docx`。
- 安装日志和验证日志。
- 私钥、证书、`.env` 文件。

不要把这些内容提交到 Git，不要上传到公开仓库，不要在最终回答里过度展开完整凭据。后台资料只给管理员；客户只接收自己的节点或订阅资料。

## 推荐命令

安装面板时优先使用环境变量传递 SSH 密码：

```bash
VPS_PASSWORD='<SSH_PASSWORD>' python3 scripts/setup_3xui.py \
  --host 192.0.2.10 \
  --user root \
  --ssh-port 22 \
  --system 'Ubuntu-22.04-x64' \
  --server-name '美国住宅1号' \
  --owner '客户/项目名称' \
  --output-dir "/absolute/path/to/output-folder"
```

如果用户提供了非默认 SSH 端口，必须传入：

```bash
--ssh-port 用户提供的端口
```

不要把 SSH 密码写进命令参数、文件或最终回复中。

添加客户时使用：

```bash
python3 scripts/add_3xui_client.py \
  --panel-info "/absolute/path/to/3xui-panel-info.json" \
  --client-name "customer-a" \
  --duration "30天" \
  --inbound-port 443
```

重新生成后台 Word 文档时使用：

```bash
python3 scripts/make_3xui_doc.py \
  --panel-info "/absolute/path/to/3xui-panel-info.json" \
  --server-name "美国住宅1号" \
  --owner "张三"
```

## 标准安装流程

1. 收集并确认 VPS 主机、SSH 用户名、SSH 密码、SSH 端口和系统版本。
2. 如果用户说服务器已在使用或可能已有面板，先确认是否允许重装。
3. 明确告知用户该操作会修改远程服务器。
4. 创建新的输出目录，例如 `outputs/3xui-<host>-<timestamp>`。
5. 运行 `scripts/setup_3xui.py`，不要临时重写安装逻辑。
6. 等待脚本完成安装、默认入站创建和验证。
7. 检查输出目录是否包含关键文件。
8. 在最终回复中给出后台 Word 文档和 panel-info 文件链接，并清楚标注后台凭据只给管理员。

## 标准加客户流程

1. 确认 `3xui-panel-info.json` 路径或面板登录信息。
2. 收集客户名称、有效期、流量限制、备注、分组和目标入站。
3. 运行 `scripts/add_3xui_client.py`。
4. 检查输出目录是否包含 `vless-link.txt`、`vless-qr.png`、`client-summary.json` 和 `client-node.docx`。
5. 如果生成了订阅链接，正式长期客户优先发订阅链接或订阅二维码。
6. 如果没有订阅链接，或只是快速测试，则发送 VLESS 链接或二维码。

## 脚本行为摘要

`setup_3xui.py` 会执行：

- 使用 `ssh` 和 `expect` 连接 VPS。
- 运行官方 3X-UI 安装器。
- 解析后台地址、用户名、密码、端口、WebBasePath 和 API token。
- 登录面板。
- 默认创建 VLESS Reality 入站。
- 保存安装日志和验证日志。
- 生成后台管理 Word 文档。

`add_3xui_client.py` 会执行：

- 登录 3X-UI 面板。
- 选择指定入站或优先选择 VLESS `443`。
- 创建客户账号。
- 导出 VLESS 链接和二维码。
- 尝试导出订阅链接和二维码。
- 生成客户节点 Word 文档。

`make_3xui_doc.py` 会执行：

- 读取 `3xui-panel-info.json`。
- 更新服务器名称和使用对象。
- 重新生成后台管理 Word 文档。

## 期望输出文件

安装成功后，输出目录通常应该包含：

- `3xui-panel-info.json`
- `3xui-management.docx`
- `install-3xui.log`
- `verify.log`

添加客户成功后，客户输出目录通常应该包含：

- `vless-link.txt`
- `vless-qr.png`
- `client-summary.json`
- `client-node.docx`

可能还会包含：

- `subscription-links.txt`
- `subscription-qr.png`

## 最终回复要求

安装面板成功后，最终回复应该包含：

- `3xui-management.docx` 的本地文件链接。
- `3xui-panel-info.json` 的本地文件链接。
- 管理后台 URL、用户名和密码。
- 明确提醒：这些是管理员后台凭据，不要发给客户。

添加客户成功后，最终回复应该包含：

- 客户输出目录。
- `client-node.docx` 的本地文件链接。
- 直接展示 `vless-qr.png`，如果界面支持图片展示。
- 如果有订阅二维码，说明正式客户优先发订阅二维码或订阅链接。
- 如果没有订阅二维码，说明可发送 VLESS 二维码或链接。

如果失败，最终回复应该包含：

- 失败发生在哪一步。
- 已检查过哪些日志。
- 下一步建议用户提供或确认什么信息。
- 不要假装安装或加客户成功。

## 失败处理

优先查看本地输出目录里的日志：

1. `install-3xui.log`
2. `verify.log`
3. `client-summary.json`，如果客户创建流程部分成功

常见问题：

- SSH 密码错误：确认密码、用户名、端口是否正确。
- SSH 端口不通：确认 VPS 安全组、防火墙、运营商面板是否放行。
- 官方 3X-UI 安装器交互变化：更新 `expect` 交互逻辑。
- 面板登录失败：确认 URL、用户名、密码和 WebBasePath 是否有效。
- 入站不存在：先创建 VLESS Reality 入站，或传入正确 `--inbound-id`。
- 订阅链接没有生成：面板可能没有配置订阅地址，可以改发 VLESS 链接或二维码。

## Git 与发布规则

提交代码前必须检查：

```bash
git status --short
```

不要提交：

- `outputs/`
- `clients/`
- 真实 `3xui-panel-info.json`
- 后台 Word 文档
- 客户 Word 文档
- 节点链接
- 订阅链接
- 二维码
- 日志
- `.env`
- 私钥或证书

如果需要更新仓库说明，保持 `README.md`、`AGENTS.md`、`SKILL.md` 的核心流程一致。

## 各智能体入口

- Codex/OpenAI：读取 `SKILL.md`。
- Claude Code：读取 `CLAUDE.md`，再导入 `AGENTS.md`。
- Hermes：读取 `HERMES.md`，再参考 `AGENTS.md`。
- OpenCloud：读取 `OPENCLOUD.md`，再参考 `AGENTS.md`。
- OpenClaw：读取 `OPENCLAW.md`，再参考 `AGENTS.md`。
- Cursor：读取 `.cursor/rules/setup-3xui.mdc`；旧版可读取 `.cursorrules`。
- Windsurf：读取 `.windsurf/rules/setup-3xui.md`，也可以读取根目录 `AGENTS.md`；旧版可读取 `.windsurfrules`。
- Cline：读取 `.clinerules/setup-3xui.md`。
- Roo Code：读取 `.roo/rules/setup-3xui.md`。
- Gemini CLI：读取 `GEMINI.md`，必要时运行 `/memory reload`。
- GitHub Copilot：读取 `.github/copilot-instructions.md`。
- Aider：读取 `CONVENTIONS.md`；`.aider.conf.yml` 已配置默认读取 `AGENTS.md` 和 `CONVENTIONS.md`。

如果某个智能体不支持自动导入文件，就把本文件内容作为项目级/system 指令提供给它。

其他智能体的中文使用说明见 `docs/OTHER_AGENTS_CN.md`。
