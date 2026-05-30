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
    archive_management_doc,
    deploy_karing_adapter,
    ensure_default_inbound,
    expect_ssh,
    optimize_network,
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
    parser.add_argument(
        "--no-optimize",
        action="store_true",
        help="Skip the BBR/TCP kernel tuning that is applied by default (borrowed from setup-vps).",
    )
    parser.add_argument(
        "--no-karing-adapter",
        action="store_true",
        help="Skip the Karing-compatibility subscription adapter that is deployed by default "
        "(adapter on :2097 in front of the sub server; enables sub + advertises :2097 URLs).",
    )
    parser.add_argument(
        "--omit-ssh-password",
        action="store_true",
        help="Do NOT write the SSH password into the management doc/JSON (included by default).",
    )
    parser.add_argument(
        "--doc-archive-dir",
        default="~/Documents/VPS",
        help="Also save a named copy of the management Word doc here. Empty string disables it.",
    )
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

    # Borrowed from setup-vps (vless.sh): the official 3X-UI installer does not tune the
    # kernel, so apply the same BBR/TCP/memory optimization here for open-the-box speed.
    optimization = None
    if not args.no_optimize:
        opt = optimize_network(
            host=args.host,
            user=args.user,
            ssh_port=args.ssh_port,
            password=password,
            timeout=120,
        )
        opt_out = opt.stdout or ""
        (out_dir / "optimize.log").write_text(opt_out, encoding="utf-8")
        optimization = {
            "applied": opt.returncode == 0,
            "bbrActive": "tcp_congestion_control = bbr" in opt_out,
            "qdiscFq": "default_qdisc = fq" in opt_out,
            "fastOpen": "tcp_fastopen = 3" in opt_out,
            "confPath": "/etc/sysctl.d/99-xray-optimization.conf",
            "log": str(out_dir / "optimize.log"),
        }

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
    karing_adapter = None
    need_session = (not args.no_default_inbound) or (not args.no_karing_adapter)
    if need_session:
        session = PanelSession(panel["url"], panel["username"], panel["password"])
        session.login()
        if not args.no_default_inbound:
            remark = args.inbound_remark or f"US-Reality-{args.host}"
            default_inbound = ensure_default_inbound(session, args.host, args.inbound_port, remark)
        # Karing-compatibility subscription adapter (default on). Runs AFTER the default
        # inbound exists: it enables the sub server + sets subURI to :2097 and restarts
        # x-ui (the inbound is already persisted, so the restart is safe). Never fatal.
        if not args.no_karing_adapter:
            try:
                karing_adapter = deploy_karing_adapter(
                    host=args.host,
                    user=args.user,
                    ssh_port=args.ssh_port,
                    password=password,
                    session=session,
                    public_host=args.host,
                )
            except Exception as exc:  # an adapter failure must not fail the whole install
                karing_adapter = {"deployed": False, "error": repr(exc)}
            (out_dir / "karing-adapter.log").write_text(
                json.dumps(karing_adapter, ensure_ascii=False, indent=2), encoding="utf-8"
            )

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
    include_ssh_pw = not args.omit_ssh_password
    server_info = {
        "host": args.host,
        "sshUser": args.user,
        "sshPort": args.ssh_port,
        "system": args.system,
        "serverName": args.server_name,
        "owner": args.owner,
        "installedAt": installed_at,
    }
    if include_ssh_pw:
        server_info["sshPassword"] = password
    info = {
        "server": server_info,
        "panel": panel,
        "defaultInbound": default_inbound,
        "optimization": optimization,
        "karingAdapter": karing_adapter,
        "artifacts": {
            "installLog": str(out_dir / "install-3xui.log"),
            "verifyLog": str(out_dir / "verify.log"),
            "managementDocx": str(out_dir / "3xui-management.docx"),
            **({"optimizeLog": str(out_dir / "optimize.log")} if optimization else {}),
            **({"karingAdapterLog": str(out_dir / "karing-adapter.log")} if karing_adapter else {}),
        },
    }

    if optimization is None:
        optimize_text = "未启用 (--no-optimize)"
    elif optimization["bbrActive"]:
        optimize_text = "已启用 BBR + FQ + TCP/内存调优"
    elif optimization["applied"]:
        optimize_text = "已写入配置，但未确认 BBR 生效（内核可能需重启或不支持）"
    else:
        optimize_text = "尝试失败，请查看 optimize.log"

    if karing_adapter is None:
        karing_text = "未启用 (--no-karing-adapter)"
    elif karing_adapter.get("deployed"):
        karing_text = (
            f"已启用（适配器 :{karing_adapter['listenPort']} → 订阅服务 :{karing_adapter['upstreamPort']}；"
            f"面板订阅地址自动用 :{karing_adapter['listenPort']}，兼容 Karing）"
        )
    else:
        karing_text = f"尝试失败，请查看 karing-adapter.log（{karing_adapter.get('error', '见日志')}）"

    doc_title = f"3X-UI 服务器后台资料 - {args.owner or args.server_name or args.host}"
    fields = [
        ("服务器名称", args.server_name or args.host),
        ("使用对象", args.owner or "未填写"),
        ("服务器 IP", args.host),
        ("系统版本", args.system or "未填写"),
        ("SSH 用户名", args.user),
        ("SSH 端口", args.ssh_port),
    ]
    if include_ssh_pw:
        fields.append(("SSH 密码", password))
    fields += [
        ("管理后台地址", panel["url"]),
        ("后台用户名", panel["username"]),
        ("后台密码", panel["password"]),
        ("面板端口", panel["port"]),
        ("默认入站", f"vless:{args.inbound_port}" if not args.no_default_inbound else "未创建"),
        ("网络优化", optimize_text),
        ("Karing 订阅适配器", karing_text),
        ("安装时间", installed_at),
    ]
    notes = [
        "后台地址、用户名、密码只给管理员保存，不要发给客户。",
        "给客户使用时，在客户端页面新增客户，并发客户自己的订阅二维码或 VLESS 链接。",
        "如果更换服务器，后台地址通常会变化；正式运营建议后续使用域名。",
    ]
    if include_ssh_pw:
        notes.insert(0, "本文档含 SSH root 密码，属于服务器最高权限凭据，务必严格保密，绝不可发给客户。")
    if karing_adapter and karing_adapter.get("deployed"):
        notes.append(
            f"Karing 适配器占用端口 {karing_adapter['listenPort']}；订阅端口(subPort)必须保持 "
            f"{karing_adapter['upstreamPort']} 不变，绝不可改成 {karing_adapter['listenPort']}"
            "（否则与适配器冲突，x-ui 会崩溃、客户掉线）。新加客户端时面板会自动给出 "
            f":{karing_adapter['listenPort']} 的订阅地址，可直接导入 Karing。"
        )
    docx_path = out_dir / "3xui-management.docx"
    write_management_docx(output_path=docx_path, title=doc_title, fields=fields, notes=notes)

    # Keep one copy in the per-run folder (above) and archive a named copy to a stable
    # local folder (default ~/Documents/VPS) so every server's backend doc collects there.
    archive_path = None
    if args.doc_archive_dir.strip():
        server_label = args.server_name or args.owner or args.host
        archive_path = archive_management_doc(docx_path, server_label, args.doc_archive_dir)
        if archive_path:
            info["artifacts"]["managementDocxArchive"] = str(archive_path)

    (out_dir / "3xui-panel-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(
        {
            "ok": True,
            "output_dir": str(out_dir),
            "panel_url": panel["url"],
            "optimization": optimize_text,
            "karingAdapter": karing_text,
            "sshPasswordInDoc": include_ssh_pw,
            "managementDocxArchive": str(archive_path) if archive_path else None,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

