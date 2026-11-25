#!/usr/bin/env python3
"""MCP server for checking exit IPs, vendor-detected regions, and consistency across Google, Anthropic, and OpenAI."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import datetime
import json
import os
from pathlib import Path
import re
import socket
import ssl
import struct
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

ROUTE_ID_RE = re.compile(r"^[0-9a-f]{24}$")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)

# Regions commonly restricted by major AI providers.
COMMON_RESTRICTED = {"CN", "HK", "MO", "RU", "BY", "IR", "KP", "SY", "CU"}

COUNTRY_NAMES_ZH: dict[str, str] = {
    "US": "美国",
    "JP": "日本",
    "SG": "新加坡",
    "TW": "中国台湾",
    "HK": "中国香港",
    "MO": "中国澳门",
    "CN": "中国内地",
    "KR": "韩国",
    "GB": "英国",
    "DE": "德国",
    "FR": "法国",
    "NL": "荷兰",
    "CA": "加拿大",
    "AU": "澳大利亚",
    "IN": "印度",
    "MY": "马来西亚",
    "TH": "泰国",
    "VN": "越南",
    "PH": "菲律宾",
    "ID": "印度尼西亚",
    "CH": "瑞士",
    "SE": "瑞典",
    "IE": "爱尔兰",
    "FI": "芬兰",
    "ES": "西班牙",
    "IT": "意大利",
    "PL": "波兰",
    "BR": "巴西",
    "MX": "墨西哥",
    "AE": "阿联酋",
    "TR": "土耳其",
    "RU": "俄罗斯",
    "UA": "乌克兰",
    "ZA": "南非",
    "NZ": "新西兰",
}


def country_label(code: str) -> str:
    clean = (code or "").strip().upper()
    if not clean:
        return ""
    zh = COUNTRY_NAMES_ZH.get(clean)
    return f"{zh} ({clean})" if zh else clean


def _recv_exact(sock: socket.socket, count: int) -> bytes:
    buf = bytearray()
    while len(buf) < count:
        chunk = sock.recv(count - len(buf))
        if not chunk:
            raise ConnectionError("unexpected EOF from proxy socket")
        buf.extend(chunk)
    return bytes(buf)


def _http_via_unix_socks5(
    unix_sock_path: str,
    url: str,
    timeout: float = 8.0,
    max_redirects: int = 4,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, dict[str, str], str]:
    current_url = url
    ctx = ssl.create_default_context()
    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "*/*",
        "Connection": "close",
        **(headers or {}),
    }

    for _ in range(max_redirects + 1):
        parsed = urllib.parse.urlsplit(current_url)
        scheme = parsed.scheme.lower()
        if scheme not in ("https", "http") or not parsed.hostname:
            raise ValueError("unsupported URL scheme")
        host = parsed.hostname
        port = parsed.port or (443 if scheme == "https" else 80)
        path_part = parsed.path or "/"
        if parsed.query:
            path_part = f"{path_part}?{parsed.query}"

        raw_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        raw_sock.settimeout(timeout)
        try:
            raw_sock.connect(unix_sock_path)
            raw_sock.sendall(b"\x05\x01\x00")
            if _recv_exact(raw_sock, 2) != b"\x05\x00":
                raise ConnectionError("SOCKS5 handshake rejected")
            host_bytes = host.encode("idna")
            if len(host_bytes) > 255:
                raise ValueError("hostname too long")
            raw_sock.sendall(
                b"\x05\x01\x00\x03"
                + bytes([len(host_bytes)])
                + host_bytes
                + struct.pack("!H", port)
            )
            head = _recv_exact(raw_sock, 4)
            if head[1] != 0x00:
                raise ConnectionError(f"SOCKS5 connect failed (code {head[1]})")
            atyp = head[3]
            if atyp == 1:
                _recv_exact(raw_sock, 4 + 2)
            elif atyp == 3:
                ln = _recv_exact(raw_sock, 1)[0]
                _recv_exact(raw_sock, ln + 2)
            elif atyp == 4:
                _recv_exact(raw_sock, 16 + 2)
            else:
                raise ConnectionError("unknown SOCKS5 address type")

            conn: socket.socket = (
                ctx.wrap_socket(raw_sock, server_hostname=host)
                if scheme == "https"
                else raw_sock
            )
            try:
                lines = [f"GET {path_part} HTTP/1.1", f"Host: {host}"]
                for k, v in req_headers.items():
                    if k.lower() != "host":
                        lines.append(f"{k}: {v}")
                request_bytes = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
                conn.sendall(request_bytes)
                response_buf = bytearray()
                while len(response_buf) < 131072:
                    chunk = conn.recv(8192)
                    if not chunk:
                        break
                    response_buf.extend(chunk)
            finally:
                conn.close()
        except BaseException:
            raw_sock.close()
            raise

        sep = response_buf.find(b"\r\n\r\n")
        if sep == -1:
            raise ConnectionError("malformed HTTP response")
        header_text = response_buf[:sep].decode("iso-8859-1", errors="replace")
        body_raw = bytes(response_buf[sep + 4 :])
        header_lines = header_text.split("\r\n")
        status_parts = header_lines[0].split(" ", 2)
        status = int(status_parts[1]) if len(status_parts) >= 2 and status_parts[1].isdigit() else 0
        resp_headers: dict[str, str] = {}
        for line in header_lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                resp_headers[k.strip().lower()] = v.strip()
        if resp_headers.get("transfer-encoding", "").lower() == "chunked":
            decoded = bytearray()
            idx = 0
            while idx < len(body_raw):
                end = body_raw.find(b"\r\n", idx)
                if end == -1:
                    break
                size_token = body_raw[idx:end].split(b";", 1)[0].strip()
                try:
                    chunk_len = int(size_token, 16)
                except ValueError:
                    break
                if chunk_len == 0:
                    break
                start_data = end + 2
                decoded.extend(body_raw[start_data : start_data + chunk_len])
                idx = start_data + chunk_len + 2
            body_raw = bytes(decoded)

        if status in (301, 302, 303, 307, 308) and "location" in resp_headers:
            current_url = urllib.parse.urljoin(current_url, resp_headers["location"])
            continue
        return status, current_url, resp_headers, body_raw[:65536].decode("utf-8", errors="replace")

    raise ConnectionError("too many redirects")


def fetch_url(
    url: str,
    socks_path: str = "",
    timeout: float = 8.0,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, dict[str, str], str, int]:
    started = time.monotonic()
    if socks_path:
        status, final_url, resp_headers, body = _http_via_unix_socks5(
            socks_path, url, timeout=timeout, headers=headers
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return status, final_url, resp_headers, body, elapsed_ms

    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(65536)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp.geturl(), hdrs, raw.decode("utf-8", errors="replace"), elapsed_ms
    except urllib.error.HTTPError as err:
        raw = err.read(16384) if err.fp else b""
        elapsed_ms = int((time.monotonic() - started) * 1000)
        hdrs = {k.lower(): v for k, v in (err.headers.items() if err.headers else [])}
        return err.code, err.geturl() or url, hdrs, raw.decode("utf-8", errors="replace"), elapsed_ms


def parse_cf_trace(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def probe_baseline_geoip(socks_path: str) -> dict[str, Any]:
    sources = [
        ("ipinfo.io", "https://ipinfo.io/json"),
        ("ip.sb", "https://api.ip.sb/geoip"),
        ("ipwho.is", "https://ipwho.is/"),
    ]
    last_err = ""
    for source_name, url in sources:
        try:
            status, _, _, body, latency_ms = fetch_url(url, socks_path=socks_path, timeout=7.0)
            if status != 200:
                last_err = f"{source_name} HTTP {status}"
                continue
            data = json.loads(body)
            if not isinstance(data, dict):
                continue
            if source_name == "ipwho.is" and data.get("success") is False:
                continue
            ip = str(data.get("ip") or "").strip()
            country = ""
            for candidate in (data.get("country_code"), data.get("countryCode"), data.get("country")):
                code = str(candidate or "").strip().upper()
                if re.fullmatch(r"[A-Z]{2}", code):
                    country = code
                    break
            region = str(data.get("region") or data.get("region_name") or "").strip()
            city = str(data.get("city") or "").strip()
            org = str(
                data.get("org")
                or data.get("organization")
                or (data.get("connection") or {}).get("isp")
                or ""
            ).strip()
            timezone = str(data.get("timezone") if isinstance(data.get("timezone"), str) else "").strip()
            if ip:
                return {
                    "ok": True,
                    "source": source_name,
                    "ip": ip,
                    "country": country,
                    "country_label": country_label(country),
                    "region": region,
                    "city": city,
                    "org": org,
                    "timezone": timezone,
                    "latency_ms": latency_ms,
                }
        except Exception as exc:
            last_err = str(exc)
    return {
        "ok": False,
        "source": "",
        "ip": "",
        "country": "",
        "country_label": "",
        "region": "",
        "city": "",
        "org": "",
        "timezone": "",
        "error": last_err or "unable to query baseline GeoIP service",
    }


def probe_google(socks_path: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": "google",
        "name": "Google (Antigravity / Gemini)",
        "ip": "",
        "country": "",
        "country_label": "",
        "colo": "",
        "edns_subnet": "",
        "services": {},
        "reachable": False,
        "supported_region": None,
        "latency_ms": None,
        "error": "",
    }
    # 1. Google Production GeoIP & seen client IP via sw.js_data
    try:
        status, _, _, body, ms = fetch_url("https://www.youtube.com/sw.js_data", socks_path=socks_path, timeout=8.0)
        result["latency_ms"] = ms
        if status == 200 and body:
            cleaned = re.sub(r"^\)\]\}'\s*", "", body)
            parsed = json.loads(cleaned)
            # Structure: [["yt.sw.adr", null, [[["en", "<COUNTRY>", null, "<CLIENT_IP>", ...
            inner = parsed[0][2][0][0]
            if isinstance(inner, list) and len(inner) >= 4:
                cc = str(inner[1] or "").strip().upper()
                ip = str(inner[3] or "").strip()
                if re.fullmatch(r"[A-Z]{2}", cc):
                    result["country"] = cc
                    result["country_label"] = country_label(cc)
                if ip:
                    result["ip"] = ip
            result["reachable"] = True
            result["services"]["google_edge"] = {"ok": True, "status": status, "latency_ms": ms}
        else:
            result["services"]["google_edge"] = {"ok": False, "status": status, "latency_ms": ms}
    except Exception as exc:
        result["error"] = str(exc)
        result["services"]["google_edge"] = {"ok": False, "error": str(exc)}

    # 2. Antigravity web & Cloud Code API reachability
    for svc_key, svc_url in (
        ("antigravity_web", "https://antigravity.google/"),
        ("antigravity_api", "https://daily-cloudcode-pa.googleapis.com/"),
        ("gemini_web", "https://gemini.google.com/app?hl=en"),
    ):
        try:
            st, final_url, _, _, ms = fetch_url(svc_url, socks_path=socks_path, timeout=8.0)
            if svc_key == "gemini_web":
                lowered = (final_url or "").lower()
                blocked_redirect = "/faq" in lowered or "unsupported" in lowered
                ok = 200 <= st < 400 and not blocked_redirect
                result["services"][svc_key] = {
                    "ok": ok,
                    "status": st,
                    "final_url": final_url,
                    "region_blocked_redirect": blocked_redirect,
                    "latency_ms": ms,
                }
            else:
                # Cloud Code PA root returns 404/401 when reachable over TLS
                ok = (200 <= st < 500) and st != 403
                result["services"][svc_key] = {"ok": ok, "status": st, "latency_ms": ms}
                if ok:
                    result["reachable"] = True
        except Exception as exc:
            result["services"][svc_key] = {"ok": False, "error": str(exc)}

    cc = result["country"]
    gemini_blocked = bool((result["services"].get("gemini_web") or {}).get("region_blocked_redirect"))
    if cc:
        result["supported_region"] = (cc not in COMMON_RESTRICTED) and not gemini_blocked
    elif gemini_blocked:
        result["supported_region"] = False
    return result


def probe_anthropic(socks_path: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": "anthropic",
        "name": "Anthropic (Claude)",
        "ip": "",
        "country": "",
        "country_label": "",
        "colo": "",
        "services": {},
        "reachable": False,
        "supported_region": None,
        "latency_ms": None,
        "error": "",
    }
    try:
        st, _, _, body, ms = fetch_url("https://claude.ai/cdn-cgi/trace", socks_path=socks_path, timeout=8.0)
        result["latency_ms"] = ms
        if st == 200:
            kv = parse_cf_trace(body)
            ip = kv.get("ip", "")
            cc = kv.get("loc", "").upper()
            colo = kv.get("colo", "")
            result["ip"] = ip
            result["country"] = cc if len(cc) == 2 else ""
            result["country_label"] = country_label(result["country"])
            result["colo"] = colo
            result["reachable"] = True
            result["services"]["claude_web"] = {"ok": True, "status": st, "colo": colo, "latency_ms": ms}
        else:
            result["services"]["claude_web"] = {"ok": False, "status": st, "latency_ms": ms}
    except Exception as exc:
        result["error"] = str(exc)
        result["services"]["claude_web"] = {"ok": False, "error": str(exc)}

    try:
        st, _, hdrs, body, ms = fetch_url("https://api.anthropic.com/v1/messages", socks_path=socks_path, timeout=8.0)
        ray = hdrs.get("cf-ray", "")
        api_colo = ray.rsplit("-", 1)[-1] if "-" in ray else ""
        if not result["colo"] and api_colo:
            result["colo"] = api_colo
        # GET /v1/messages without auth returns 405 Method Not Allowed when unblocked, 403 when region-blocked
        allowed = st in (200, 400, 401, 404, 405)
        blocked = st == 403
        result["services"]["anthropic_api"] = {
            "ok": allowed,
            "status": st,
            "colo": api_colo,
            "region_blocked": blocked,
            "latency_ms": ms,
        }
        if allowed:
            result["reachable"] = True
    except Exception as exc:
        result["services"]["anthropic_api"] = {"ok": False, "error": str(exc)}

    cc = result["country"]
    api_blocked = bool((result["services"].get("anthropic_api") or {}).get("region_blocked"))
    if api_blocked:
        result["supported_region"] = False
    elif cc:
        result["supported_region"] = cc not in COMMON_RESTRICTED
    return result


def probe_openai(socks_path: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": "openai",
        "name": "OpenAI (Codex / ChatGPT)",
        "ip": "",
        "auth_ip": "",
        "country": "",
        "auth_country": "",
        "country_label": "",
        "colo": "",
        "services": {},
        "reachable": False,
        "supported_region": None,
        "latency_ms": None,
        "error": "",
    }
    try:
        st, _, _, body, ms = fetch_url("https://chatgpt.com/cdn-cgi/trace", socks_path=socks_path, timeout=8.0)
        result["latency_ms"] = ms
        if st == 200:
            kv = parse_cf_trace(body)
            ip = kv.get("ip", "")
            cc = kv.get("loc", "").upper()
            colo = kv.get("colo", "")
            result["ip"] = ip
            result["country"] = cc if len(cc) == 2 else ""
            result["country_label"] = country_label(result["country"])
            result["colo"] = colo
            result["reachable"] = True
            result["services"]["chatgpt_web"] = {"ok": True, "status": st, "colo": colo, "latency_ms": ms}
        else:
            result["services"]["chatgpt_web"] = {"ok": False, "status": st, "latency_ms": ms}
    except Exception as exc:
        result["error"] = str(exc)
        result["services"]["chatgpt_web"] = {"ok": False, "error": str(exc)}

    try:
        st, _, _, body, ms = fetch_url("https://auth.openai.com/cdn-cgi/trace", socks_path=socks_path, timeout=8.0)
        if st == 200:
            kv = parse_cf_trace(body)
            result["auth_ip"] = kv.get("ip", "")
            auth_cc = kv.get("loc", "").upper()
            result["auth_country"] = auth_cc if len(auth_cc) == 2 else ""
            result["services"]["codex_oauth"] = {
                "ok": True,
                "status": st,
                "ip": result["auth_ip"],
                "country": result["auth_country"],
                "colo": kv.get("colo", ""),
                "latency_ms": ms,
            }
        else:
            result["services"]["codex_oauth"] = {"ok": False, "status": st, "latency_ms": ms}
    except Exception as exc:
        result["services"]["codex_oauth"] = {"ok": False, "error": str(exc)}

    try:
        st, _, _, body, ms = fetch_url("https://api.openai.com/v1/models", socks_path=socks_path, timeout=8.0)
        unsupported = st == 403 or "unsupported_country_region_territory" in (body or "")
        allowed = st in (200, 401) and not unsupported
        result["services"]["openai_api"] = {
            "ok": allowed,
            "status": st,
            "region_blocked": unsupported,
            "latency_ms": ms,
        }
        if allowed:
            result["reachable"] = True
    except Exception as exc:
        result["services"]["openai_api"] = {"ok": False, "error": str(exc)}

    cc = result["country"] or result["auth_country"]
    api_blocked = bool((result["services"].get("openai_api") or {}).get("region_blocked"))
    if api_blocked:
        result["supported_region"] = False
    elif cc:
        result["supported_region"] = cc not in COMMON_RESTRICTED
    return result


def evaluate_provider(
    item: dict[str, Any],
    baseline: dict[str, Any],
    expected_country: str,
    peer_countries: set[str],
) -> dict[str, Any]:
    base_ip = baseline.get("ip") or ""
    base_cc = baseline.get("country") or ""
    prov_ip = item.get("ip") or ""
    prov_cc = item.get("country") or ""

    same_ip_as_baseline = bool(base_ip and prov_ip and base_ip == prov_ip)
    split_routed = bool(base_ip and prov_ip and base_ip != prov_ip)
    matches_baseline_region = bool(base_cc and prov_cc and base_cc == prov_cc)
    matches_expected = bool(expected_country and prov_cc == expected_country) if expected_country else None

    notes: list[str] = []
    verdict = "ok"

    if not item.get("reachable"):
        verdict = "error"
        notes.append("无法连接官方边缘服务，请检查代理节点或网络连通性。")
    else:
        if item.get("supported_region") is False:
            verdict = "blocked"
            notes.append(f"当前被官方识别为受限地区 {country_label(prov_cc) or '未知'}，服务可能拒绝访问。")
        if same_ip_as_baseline and base_cc and prov_cc and base_cc != prov_cc:
            if verdict == "ok":
                verdict = "warn"
            notes.append(
                f"出口 IP 相同，但 GeoIP 标称为 {country_label(base_cc)}，厂商实际识别为 {country_label(prov_cc)}（IP 归属库存在偏差）。"
            )
        elif split_routed:
            if base_cc and prov_cc and base_cc != prov_cc:
                if verdict == "ok":
                    verdict = "warn"
                notes.append(
                    f"走了独立分流节点（IP 与默认出口不同），厂商识别地区为 {country_label(prov_cc)}。"
                )
            else:
                notes.append("走了独立分流节点（IP 与默认出口不同，但国家/地区一致）。")
        other_ccs = sorted(c for c in peer_countries if c and c != prov_cc)
        if prov_cc and other_ccs:
            if verdict == "ok":
                verdict = "warn"
            others_str = " / ".join(country_label(c) for c in other_ccs)
            notes.append(f"与其他 AI 平台识别地区（{others_str}）不一致。")
        if item.get("provider") == "openai":
            auth_ip = item.get("auth_ip") or ""
            auth_cc = item.get("auth_country") or ""
            if prov_ip and auth_ip and prov_ip != auth_ip:
                if verdict == "ok":
                    verdict = "warn"
                notes.append(
                    f"chatgpt.com ({prov_ip}) 与 auth.openai.com ({auth_ip}) 出口不一致，登录与会话可能走了不同分流规则。"
                )
            if prov_cc and auth_cc and prov_cc != auth_cc:
                if verdict == "ok":
                    verdict = "warn"
                notes.append(
                    f"ChatGPT ({country_label(prov_cc)}) 与 Codex 授权页 ({country_label(auth_cc)}) 识别地区不一致。"
                )
        if expected_country and prov_cc and prov_cc != expected_country:
            if verdict == "ok":
                verdict = "warn"
            notes.append(
                f"与期望目标地区 {country_label(expected_country)} 不一致（实际识别为 {country_label(prov_cc)}）。"
            )
        if not notes and prov_cc:
            notes.append(f"出口识别正常，厂商识别地区与预期一致（{country_label(prov_cc)}）。")

    return {
        **item,
        "same_ip_as_baseline": same_ip_as_baseline,
        "split_routed": split_routed,
        "matches_baseline_region": matches_baseline_region,
        "matches_expected_region": matches_expected,
        "verdict": verdict,
        "notes": notes,
    }


def discover_active_routes() -> list[dict[str, str]]:
    routes = [{"id": "default", "label": "默认网络出口"}]
    routes_root = Path("/run/account-routes")
    if not routes_root.is_dir():
        return routes
    for entry in sorted(routes_root.iterdir()):
        if not ROUTE_ID_RE.fullmatch(entry.name):
            continue
        sock = entry / "browser.sock"
        if sock.exists() and os.access(sock, os.R_OK | os.W_OK):
            routes.append({"id": entry.name, "label": f"独立账号出口 ({entry.name[:8]}…)"})
    return routes


def run_exit_check(route_id: str = "", expected_country: str = "") -> dict[str, Any]:
    clean_route = (route_id or "").strip().lower()
    socks_path = ""
    if clean_route and clean_route != "default":
        if not ROUTE_ID_RE.fullmatch(clean_route):
            raise ValueError("invalid route_id; expected 'default' or a 24-character hex route identifier")
        candidate = Path("/run/account-routes") / clean_route / "browser.sock"
        if not candidate.exists():
            raise ValueError("the selected dedicated account route is not currently active")
        socks_path = str(candidate)

    clean_expected = (expected_country or "").strip().upper()
    if clean_expected and not re.fullmatch(r"[A-Z]{2}", clean_expected):
        raise ValueError("expected_country must be a 2-letter ISO country code such as US, JP, SG")

    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_base = pool.submit(probe_baseline_geoip, socks_path)
        fut_google = pool.submit(probe_google, socks_path)
        fut_anthropic = pool.submit(probe_anthropic, socks_path)
        fut_openai = pool.submit(probe_openai, socks_path)

        baseline = fut_base.result()
        raw_providers = [fut_google.result(), fut_anthropic.result(), fut_openai.result()]

    providers = [
        evaluate_provider(
            p,
            baseline,
            clean_expected,
            {other["country"] for other in raw_providers if other is not p and other.get("country")},
        )
        for p in raw_providers
    ]

    seen_ips = {p["ip"] for p in providers if p.get("ip")}
    if baseline.get("ip"):
        seen_ips.add(baseline["ip"])
    seen_countries = {p["country"] for p in providers if p.get("country")}

    all_ips_match = len(seen_ips) <= 1 and bool(seen_ips)
    all_regions_match = (
        len(seen_countries) == 1
        and (not baseline.get("country") or baseline["country"] in seen_countries)
        and (not clean_expected or clean_expected in seen_countries)
    )
    any_blocked = any(p["verdict"] in ("blocked", "error") for p in providers)
    any_warn = any(p["verdict"] == "warn" for p in providers)

    if any_blocked:
        overall = "blocked"
        summary = "存在受限地区或连接异常，部分 AI 服务可能无法正常使用。"
    elif any_warn or not all_regions_match:
        overall = "warn"
        summary = "各平台识别到的出口 IP 或所属地区存在分流/归属库差异，请核对下方明细。"
    else:
        only_cc = next(iter(seen_countries), baseline.get("country") or "")
        overall = "ok"
        summary = f"三端出口识别完全一致，均识别为受支持地区 {country_label(only_cc)}。"

    return {
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "route": clean_route or "default",
        "expected_country": clean_expected,
        "overall_status": overall,
        "summary": summary,
        "all_ips_consistent": all_ips_match,
        "all_regions_consistent": all_regions_match,
        "baseline": baseline,
        "providers": providers,
    }


TOOLS: list[dict[str, Any]] = [
    {
        "name": "check_ai_exit_regions",
        "description": (
            "Checks the current outbound exit IP, vendor-recognized country/region, edge location, "
            "service reachability, and region consistency across Google (Antigravity/Gemini), "
            "Anthropic (Claude), and OpenAI (Codex/ChatGPT)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "expected_country": {
                    "type": "string",
                    "description": "Optional 2-letter ISO country code (for example US, JP, SG) to verify against each provider's detected region.",
                },
                "route_id": {
                    "type": "string",
                    "description": "Optional outbound route identifier ('default' or a 24-character hex account route ID).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "list_exit_routes",
        "description": "Lists currently active outbound routes available for exit IP and region probing.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "_meta": {"ui": {"visibility": ["app"]}},
    },
]


def ok_json(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}]}


def err_result(message: str) -> dict[str, Any]:
    return {"isError": True, "content": [{"type": "text", "text": message}]}


def handle_tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "check_ai_exit_regions":
            report = run_exit_check(
                route_id=str((args or {}).get("route_id") or ""),
                expected_country=str((args or {}).get("expected_country") or ""),
            )
            return ok_json(report)
        if name == "list_exit_routes":
            return ok_json({"routes": discover_active_routes()})
        return err_result(f"unknown tool: {name}")
    except Exception as exc:
        return err_result(str(exc))


def answer(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ai-exit-check", "version": "0.1.0"},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        return handle_tool_call(params.get("name", ""), params.get("arguments") or {})
    if method == "ping":
        return {}
    return None


def main() -> None:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        request = json.loads(line)
        if "id" not in request:
            continue
        result = answer(request)
        reply: dict[str, Any] = {"jsonrpc": "2.0", "id": request["id"]}
        if result is None:
            reply["error"] = {"code": -32601, "message": "method not found"}
        else:
            reply["result"] = result
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
