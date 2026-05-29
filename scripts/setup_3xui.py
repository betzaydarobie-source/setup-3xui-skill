#!/usr/bin/env python3
"""Install 3X-UI on a VPS and export management artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common_3xui import (  # noqa: E402
    PanelSession,
    ensure_default_inbound,
    expect_ssh,
    parse_panel_install_log,
    require_password,
    write_management_docx,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install 3X-UI and save panel credentials.")
    parser.add_argument("--host", required=True, help="VPS public IP or hostname.")
    parser.add_argument("--user", default="root", help="SSH username.")
    parser.add_argument("--ssh-port", type=int, default=22, help="SSH port.")
    parser.add_argument("--system", default="", help="Provider-displayed OS version.")
    parser.add_argument("--output-dir", required=True, help="Directory for output artifacts.")
    parser.add_argument("--server-name", default="", help="Human-readable server/customer label.")
    parser.add_argument("--owner", default="", help="Who this server is for.")
    parser.add_argument("--panel-port", type=int, default=0, help="3X-UI panel port. Random if omitted.")
    parser.add_argument("--inbound-port", type=int, default=443, help="Default VLESS Reality inbound port.")
    parser.add_argument("--inbound-remark", default="", help="Default inbound remark.")
    parser.add_argument("--no-default-inbound", action="store_true", help="Only install panel; do not create vless:443.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = require_password()
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    panel_port = args.panel_port or random.randint(30000, 62000)
    os.environ["PANEL_PORT"] = str(panel_port)

    install_command = (
        "DEBIAN_FRONTEND=noninteractive bash -lc "
        "'bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)'"
    )
    install_result = expect_ssh(
        host=args.host,
        user=args.user,
        ssh_port=args.ssh_port,
        password=password,
        remote_command=install_command,
        timeout=1500,
    )
    install_log = install_result.stdout
    (out_dir / "install-3xui.log").write_text(install_log, encoding="utf-8")
    if install_result.returncode != 0:
        print(install_log)
        raise SystemExit(f"3X-UI installation failed with exit code {install_result.returncode}.")

    parsed = parse_panel_install_log(install_log)
    panel = {
        "url": parsed["access_url"].rstrip("/"),
        "username": parsed["username"],
        "password": parsed["password"],
        "port": parsed["port"],
        "webBasePath": parsed["web_base_path"],
        "database": parsed.get("database", "SQLite"),
        "apiToken": parsed.get("api_token", ""),
        "ssl": "enabled" if parsed["access_url"].startswith("https://") else "disabled",
    }

    default_inbound = None
    if not args.no_default_inbound:
        session = PanelSession(panel["url"], panel["username"], panel["password"])
        session.login()
        remark = args.inbound_remark or f"US-Reality-{args.host}"
        default_inbound = ensure_default_inbound(session, args.host, args.inbound_port, remark)

    verify_command = (
        "bash -lc "
        + repr(
            "systemctl is-active x-ui; "
            f"ss -ltnp | grep -E ':({panel['port']}|{args.inbound_port})\\b' || true; "
            "journalctl -u x-ui -n 20 --no-pager | tail -n 12"
        )
    )
    verify = expect_ssh(
        host=args.host,
        user=args.user,
        ssh_port=args.ssh_port,
        password=password,
        remote_command=verify_command,
        timeout=60,
    )
    (out_dir / "verify.log").write_text(verify.stdout, encoding="utf-8")

    installed_at = dt.datetime.now().isoformat(timespec="seconds")
    info = {
        "server": {
            "host": args.host,
            "sshUser": args.user,
            "sshPort": args.ssh_port,
            "system": args.system,
            "serverName": args.server_name,
            "owner": args.owner,
            "installedAt": installed_at,
        },
        "panel": panel,
        "defaultInbound": default_inbound,
        "artifacts": {
            "installLog": str(out_dir / "install-3xui.log"),
            "verifyLog": str(out_dir / "verify.log"),
            "managementDocx": str(out_dir / "3xui-management.docx"),
        },
    }
    (out_dir / "3xui-panel-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    doc_title = f"3X-UI 服务器后台资料 - {args.owner or args.server_name or args.host}"
    fields = [
        ("服务器名称", args.server_name or args.host),
        ("使用对象", args.owner or "未填写"),
        ("服务器 IP", args.host),
        ("系统版本", args.system or "未填写"),
        ("SSH 用户名", args.user),
        ("SSH 端口", args.ssh_port),
        ("管理后台地址", panel["url"]),
        ("后台用户名", panel["username"]),
        ("后台密码", panel["password"]),
        ("面板端口", panel["port"]),
        ("默认入站", f"vless:{args.inbound_port}" if not args.no_default_inbound else "未创建"),
        ("安装时间", installed_at),
    ]
    write_management_docx(
        output_path=out_dir / "3xui-management.docx",
        title=doc_title,
        fields=fields,
        notes=[
            "后台地址、用户名、密码只给管理员保存，不要发给客户。",
            "给客户使用时，在客户端页面新增客户，并发客户自己的订阅二维码或 VLESS 链接。",
            "如果更换服务器，后台地址通常会变化；正式运营建议后续使用域名。",
        ],
    )

    print(json.dumps({"ok": True, "output_dir": str(out_dir), "panel_url": panel["url"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

