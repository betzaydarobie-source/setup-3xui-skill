#!/usr/bin/env python3
"""Create or refresh the Word management document from panel-info JSON."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common_3xui import load_panel_info, write_management_docx  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a 3X-UI management Word document.")
    parser.add_argument("--panel-info", required=True, help="Path to 3xui-panel-info.json.")
    parser.add_argument("--server-name", default="", help="Human-readable server label.")
    parser.add_argument("--owner", default="", help="Who this server is for.")
    parser.add_argument("--output", default="", help="Output .docx path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    info_path = Path(args.panel_info).expanduser().resolve()
    info = load_panel_info(info_path)
    server = info.get("server", {})
    panel = info.get("panel", info)
    server_host = server.get("host") or info.get("server_ip") or "未填写"
    server_name = args.server_name or server.get("serverName") or server.get("host") or "3X-UI 服务器"
    owner = args.owner or server.get("owner") or "未填写"
    output = Path(args.output).expanduser().resolve() if args.output else info_path.parent / "3xui-management.docx"

    fields = [
        ("服务器名称", server_name),
        ("使用对象", owner),
        ("服务器 IP", server_host),
        ("系统版本", server.get("system", "未填写")),
        ("SSH 用户名", server.get("sshUser", "root")),
        ("SSH 端口", server.get("sshPort", 22)),
        ("管理后台地址", panel["url"]),
        ("后台用户名", panel["username"]),
        ("后台密码", panel["password"]),
        ("面板端口", panel.get("port", "")),
        ("生成时间", dt.datetime.now().isoformat(timespec="seconds")),
    ]
    write_management_docx(
        output_path=output,
        title=f"3X-UI 服务器后台资料 - {owner}",
        fields=fields,
        notes=[
            "后台地址、用户名、密码只给管理员保存，不要发给客户。",
            "客户只接收自己的订阅二维码或 VLESS 节点二维码。",
        ],
    )
    info.setdefault("server", {})["serverName"] = server_name
    info.setdefault("server", {})["owner"] = owner
    info.setdefault("artifacts", {})["managementDocx"] = str(output)
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "docx": str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
