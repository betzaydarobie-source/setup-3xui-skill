# 其他智能体中文使用说明

本项目已经提供多种智能体入口。核心原则是：所有智能体都应该优先读取 `AGENTS.md`，执行时调用仓库里的脚本，不要临时重写 3X-UI 安装流程或面板 API 逻辑。

## 通用方式

适用于任何能读取文件、执行命令的智能体：

1. 打开本仓库根目录。
2. 让智能体先读取 `AGENTS.md`。
3. 安装面板时提供 VPS IP/域名、SSH 用户名、SSH 密码、SSH 端口和系统版本。
4. 添加客户时提供 `3xui-panel-info.json` 路径、客户名称和可选有效期/流量限制。
5. 要求它使用 `scripts/setup_3xui.py`、`scripts/add_3xui_client.py` 或 `scripts/make_3xui_doc.py`。
6. 任务完成后，让它返回必要的 Word 文档、二维码、链接或输出目录。

如果某个智能体不会自动读取项目说明文件，就把 `AGENTS.md` 的内容复制给它，作为项目级说明或 system prompt。

## Cursor

已提供：

- `.cursor/rules/setup-3xui.mdc`
- `.cursorrules`

推荐使用新版 Cursor Project Rules，也就是 `.cursor/rules/setup-3xui.mdc`。`.cursorrules` 只是兼容旧版。

使用方式：

1. 用 Cursor 打开仓库。
2. 确认 Cursor 已加载项目规则。
3. 对 Cursor 说：`请根据 AGENTS.md 帮我安装 3X-UI 面板。`
4. 提供 VPS 信息。

## Claude Code

已提供：

- `CLAUDE.md`
- `AGENTS.md`

使用方式：

1. 用 Claude Code 打开仓库。
2. 确认 Claude Code 已读取 `CLAUDE.md` 和 `AGENTS.md`。
3. 提供 VPS 或面板信息。
4. 要求它调用仓库脚本完成任务。

## Hermes

已提供：

- `HERMES.md`
- `AGENTS.md`

如果 Hermes 支持项目说明文件导入，请导入 `HERMES.md` 或 `AGENTS.md`。如果不支持，就把 `AGENTS.md` 的内容作为项目级提示词或 system 指令提供给 Hermes。

## OpenCloud

已提供：

- `OPENCLOUD.md`
- `AGENTS.md`

如果 OpenCloud 支持项目说明文件导入，请导入 `OPENCLOUD.md` 或 `AGENTS.md`。如果不支持，就把 `AGENTS.md` 的内容作为项目级提示词或 system 指令提供给 OpenCloud。

## Windsurf

已提供：

- `.windsurf/rules/setup-3xui.md`
- `.windsurfrules`
- `AGENTS.md`

Windsurf Cascade 可以读取 `.windsurf/rules/` 里的规则，也可以读取 `AGENTS.md`。

## Cline

已提供：

- `.clinerules/setup-3xui.md`

使用方式：

1. 用 VS Code 打开仓库。
2. 在 Cline 里确认 `.clinerules/setup-3xui.md` 已启用。
3. 要求 Cline 阅读 `AGENTS.md`。
4. 提供 VPS 或面板信息并让它运行对应脚本。

## Roo Code

已提供：

- `.roo/rules/setup-3xui.md`

使用方式：

1. 用 VS Code 打开仓库。
2. 在 Roo Code 中确认项目规则已加载。
3. 要求它阅读 `AGENTS.md`。
4. 提供 VPS 或面板信息并执行对应脚本。

## Gemini CLI

已提供：

- `GEMINI.md`

使用方式：

```bash
gemini
```

如果刚修改过说明文件，可以在 Gemini CLI 里执行：

```text
/memory reload
```

然后输入：

```text
请阅读 GEMINI.md 和 AGENTS.md，按照仓库流程帮我安装 3X-UI 面板或添加客户节点。
```

## GitHub Copilot

已提供：

- `.github/copilot-instructions.md`

使用方式：

1. 在 VS Code、Visual Studio、JetBrains 或 GitHub Copilot Chat 中打开仓库。
2. 确认 Copilot custom instructions 已启用。
3. 要求 Copilot 阅读 `AGENTS.md`。
4. 提供 VPS 或面板信息，并让它使用脚本执行。

注意：Copilot 更适合辅助修改说明和脚本；如果要真正连接 VPS，需要确保当前环境允许它执行本地命令。

## Aider

已提供：

- `CONVENTIONS.md`
- `.aider.conf.yml`

`.aider.conf.yml` 会让 Aider 默认读取 `AGENTS.md` 和 `CONVENTIONS.md`。

也可以手动启动：

```bash
aider --read AGENTS.md --read CONVENTIONS.md
```

然后让 Aider 根据 `AGENTS.md` 执行任务或修改脚本。

## 其他没有专属入口的智能体

如果某个智能体没有固定的项目规则文件，例如某些远程编程智能体或网页端智能体，可以使用通用方式：

1. 把仓库地址给它。
2. 明确要求它先阅读 `AGENTS.md`。
3. 告诉它不要提交 `outputs/`、`clients/`、后台资料、客户资料、节点链接、二维码、日志、私钥、证书或 `.env` 文件。
4. 要求它使用仓库里的脚本。

推荐给它的中文提示：

```text
请先阅读仓库根目录的 AGENTS.md。这个仓库用于安装和管理 3X-UI 面板，并生成后台资料和客户节点资料。你必须使用仓库 scripts/ 里的脚本，不要临时重写部署或面板 API 流程。运行前向我确认必要的 VPS 或面板信息。不要提交或公开 outputs、clients、后台资料、客户资料、节点链接、二维码、日志、私钥、证书或 .env 文件。
```

## 安全提醒

不管使用哪个智能体，都必须遵守：

- 不公开 SSH 密码。
- 不公开 3X-UI 后台凭据。
- 不公开节点链接。
- 不公开二维码。
- 不提交真实部署产物。
- 不在未经用户明确授权时连接或修改服务器。
