#!/usr/bin/env python3
"""Apply (or revert) the BBR/TCP kernel optimization on an EXISTING VPS.

Safe for an already-running 3X-UI panel: it ONLY touches kernel sysctl
parameters and loads the bbr/fq modules. It does NOT log into the panel and does
NOT change the xray config, inbounds, client UUIDs, Reality keys, ports, or any
VLESS / subscription links. Client links that were already handed out keep
working unchanged.

Tcl-safety note: every remote command sent through `expect_ssh` must avoid the
characters `$ [ ] ` (backtick), because the expect spawn line puts the command
inside a Tcl double-quoted word, where those characters trigger variable/command
substitution. This script therefore uses fixed file names instead of `$(date)`
and avoids `[ test ]` constructs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common_3xui import (  # noqa: E402
    expect_ssh,
    load_panel_info,
    optimize_network,
    require_password,
)

CONF_PATH = "/etc/sysctl.d/99-xray-optimization.conf"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply or revert BBR/TCP kernel optimization on an existing VPS "
        "without reinstalling or touching the 3X-UI panel/clients."
    )
    parser.add_argument("--host", default="", help="VPS IP/hostname. Optional if --panel-info is given.")
    parser.add_argument("--user", default="", help="SSH username. Defaults to root or panel-info value.")
    parser.add_argument("--ssh-port", type=int, default=0, help="SSH port. Defaults to 22 or panel-info value.")
    parser.add_argument(
        "--panel-info",
        default="",
        help="Path to an existing 3xui-panel-info.json to read host/user/port from.",
    )
    parser.add_argument("--output-dir", default="", help="Where to write optimize.log. Defaults to CWD.")
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Undo the optimization: remove the sysctl drop-in and reset to cubic/fq_codel.",
    )
    return parser.parse_args()


def resolve_target(args: argparse.Namespace) -> tuple[str, str, int, int | None]:
    """Return (host, user, ssh_port, panel_port) from flags and/or panel-info."""
    host, user, ssh_port, panel_port = args.host, args.user, args.ssh_port, None
    if args.panel_info:
        info = load_panel_info(Path(args.panel_info).expanduser().resolve())
        server = info.get("server", {})
        host = host or server.get("host", "")
        user = user or server.get("sshUser", "")
        ssh_port = ssh_port or int(server.get("sshPort", 0) or 0)
        panel = info.get("panel", {})
        try:
            panel_port = int(panel.get("port")) if panel.get("port") else None
        except (TypeError, ValueError):
            panel_port = None
    if not host:
        raise SystemExit("Missing --host (or provide --panel-info with a server.host).")
    return host, user or "root", ssh_port or 22, panel_port


def backup_command() -> str:
    # Fixed .bak name (no $(date)) to stay Tcl-safe. `cp ... || true` handles absence.
    return "bash -lc " + repr(
        f"cp -a {CONF_PATH} {CONF_PATH}.bak 2>/dev/null && echo 'backup: saved previous conf to {CONF_PATH}.bak' "
        f"|| echo 'backup: no previous conf (clean apply)'"
    )


def post_check_command(panel_port: int | None, inbound_port: int = 443) -> str:
    # Confirms the panel/xray service survived. No $ [ ] backtick.
    ports = f"{inbound_port}" if panel_port is None else f"{inbound_port}|{panel_port}"
    return "bash -lc " + repr(
        "echo '----- service still alive? -----'; "
        "systemctl is-active x-ui || true; "
        "echo '----- listening ports -----'; "
        f"ss -ltnp | grep -E ':({ports})' || ss -ltnp | tail -n 15 || true"
    )


def revert_command() -> str:
    return "bash -lc " + repr(
        f"rm -f {CONF_PATH}; "
        "sysctl -w net.ipv4.tcp_congestion_control=cubic >/dev/null 2>&1 || true; "
        "sysctl -w net.core.default_qdisc=fq_codel >/dev/null 2>&1 || true; "
        "sysctl --system >/dev/null 2>&1 || true; "
        "echo '----- reverted, current values -----'; "
        "sysctl net.ipv4.tcp_congestion_control net.core.default_qdisc 2>/dev/null || true; "
        f"echo 'note: a backup (if any) is still at {CONF_PATH}.bak'"
    )


def main() -> int:
    args = parse_args()
    password = require_password()
    host, user, ssh_port, panel_port = resolve_target(args)

    out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    if args.revert:
        rev = expect_ssh(
            host=host, user=user, ssh_port=ssh_port, password=password,
            remote_command=revert_command(), timeout=60,
        )
        (out_dir / f"optimize-revert-{stamp}.log").write_text(rev.stdout or "", encoding="utf-8")
        print(json.dumps(
            {"ok": rev.returncode == 0, "action": "revert", "host": host,
             "log": str(out_dir / f"optimize-revert-{stamp}.log")},
            ensure_ascii=False, indent=2,
        ))
        return 0 if rev.returncode == 0 else 1

    # APPLY: back up any pre-existing conf first, then apply, then confirm panel survived.
    backup = expect_ssh(
        host=host, user=user, ssh_port=ssh_port, password=password,
        remote_command=backup_command(), timeout=60,
    )
    opt = optimize_network(
        host=host, user=user, ssh_port=ssh_port, password=password, timeout=120,
    )
    check = expect_ssh(
        host=host, user=user, ssh_port=ssh_port, password=password,
        remote_command=post_check_command(panel_port), timeout=60,
    )

    opt_out = opt.stdout or ""
    combined = (
        "===== backup =====\n" + (backup.stdout or "")
        + "\n===== optimize =====\n" + opt_out
        + "\n===== post-check =====\n" + (check.stdout or "")
    )
    log_path = out_dir / f"optimize-{stamp}.log"
    log_path.write_text(combined, encoding="utf-8")

    bbr_active = "tcp_congestion_control = bbr" in opt_out
    xui_alive = "active" in (check.stdout or "")
    print(json.dumps(
        {
            "ok": opt.returncode == 0,
            "action": "apply",
            "host": host,
            "bbrActive": bbr_active,
            "xuiStillActive": xui_alive,
            "note": "面板与客户链接未改动；优化仅作用于内核 TCP 行为。",
            "log": str(log_path),
        },
        ensure_ascii=False, indent=2,
    ))
    return 0 if opt.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
