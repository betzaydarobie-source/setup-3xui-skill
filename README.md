# Setup 3X-UI Skill 中文说明

这是一个可复用的 AI 智能体工作流，用来在 VPS 上安装和管理 3X-UI 面板，创建默认 VLESS Reality 入站，生成后台管理资料，并为客户添加节点、导出 VLESS/订阅链接和二维码。

这个项目既可以作为 Codex/OpenAI Skill 使用，也可以给 Claude Code、Hermes、OpenCloud、Cursor、Windsurf、Cline、Roo Code、Gemini CLI、GitHub Copilot 和 Aider 等能读取项目说明文件的智能体使用。

更多智能体中文用法见 `docs/OTHER_AGENTS_CN.md`。

## 适用场景

当用户明确提出下面这类需求时，可以使用这个项目：

- 安装 3X-UI 或 X-UI 面板。
- 创建 3X-UI 后台管理资料。
- 在面板里创建默认 VLESS Reality 入站。
- 给客户新增 3X-UI 客户端账号。
- 为客户生成 VLESS 链接、订阅链接或二维码。
- 把后台资料导出成 Word 文档。

不建议把它用于泛泛的服务器运维、网站部署、数据库安装或旧版一键 VLESS 脚本部署。这个项目的目标很明确：管理 3X-UI 面板和客户节点。

## 文件结构

```text
setup-3xui/
├── SKILL.md                         # Codex/OpenAI Skill 入口
├── AGENTS.md                        # 通用智能体执行说明
├── CLAUDE.md                        # Claude Code 入口，指向 AGENTS.md
├── HERMES.md                        # Hermes 入口，指向 AGENTS.md
├── OPENCLOUD.md                     # OpenCloud 入口，指向 AGENTS.md
├── OPENCLAW.md                      # OpenClaw/兼容入口，指向 AGENTS.md
├── GEMINI.md                        # Gemini CLI 入口，指向 AGENTS.md
├── CONVENTIONS.md                   # Aider 只读约定
├── README.md                        # 当前中文说明
├── .gitignore                       # 防止提交敏感部署产物
├── .aider.conf.yml                  # Aider 默认读取的说明文件
├── .cursorrules                     # Cursor 旧版兼容入口
├── .windsurfrules                   # Windsurf 旧版兼容入口
├── .cursor/rules/setup-3xui.mdc     # Cursor Project Rule
├── .windsurf/rules/setup-3xui.md    # Windsurf Workspace Rule
├── .clinerules/setup-3xui.md        # Cline Rule
├── .roo/rules/setup-3xui.md         # Roo Code Rule
├── .github/copilot-instructions.md  # GitHub Copilot 仓库说明
├── docs/
│   └── OTHER_AGENTS_CN.md           # 其他智能体中文使用说明
├── agents/
│   └── openai.yaml                  # Codex/OpenAI 界面展示信息
└── scripts/
    ├── setup_3xui.py                # 安装 3X-UI 面板并生成后台资料
    ├── add_3xui_client.py           # 给面板添加客户并导出链接/二维码
    ├── make_3xui_doc.py             # 从 panel-info 重新生成 Word 文档
    └── common_3xui.py               # 通用工具函数
```

## 本地依赖

运行脚本的本地机器需要具备这些工具：

- `python3`
- `ssh`
- `expect`

生成二维码时脚本会自动安装 Python 包 `segno`。脚本通过 SSH 连接远程 VPS，所以本地网络需要能访问 VPS 的 SSH 端口。

## 需要准备的信息

安装面板前需要用户提供：

- VPS 的 IP 地址或域名。
- SSH 用户名，通常是 `root`。
- SSH 密码。
- SSH 端口，默认 `22`。
- 系统版本，例如 `Ubuntu-22.04-x64`。

可选信息：

- 服务器名称。
- 客户或项目名称。
- 面板端口，不提供时随机生成。
- 默认 VLESS Reality 入站端口，默认 `443`。
- 输出目录。

## 安装 3X-UI 面板

建议使用环境变量 `VPS_PASSWORD` 传递密码，避免把密码写进命令历史或进程参数里。

```bash
VPS_PASSWORD='这里换成你的SSH密码' python3 scripts/setup_3xui.py \
  --host 192.0.2.10 \
  --user root \
  --ssh-port 22 \
  --system 'Ubuntu-22.04-x64' \
  --server-name '美国住宅1号' \
  --owner '客户/项目名称' \
  --output-dir "$(pwd)/outputs/3xui-192.0.2.10-$(date +%Y%m%d-%H%M%S)"
```

脚本会自动：

1. 通过 SSH 登录 VPS。
2. 执行官方 3X-UI 安装器。
3. 设置或生成面板端口。
4. 默认进行内核网络优化（借鉴自 setup-vps 的 `vless.sh`）：开启 BBR + fq、放大 TCP 缓冲、TCP Fast Open、内存与文件描述符调优，写入 `/etc/sysctl.d/99-xray-optimization.conf` 并加载 `tcp_bbr`/`sch_fq`。官方安装器本身不调内核，这一步让面板节点开箱即拥有和一键 VLESS 脚本同级的速度。传 `--no-optimize` 可跳过。
5. 默认部署 Karing 兼容订阅适配器：在订阅服务（`:2096`）前起一个纯 stdlib 反向代理 `:2097`，把 Karing 更新检查的 HEAD 请求改成返回 200（原版订阅服务对 HEAD 返回 404），并从 Clash YAML 剥掉 `packet-encoding: none`；同时开启订阅服务并把 `subURI`/`subClashURI` 设成 `:2097`，让面板对每个客户端自动给出 `:2097` 订阅地址。订阅端口 `subPort` 保持 `2096` 不变——**绝不可改成 `2097`**（会和适配器冲突导致 x-ui 崩溃、客户掉线）。传 `--no-karing-adapter` 可跳过。
6. 保存后台地址、用户名、密码、端口和 API token。
7. 默认创建 VLESS Reality `443` 入站，除非传入 `--no-default-inbound`。
8. 生成 `3xui-panel-info.json`、`install-3xui.log`、`optimize.log`、`karing-adapter.log`、`verify.log` 和 `3xui-management.docx`。

> 说明：内核优化和 Karing 适配器都是借鉴/扩展同系列 setup-vps 思路移植进来的增强，上游 `mhsanaei/3x-ui` 官方安装器本身并不包含它们。如不需要，安装时分别加 `--no-optimize` / `--no-karing-adapter` 即可跳过。

如果服务器已经在使用，或用户说可能已有面板，必须先确认是否允许重装。安装 3X-UI 可能替换已有服务或配置。

## 给已有服务器单独补网络优化（不重装）

如果服务器已经装好 3X-UI、客户也在用了，只想补上 BBR/TCP 内核优化，用这个脚本，不需要重装：

```bash
VPS_PASSWORD='这里换成你的SSH密码' python3 scripts/optimize_3xui.py \
  --panel-info "/absolute/path/to/3xui-panel-info.json"
```

它只修改内核 sysctl 参数并加载 bbr/fq 模块，**不会登录面板，也不会改动 xray 配置、UUID、端口、Reality 密钥或任何 VLESS/订阅链接**，所以已经发给客户的链接继续有效。脚本会：

1. 先把已有的 `99-xray-optimization.conf` 备份成 `.bak`。
2. 应用优化（BBR + fq + TCP / 内存 / 文件描述符调优）。
3. 确认 `x-ui` 服务仍在运行。
4. 写入 `optimize-<时间戳>.log`。

想回滚就加 `--revert`（删除优化文件，拥塞算法重置为 cubic）。也可以不带 `--panel-info`，改用 `--host / --user / --ssh-port` 直接指定服务器。

## 重新生成后台 Word 文档

```bash
python3 scripts/make_3xui_doc.py \
  --panel-info '/absolute/path/to/3xui-panel-info.json' \
  --server-name '美国住宅1号' \
  --owner '张三'
```

Word 文档会包含服务器名称、使用对象、服务器 IP、系统版本、SSH 用户名/端口、管理后台地址、后台用户名和后台密码。现在**默认也会写入 SSH 密码**（加 `--omit-ssh-password` 可不写）——因此这份文档等于服务器最高权限,务必只给管理员、绝不发客户。文档默认还会按 `<服务器名>-3X-UI后台资料.docx` 归档一份到 `~/Documents/VPS`(用 `--doc-archive-dir` 改目录,留空则关闭)。

## 添加客户节点

```bash
python3 scripts/add_3xui_client.py \
  --panel-info '/absolute/path/to/3xui-panel-info.json' \
  --client-name 'customer-a' \
  --duration '30天' \
  --inbound-port 443
```

常用参数：

- `--days 7`、`--duration '1个月'` 或 `--expires-at 2026-06-30` 设置到期时间。
- `--traffic-gb 50` 设置流量限制；不传或传 `0` 表示不限流量。
- `--comment '试用'` 写入备注。
- `--group 'TikTok'` 写入客户分组。
- `--inbound-id N` 指定入站；否则优先使用 VLESS `443`。

输出通常包含：

- `vless-link.txt`
- `vless-qr.png`
- `subscription-links.txt`，如果面板提供订阅地址
- `subscription-qr.png`，如果面板提供订阅地址
- `client-summary.json`
- `client-node.docx`

正式长期客户优先发订阅二维码或订阅链接；快速测试或不支持订阅的客户端，可以发 VLESS 二维码或 VLESS 链接。

## 给 Codex 使用

把这个目录同步到 Codex skills 目录：

```bash
mkdir -p ~/.codex/skills/setup-3xui
rsync -a --exclude .git --exclude outputs ./ ~/.codex/skills/setup-3xui/
```

之后在 Codex 里可以用类似这样的请求触发：

```text
帮我给这台 VPS 安装 3X-UI 面板，并生成后台资料。
```

Codex 会读取 `SKILL.md`，然后优先调用 `scripts/setup_3xui.py`、`scripts/add_3xui_client.py` 或 `scripts/make_3xui_doc.py`。

## 给其他智能体使用

本仓库提供这些入口：

- Claude Code：`CLAUDE.md`
- Hermes：`HERMES.md`
- OpenCloud：`OPENCLOUD.md`
- OpenClaw：`OPENCLAW.md`
- Cursor：`.cursor/rules/setup-3xui.mdc`，并保留 `.cursorrules` 兼容入口
- Windsurf：`.windsurf/rules/setup-3xui.md`，并保留 `.windsurfrules` 兼容入口
- Cline：`.clinerules/setup-3xui.md`
- Roo Code：`.roo/rules/setup-3xui.md`
- Gemini CLI：`GEMINI.md`
- GitHub Copilot：`.github/copilot-instructions.md`
- Aider：`CONVENTIONS.md` 和 `.aider.conf.yml`

通用原则：如果某个智能体不会自动读取这些文件，就把 `AGENTS.md` 的内容作为项目说明或 system prompt 提供给它。

## 安全规则

使用这个项目时，请遵守这些规则：

- 不要把 SSH 密码写进仓库文件。
- 不要提交 `.env` 文件。
- 不要提交 `outputs/`、`clients/` 或真实运行产物。
- 不要提交 `3xui-panel-info.json`、后台 Word 文档、客户 Word 文档、节点链接、二维码、配置、日志、私钥或证书。
- 后台地址、后台用户名和后台密码只给管理员保存，不要发给客户。
- 客户只应接收自己的订阅二维码/链接或 VLESS 二维码/链接。
- 不要在用户没有明确授权的情况下连接或修改任何服务器。

本仓库的 `.gitignore` 已经默认排除了常见敏感文件，但使用前仍然应该检查 `git status`，确认没有意外文件被加入。

## 故障排查

如果安装失败，优先检查输出目录里的文件：

- `install-3xui.log`
- `verify.log`

常见问题：

- SSH 密码错误：确认密码、用户名、端口是否正确。
- SSH 端口不通：确认 VPS 安全组、防火墙、运营商面板是否放行。
- 官方 3X-UI 安装器变更：需要更新安装交互解析或手动确认新的安装流程。
- 面板登录失败：确认 `3xui-panel-info.json` 里的 URL、用户名、密码是否仍有效。
- 客户订阅链接缺失：部分面板配置没有暴露订阅 URL，可以改发 VLESS 链接或二维码。
