#!/usr/bin/env python3
"""Add a client to a 3X-UI panel and export client artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common_3xui import (  # noqa: E402
    add_client_payload,
    load_panel_info,
    panel_session_from_info,
    parse_duration_to_expiry,
    random_token,
    select_inbound,
    vless_link_from_inbound,
    write_management_docx,
    write_qr_png,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add a 3X-UI client and export links/QR.")
    parser.add_argument("--panel-info", required=True, help="Path to 3xui-panel-info.json.")
    parser.add_argument("--client-name", required=True, help="Customer display name.")
    parser.add_argument("--duration", default="", help="Duration like 7天, 1个月, 30 days, 永久.")
    parser.add_argument("--days", type=int, default=None, help="Expiry in days from now.")
    parser.add_argument("--expires-at", default="", help="Exact expiry date/time, e.g. 2026-06-30.")
    parser.add_argument("--traffic-gb", type=float, default=0, help="Traffic limit in GB. 0 means unlimited.")
    parser.add_argument("--comment", default="", help="Client note/comment.")
    parser.add_argument("--group", default="", help="Optional client group.")
    parser.add_argument("--inbound-id", type=int, default=None, help="Specific inbound id.")
    parser.add_argument("--inbound-port", type=int, default=443, help="Prefer this VLESS inbound port.")
    parser.add_argument("--output-dir", default="", help="Output directory. Defaults next to panel-info.")
    return parser.parse_args()


def safe_email(display_name: str) -> tuple[str, str]:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", display_name.strip()).strip("-._")
    if cleaned and len(cleaned) >= 3:
        return cleaned[:48], ""
    generated = "client-" + random_token(8).lower()
    return generated, display_name


def main() -> int:
    args = parse_args()
    panel_info_path = Path(args.panel_info).expanduser().resolve()
    info = load_panel_info(panel_info_path)
    host = info.get("server", {}).get("host") or re.sub(r"^https?://", "", info["panel"]["url"]).split(":")[0]
    session = panel_session_from_info(info)

    inbound = select_inbound(session, inbound_id=args.inbound_id, inbound_port=args.inbound_port)
    inbound_id = int(inbound["id"])

    email, generated_comment = safe_email(args.client_name)
    comment = args.comment or generated_comment
    expiry_time = parse_duration_to_expiry(
        duration=args.duration or None,
        days=args.days,
        expires_at=args.expires_at or None,
    )
    payload = add_client_payload(
        client_name=email,
        inbound_ids=[inbound_id],
        expiry_time=expiry_time,
        total_gb=args.traffic_gb,
        comment=comment,
        group=args.group,
    )
    result = session.post_json("/panel/api/clients/add", payload)
    if not isinstance(result, dict) or not result.get("success"):
        raise SystemExit(f"Could not add client: {result}")

    full = session.get(f"/panel/api/inbounds/get/{inbound_id}")
    if not isinstance(full, dict) or not full.get("success") or not full.get("obj"):
        raise SystemExit(f"Client added, but could not fetch inbound: {full}")
    inbound_full = full["obj"]
    client = payload["client"]
    link = vless_link_from_inbound(inbound_full, client, host)

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.output_dir:
        out_dir = Path(args.output_dir).expanduser().resolve()
    else:
        out_dir = panel_info_path.parent / "clients" / f"{email}-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "vless-link.txt").write_text(link + "\n", encoding="utf-8")
    write_qr_png(link, out_dir / "vless-qr.png")

    subscriptions: dict[str, str] = {}
    try:
        defaults = session.post_form("/panel/setting/defaultSettings")
        obj = defaults.get("obj") if isinstance(defaults, dict) else {}
        sub_id = client.get("subId") or ""
        if sub_id and obj:
            if obj.get("subURI"):
                subscriptions["SUB"] = obj["subURI"] + sub_id
            if obj.get("subClashURI"):
                subscriptions["CLASH"] = obj["subClashURI"] + sub_id
    except Exception:
        subscriptions = {}
    if subscriptions:
        (out_dir / "subscription-links.txt").write_text(
            "\n".join(f"{key}: {value}" for key, value in subscriptions.items()) + "\n",
            encoding="utf-8",
        )
        first_sub = next(iter(subscriptions.values()))
        write_qr_png(first_sub, out_dir / "subscription-qr.png")

    expiry_text = "永久/不限时"
    if expiry_time:
        expiry_text = dt.datetime.fromtimestamp(expiry_time / 1000).strftime("%Y-%m-%d %H:%M:%S")
    summary = {
        "clientDisplayName": args.client_name,
        "clientEmail": email,
        "comment": comment,
        "group": args.group,
        "inbound": inbound,
        "expiryTime": expiry_time,
        "expiryText": expiry_text,
        "trafficGB": args.traffic_gb,
        "link": link,
        "subscriptions": subscriptions,
        "artifacts": {
            "vlessLink": str(out_dir / "vless-link.txt"),
            "vlessQr": str(out_dir / "vless-qr.png"),
            "summary": str(out_dir / "client-summary.json"),
            "clientDocx": str(out_dir / "client-node.docx"),
        },
    }
    (out_dir / "client-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    write_management_docx(
        output_path=out_dir / "client-node.docx",
        title=f"客户节点资料 - {args.client_name}",
        fields=[
            ("客户名称", args.client_name),
            ("后台客户标识", email),
            ("关联入站", f"{inbound.get('remark') or inbound.get('protocol')} ({inbound.get('protocol')}:{inbound.get('port')})"),
            ("到期时间", expiry_text),
            ("流量限制", "不限" if not args.traffic_gb else f"{args.traffic_gb:g} GB"),
            ("VLESS 链接文件", out_dir / "vless-link.txt"),
            ("VLESS 二维码", out_dir / "vless-qr.png"),
        ],
        notes=[
            "客户只需要 VLESS 二维码/链接或订阅二维码，不要给客户后台地址。",
            "如果客户使用 Clash/Mihomo，优先使用 CLASH 订阅；其他软件一般使用 VLESS 或 SUB。",
        ],
    )

    print(json.dumps({"ok": True, "client": email, "output_dir": str(out_dir), "link": link}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

