#!/usr/bin/env python3
"""Shared helpers for setup-3xui scripts."""

from __future__ import annotations

import base64
import datetime as _dt
import html
import http.cookiejar
import json
import os
import random
import re
import secrets
import ssl
import string
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


# Kernel/network tuning borrowed from the setup-vps skill (vless.sh `optimize_network`).
# The official 3X-UI installer does NOT tune the kernel, so a fresh panel node has no
# BBR/buffer tuning out of the box. Applying this drop-in gives the 3X-UI node the same
# open-the-box speed profile as the one-click VLESS script: BBR + fq + enlarged TCP
# buffers + TCP Fast Open + sane keepalive/timeout + memory and file-descriptor limits.
NETWORK_SYSCTL = """# Xray/3X-UI network optimization (borrowed from setup-vps vless.sh)
# TCP optimization
net.core.rmem_default = 262144
net.core.rmem_max = 16777216
net.core.wmem_default = 262144
net.core.wmem_max = 16777216
net.core.netdev_max_backlog = 5000
net.core.netdev_budget = 600
net.ipv4.tcp_rmem = 4096 65536 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_probes = 3
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_retries2 = 5
net.ipv4.tcp_fin_timeout = 10
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 10240 65535
net.ipv4.tcp_max_tw_buckets = 5000
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_timestamps = 1
net.ipv4.tcp_sack = 1
net.ipv4.tcp_fack = 1
net.ipv4.tcp_low_latency = 1
net.ipv4.tcp_adv_win_scale = 2
net.ipv4.tcp_moderate_rcvbuf = 1
net.ipv4.route.flush = 1

# BBR congestion control
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# Memory optimization
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
vm.overcommit_memory = 1

# File descriptor optimization
fs.file-max = 1000000
fs.inotify.max_user_instances = 8192
fs.inotify.max_user_watches = 524288
"""


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def require_password() -> str:
    password = os.environ.get("VPS_PASSWORD") or os.environ.get("SSH_PASSWORD")
    if not password:
        raise SystemExit("Set VPS_PASSWORD in the environment before running this script.")
    return password


def random_token(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def expect_ssh(
    *,
    host: str,
    user: str,
    ssh_port: int,
    password: str,
    remote_command: str,
    timeout: int = 1200,
) -> subprocess.CompletedProcess[str]:
    known_hosts = f"/tmp/codex_3xui_known_hosts_{host.replace('.', '_')}_{os.getpid()}"
    expect_script = f"""
set timeout {timeout}
spawn ssh -tt -o StrictHostKeyChecking=no -o UserKnownHostsFile={known_hosts} -p {ssh_port} {user}@{host} {json.dumps(remote_command)}
expect {{
  -re {{password:}} {{ send "$env(VPS_PASSWORD)\\r"; exp_continue }}
  -re {{Please enter your server.*public IPv4 address:}} {{ send "{host}\\r"; exp_continue }}
  -re {{Choose \\[1\\]:}} {{ send "\\r"; exp_continue }}
  -re {{Would you like to customize the Panel Port settings\\?}} {{ send "y\\r"; exp_continue }}
  -re {{Please set up the panel port:}} {{ send "$env(PANEL_PORT)\\r"; exp_continue }}
  -re {{Choose an option \\(default 2 for IP\\):}} {{ send "\\r"; exp_continue }}
  -re {{Do you have an IPv6 address to include\\?}} {{ send "\\r"; exp_continue }}
  -re {{Port to use for ACME HTTP-01 listener.*:}} {{ send "\\r"; exp_continue }}
  -re {{Enter another port for acme\\.sh standalone listener.*:}} {{ send "\\r"; exp_continue }}
  timeout {{ puts "\\nEXPECT_TIMEOUT"; exit 124 }}
  eof
}}
catch wait result
exit [lindex $result 3]
"""
    env = os.environ.copy()
    env["VPS_PASSWORD"] = password
    return subprocess.run(
        ["expect", "-c", expect_script],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def optimize_network(
    *,
    host: str,
    user: str,
    ssh_port: int,
    password: str,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Apply BBR + TCP/memory/fd tuning on the VPS via an idempotent sysctl drop-in.

    Ships NETWORK_SYSCTL as base64 so multi-line content survives the
    repr -> json.dumps -> Tcl -> remote-shell quoting chain without any escaping
    surprises, then reloads sysctl and loads the bbr/fq modules. Re-running it
    just rewrites the same drop-in file, so it is safe to call repeatedly.
    """
    payload = base64.b64encode(NETWORK_SYSCTL.encode("utf-8")).decode("ascii")
    # Order matters: load the bbr/fq modules BEFORE applying sysctl. On stock
    # Ubuntu kernels tcp_bbr is not preloaded (tcp_available_congestion_control
    # shows only "reno cubic"), so applying `tcp_congestion_control = bbr` first
    # could fail. modprobe first guarantees bbr is available when sysctl sets it.
    remote_command = "bash -lc " + repr(
        f"echo '{payload}' | base64 -d > /etc/sysctl.d/99-xray-optimization.conf; "
        "modprobe tcp_bbr >/dev/null 2>&1 || true; "
        "modprobe sch_fq >/dev/null 2>&1 || true; "
        "sysctl --system >/dev/null 2>&1 || "
        "sysctl -p /etc/sysctl.d/99-xray-optimization.conf >/dev/null 2>&1 || true; "
        "echo '----- optimization result -----'; "
        "sysctl net.ipv4.tcp_congestion_control net.core.default_qdisc net.ipv4.tcp_fastopen 2>/dev/null || true; "
        "(lsmod | grep -q '^tcp_bbr' && echo 'tcp_bbr module: loaded') "
        "|| echo 'tcp_bbr module: builtin or unavailable'"
    )
    return expect_ssh(
        host=host,
        user=user,
        ssh_port=ssh_port,
        password=password,
        remote_command=remote_command,
        timeout=timeout,
    )


def parse_panel_install_log(log_text: str) -> dict[str, Any]:
    clean = strip_ansi(log_text)
    patterns = {
        "username": r"Username:\s*([^\s]+)",
        "password": r"Password:\s*([^\s]+)",
        "port": r"Port:\s*([0-9]+)",
        "web_base_path": r"WebBasePath:\s*([^\s]+)",
        "access_url": r"Access URL:\s*(https?://[^\s]+)",
        "api_token": r"API Token:\s*([^\s]+)",
        "database": r"Database:\s*(.+)",
    }
    info: dict[str, Any] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, clean)
        if match:
            info[key] = match.group(1).strip()
    if "port" in info:
        info["port"] = int(info["port"])
    if "web_base_path" in info:
        path = info["web_base_path"]
        info["web_base_path"] = "/" + path.strip("/") + "/"
    required = ["username", "password", "port", "web_base_path", "access_url"]
    missing = [key for key in required if not info.get(key)]
    if missing:
        raise ValueError(f"Could not parse panel install log. Missing: {', '.join(missing)}")
    return info


class PanelSession:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.cookiejar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
            urllib.request.HTTPCookieProcessor(self.cookiejar),
        )
        self.csrf_token = ""

    def _request(
        self,
        method: str,
        path: str,
        data: Any | None = None,
        *,
        json_body: bool = False,
        csrf: bool = False,
    ) -> Any:
        url = self.base_url + path
        body = None
        headers = {"X-Requested-With": "XMLHttpRequest"}
        if csrf and self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        if data is not None:
            if json_body:
                body = json.dumps(data).encode("utf-8")
                headers["Content-Type"] = "application/json"
            else:
                body = urllib.parse.urlencode(data).encode("utf-8")
                headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with self.opener.open(req, timeout=45) as resp:
            text = resp.read().decode("utf-8", "replace")
            ctype = resp.headers.get("content-type", "")
        if "json" in ctype or text.startswith("{") or text.startswith("["):
            return json.loads(text)
        return text

    def login(self) -> None:
        html_text = self._request("GET", "/")
        match = re.search(r'name="csrf-token" content="([^"]+)"', html_text)
        if match:
            self.csrf_token = match.group(1)
        result = self._request(
            "POST",
            "/login",
            {"username": self.username, "password": self.password},
            csrf=True,
        )
        if not isinstance(result, dict) or not result.get("success"):
            raise RuntimeError(f"3X-UI login failed: {result}")
        try:
            token = self._request("GET", "/csrf-token")
            if isinstance(token, dict) and token.get("success") and token.get("obj"):
                self.csrf_token = token["obj"]
        except Exception:
            pass

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post_form(self, path: str, data: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, data or {}, csrf=True)

    def post_json(self, path: str, data: dict[str, Any] | list[Any] | None = None) -> Any:
        return self._request("POST", path, data or {}, json_body=True, csrf=True)


def load_panel_info(path: Path) -> dict[str, Any]:
    info = json.loads(path.read_text(encoding="utf-8"))
    panel = info.get("panel", info)
    for key in ["url", "username", "password"]:
        if not panel.get(key):
            raise ValueError(f"panel-info JSON missing panel.{key}")
    return info


def panel_session_from_info(info: dict[str, Any]) -> PanelSession:
    panel = info.get("panel", info)
    session = PanelSession(panel["url"], panel["username"], panel["password"])
    session.login()
    return session


def default_vless_reality_payload(host: str, inbound_port: int, remark: str, keys: dict[str, str]) -> dict[str, Any]:
    short_id = secrets.token_hex(4)
    settings = {
        "clients": [],
        "decryption": "none",
        "encryption": "none",
        "fallbacks": [],
    }
    stream_settings = {
        "network": "tcp",
        "security": "reality",
        "tcpSettings": {
            "acceptProxyProtocol": False,
            "header": {"type": "none"},
        },
        "realitySettings": {
            "show": False,
            "xver": 0,
            "target": "www.nvidia.com:443",
            "serverNames": ["www.nvidia.com"],
            "privateKey": keys["privateKey"],
            "minClientVer": "",
            "maxClientVer": "",
            "maxTimediff": 0,
            "shortIds": [short_id],
            "mldsa65Seed": "",
            "settings": {
                "publicKey": keys["publicKey"],
                "fingerprint": "chrome",
                "serverName": "",
                "spiderX": "/",
                "mldsa65Verify": "",
            },
        },
    }
    return {
        "up": 0,
        "down": 0,
        "total": 0,
        "remark": remark or f"US-Reality-{host}",
        "enable": "true",
        "expiryTime": 0,
        "trafficReset": "never",
        "lastTrafficResetTime": 0,
        "listen": "",
        "port": inbound_port,
        "protocol": "vless",
        "settings": json.dumps(settings, separators=(",", ":")),
        "streamSettings": json.dumps(stream_settings, separators=(",", ":")),
        "sniffing": json.dumps({"enabled": False}, separators=(",", ":")),
        "tag": "",
    }


def ensure_default_inbound(session: PanelSession, host: str, inbound_port: int, remark: str) -> dict[str, Any]:
    options = session.get("/panel/api/inbounds/options")
    if isinstance(options, dict) and options.get("success"):
        for item in options.get("obj") or []:
            if item.get("protocol") == "vless" and int(item.get("port") or 0) == inbound_port:
                return {"created": False, "inbound": item}
    keys = session.get("/panel/api/server/getNewX25519Cert")
    if not isinstance(keys, dict) or not keys.get("success"):
        raise RuntimeError(f"Could not generate Reality keys: {keys}")
    payload = default_vless_reality_payload(host, inbound_port, remark, keys["obj"])
    result = session.post_form("/panel/api/inbounds/add", payload)
    if not isinstance(result, dict) or not result.get("success"):
        raise RuntimeError(f"Could not create VLESS Reality inbound: {result}")
    inbound = result.get("obj") or {}
    return {"created": True, "inbound": inbound, "payload": payload}


def select_inbound(session: PanelSession, inbound_id: int | None = None, inbound_port: int | None = None) -> dict[str, Any]:
    options = session.get("/panel/api/inbounds/options")
    if not isinstance(options, dict) or not options.get("success"):
        raise RuntimeError(f"Could not list inbounds: {options}")
    inbounds = options.get("obj") or []
    if inbound_id is not None:
        for inbound in inbounds:
            if int(inbound.get("id")) == inbound_id:
                return inbound
        raise RuntimeError(f"Inbound id {inbound_id} was not found.")
    if inbound_port is not None:
        for inbound in inbounds:
            if int(inbound.get("port") or 0) == inbound_port and inbound.get("protocol") == "vless":
                return inbound
    for inbound in inbounds:
        if inbound.get("protocol") == "vless":
            return inbound
    if inbounds:
        return inbounds[0]
    raise RuntimeError("No inbound exists. Create a VLESS Reality inbound first.")


def parse_duration_to_expiry(duration: str | None = None, days: int | None = None, expires_at: str | None = None) -> int:
    if expires_at:
        value = expires_at.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            dt = _dt.datetime.fromisoformat(value + "T23:59:59")
        else:
            dt = _dt.datetime.fromisoformat(value)
        return int(dt.timestamp() * 1000)
    if days is not None:
        return int((_dt.datetime.now() + _dt.timedelta(days=days)).timestamp() * 1000)
    if not duration:
        return 0
    text = duration.strip().lower()
    if text in {"0", "none", "unlimited", "永久", "不限", "无限"}:
        return 0
    match = re.search(r"(\d+)\s*(天|日|day|days|d)", text)
    if match:
        return parse_duration_to_expiry(days=int(match.group(1)))
    match = re.search(r"(\d+)\s*(周|星期|week|weeks|w)", text)
    if match:
        return parse_duration_to_expiry(days=int(match.group(1)) * 7)
    match = re.search(r"(\d+)\s*(月|个月|month|months|m)", text)
    if match:
        return parse_duration_to_expiry(days=int(match.group(1)) * 30)
    match = re.search(r"(\d+)\s*(年|year|years|y)", text)
    if match:
        return parse_duration_to_expiry(days=int(match.group(1)) * 365)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return parse_duration_to_expiry(expires_at=text)
    raise ValueError(f"Unsupported duration: {duration}")


def add_client_payload(
    *,
    client_name: str,
    inbound_ids: list[int],
    expiry_time: int,
    total_gb: float = 0,
    comment: str = "",
    group: str = "",
    flow: str = "xtls-rprx-vision",
) -> dict[str, Any]:
    return {
        "client": {
            "email": client_name,
            "subId": random_token(16).lower(),
            "id": str(uuid.uuid4()),
            "password": random_token(16),
            "auth": random_token(16),
            "flow": flow,
            "security": "auto",
            "totalGB": int(total_gb * 1024 * 1024 * 1024) if total_gb else 0,
            "expiryTime": expiry_time,
            "reset": 0,
            "limitIp": 0,
            "tgId": 0,
            "group": group,
            "comment": comment,
            "enable": True,
        },
        "inboundIds": inbound_ids,
    }


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value) if value.strip() else {}
    return value or {}


def vless_link_from_inbound(inbound: dict[str, Any], client: dict[str, Any], host: str) -> str:
    settings = parse_jsonish(inbound.get("settings"))
    stream = parse_jsonish(inbound.get("streamSettings"))
    reality = stream.get("realitySettings") or {}
    reality_settings = reality.get("settings") or {}
    target = reality.get("target") or "www.nvidia.com:443"
    sni = reality_settings.get("serverName") or (reality.get("serverNames") or [target.split(":")[0]])[0]
    short_ids = reality.get("shortIds") or [""]
    encryption = settings.get("encryption") or "none"
    client_id = client.get("id") or client.get("uuid")
    if not client_id:
        raise RuntimeError(f"Client has no UUID/id: {client}")
    remark = f"{inbound.get('remark') or 'VLESS'}-{client.get('email') or client_id}"
    params = {
        "type": stream.get("network") or "tcp",
        "encryption": encryption,
        "security": stream.get("security") or "none",
        "sni": sni,
        "fp": reality_settings.get("fingerprint") or "chrome",
        "pbk": reality_settings.get("publicKey") or "",
        "sid": short_ids[0] if short_ids else "",
        "spx": reality_settings.get("spiderX") or "/",
    }
    flow = client.get("flow")
    if flow:
        params["flow"] = flow
    query = urllib.parse.urlencode(params, safe="/")
    return f"vless://{client_id}@{host}:{inbound.get('port')}?{query}#{urllib.parse.quote(remark)}"


def write_qr_png(text: str, output_path: Path) -> None:
    try:
        import segno  # type: ignore
    except Exception:
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "segno"], check=True)
        import segno  # type: ignore
    qr = segno.make(text, error="m")
    qr.save(output_path, scale=8, border=3)


def xml_escape(text: Any) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def docx_paragraph(text: str, *, bold: bool = False) -> str:
    safe = xml_escape(text)
    bold_xml = "<w:b/>" if bold else ""
    return (
        "<w:p><w:r><w:rPr>"
        f"{bold_xml}"
        "</w:rPr><w:t xml:space=\"preserve\">"
        f"{safe}"
        "</w:t></w:r></w:p>"
    )


def write_management_docx(
    *,
    output_path: Path,
    title: str,
    fields: list[tuple[str, Any]],
    notes: list[str] | None = None,
) -> None:
    paragraphs = [docx_paragraph(title, bold=True), docx_paragraph("")]
    for key, value in fields:
        paragraphs.append(docx_paragraph(f"{key}: {value}"))
    if notes:
        paragraphs.append(docx_paragraph(""))
        paragraphs.append(docx_paragraph("注意事项", bold=True))
        for note in notes:
            paragraphs.append(docx_paragraph(f"- {note}"))
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(paragraphs)}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)


def archive_management_doc(
    src: Path,
    server_label: str,
    archive_dir: str = "~/Documents/VPS",
) -> Path | None:
    """Drop a second, meaningfully named copy of a management .docx into a stable folder.

    The per-run output folder keeps its own `3xui-management.docx`; this copies it to
    `<archive_dir>/<server_label>-3X-UI后台资料.docx` so every server's backend doc
    collects in one place (default ~/Documents/VPS). Returns the destination path, or
    None if archiving was skipped/failed (never fatal to the install).
    """
    try:
        dest_dir = Path(archive_dir).expanduser()
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r'[\\/:*?"<>|]+', "_", str(server_label or "3X-UI").strip()).strip("._- ") or "3X-UI"
        dest = dest_dir / f"{safe}-3X-UI后台资料.docx"
        dest.write_bytes(Path(src).read_bytes())
        return dest
    except Exception:
        return None

