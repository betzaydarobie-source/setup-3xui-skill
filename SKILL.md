---
name: setup-3xui
description: Install and manage 3X-UI panels for VPS-based VLESS Reality services. Use when the user provides a VPS IP/host, SSH username, password, SSH port, and system version and asks Codex to 搭建 3X-UI, install a 3X-UI/X-UI panel, create a backend management Word document, add a customer/client node, associate a client with an inbound, generate VLESS/subscription links, or create QR codes for customers.
---

# Setup 3X-UI

Use this skill for the newer 3X-UI panel workflow, not the older direct one-command VLESS script. The panel is the administrator backend; customers should receive only their own VLESS link, subscription link, or QR code.

## Install A Panel

Ask for any missing VPS host/IP, SSH username, SSH password, SSH port, and system version. Prefer `VPS_PASSWORD` over command-line password arguments.

```bash
VPS_PASSWORD='<SSH_PASSWORD>' python3 scripts/setup_3xui.py \
  --host 192.0.2.10 \
  --user root \
  --ssh-port 22 \
  --system 'Ubuntu-22.04-x64' \
  --server-name '美国住宅1号' \
  --owner '客户/项目名称' \
  --output-dir '/absolute/path/to/outputs/3xui-192.0.2.10-YYYYMMDD-HHMMSS'
```

What the script does:

- Logs in over SSH and runs the official 3X-UI installer.
- Uses SQLite, a generated or provided panel port, and Let's Encrypt IP HTTPS when available.
- Applies kernel network tuning by default (borrowed from the setup-vps `vless.sh`): enables BBR + fq, enlarges TCP buffers, turns on TCP Fast Open, and sets memory/file-descriptor limits via `/etc/sysctl.d/99-xray-optimization.conf`. The official 3X-UI installer does NOT tune the kernel, so this is what gives a fresh panel node the same open-the-box speed as the one-click VLESS script. Pass `--no-optimize` to skip it.
- Saves the generated admin URL, username, password, panel port, and API token.
- Creates a default VLESS Reality inbound on `443` unless `--no-default-inbound` is passed.
- Writes `3xui-panel-info.json`, `install-3xui.log`, `optimize.log`, `verify.log`, and `3xui-management.docx`. The management doc includes the SSH password by default (`--omit-ssh-password` to skip) and a named copy (`<server>-3X-UI后台资料.docx`) is archived to `~/Documents/VPS` (`--doc-archive-dir` to change, empty to disable).

If the user says the server is already in use or might already have a panel, confirm before reinstalling because installing can replace the existing 3X-UI service/configuration.

## Generate Or Refresh The Word Document

If the user gives the customer/project name after installation, update the existing panel info and regenerate the Word file:

```bash
python3 scripts/make_3xui_doc.py \
  --panel-info '/absolute/path/to/3xui-panel-info.json' \
  --server-name '美国住宅1号' \
  --owner '张三'
```

The Word document contains the server label, who it was built for, server IP, system, SSH username/port, management backend URL, backend username, and backend password. The SSH password is also included by default now (pass `--omit-ssh-password` to leave it out) — which means the doc grants full root access, so keep it strictly admin-only. A named copy (`<server>-3X-UI后台资料.docx`) is also archived to `~/Documents/VPS` by default; override with `--doc-archive-dir` or set it empty to disable.

## Add A Customer Client

Use this when the user asks to add a user/customer/client, tells you the customer name, duration, traffic limit, or says to associate the customer with an inbound.

```bash
python3 scripts/add_3xui_client.py \
  --panel-info '/absolute/path/to/3xui-panel-info.json' \
  --client-name 'customer-a' \
  --duration '30天' \
  --inbound-port 443
```

Options:

- `--days 7`, `--duration '1个月'`, or `--expires-at 2026-06-30` sets expiry.
- `--traffic-gb 50` sets a traffic limit; omit or use `0` for unlimited.
- `--comment '试用'` stores a note in 3X-UI.
- `--group 'TikTok'` stores a customer group.
- `--inbound-id N` targets a specific inbound; otherwise prefer VLESS `443`.

Outputs include:

- `vless-link.txt`
- `vless-qr.png`
- optional `subscription-links.txt` and `subscription-qr.png` if the panel exposes subscription URLs
- `client-summary.json`
- `client-node.docx`

## Optimize An Existing Server (No Reinstall)

Use this when the user already has a working 3X-UI panel (clients may already be
connected) and only wants the BBR/TCP kernel tuning added, without reinstalling.
It is safe for live clients: it only changes kernel sysctl params and loads the
bbr/fq modules. It does NOT log into the panel and does NOT touch the xray
config, inbounds, client UUIDs, Reality keys, ports, or any VLESS/subscription
links, so links that were already handed out keep working unchanged.

```bash
VPS_PASSWORD='<SSH_PASSWORD>' python3 scripts/optimize_3xui.py \
  --panel-info '/absolute/path/to/3xui-panel-info.json'
```

Or point it at a server directly:

```bash
VPS_PASSWORD='<SSH_PASSWORD>' python3 scripts/optimize_3xui.py \
  --host 192.0.2.10 --user root --ssh-port 22
```

It backs up any existing `99-xray-optimization.conf` to `.bak`, applies the
tuning, then confirms `x-ui` is still active. Pass `--revert` to undo it
(removes the drop-in and resets to cubic/fq_codel). Writes `optimize-<ts>.log`.

## Final Response

For panel installation, include clickable links to:

- `3xui-management.docx`
- `3xui-panel-info.json`

Also state the management backend URL, username, and password clearly, and remind the user that these are admin-only.

For adding a customer, show the QR image with an absolute Markdown image path and include the output directory. Tell the user which artifact to send:

- Formal/long-term customer: subscription QR/link when available.
- Quick test or unsupported subscription app: VLESS QR/link.
