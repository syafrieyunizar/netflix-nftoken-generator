#!/usr/bin/env python3
"""
Netflix NFToken Generator

Generate Netflix auto-login links from session cookies.
Single file, minimal dependencies.

Usage:
    python3 nftoken_generator.py [--config config.json] [--daemon] [--interval 3000]

Modes:
    one-shot  : Generate one link, print it, exit.
    daemon    : Auto-refresh link before expiry, print/update continuously.

Features:
- Input: Netflix cookies (NetflixId required, SecureNetflixId + nfvdid optional)
- Output: https://netflix.com/?nftoken=...
- Expiry detection (~65 minutes TTL)
- Auto-refresh mode (daemon)
- Optional Telegram notification on each refresh
- Config file or CLI args
"""

import json
import os
import sys
import time
import argparse
import urllib.parse
import requests
from datetime import datetime, timezone
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

__version__ = "1.0.0"

# ─── Netflix API ─────────────────────────────────────────────────────────────

API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"

QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

# ─── Config ──────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "netflix_id": "",
    "secure_netflix_id": "",
    "nfvdid": "",
    "refresh_interval_sec": 3000,  # 50 minutes (token TTL ~65 min)
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
    },
    "output_file": "",  # if set, write link to this file on each refresh
}

CONFIG = dict(DEFAULT_CONFIG)

# ─── Utilities ───────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def format_timestamp(ts_ms):
    """Convert millisecond timestamp to human-readable string."""
    if not ts_ms:
        return "Unknown"
    ts_sec = ts_ms / 1000 if ts_ms > 1e12 else ts_ms
    try:
        dt = datetime.fromtimestamp(ts_sec)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts_ms)


def seconds_until_expiry(ts_ms):
    """Calculate seconds remaining until expiry."""
    if not ts_ms:
        return 0
    ts_sec = ts_ms / 1000 if ts_ms > 1e12 else ts_ms
    now = datetime.now().timestamp()
    return max(0, int(ts_sec - now))


# ─── Cookie Parsing ──────────────────────────────────────────────────────────

def parse_cookies_from_json(json_data):
    """Parse cookies from browser export JSON format (list of cookie objects)."""
    cookies = {}
    if isinstance(json_data, list):
        for cookie in json_data:
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            if name in ("NetflixId", "SecureNetflixId", "nfvdid"):
                cookies[name] = urllib.parse.unquote(value) if "%" in value else value
    elif isinstance(json_data, dict):
        for key in ("NetflixId", "SecureNetflixId", "nfvdid"):
            if key in json_data:
                cookies[key] = json_data[key]
        if "cookies" in json_data and isinstance(json_data["cookies"], list):
            for cookie in json_data["cookies"]:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name in ("NetflixId", "SecureNetflixId", "nfvdid"):
                    cookies[name] = urllib.parse.unquote(value) if "%" in value else value
    return cookies


def parse_cookies_from_string(cookie_str):
    """Parse cookies from raw Cookie header string format."""
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            if k in ("NetflixId", "SecureNetflixId", "nfvdid"):
                cookies[k] = urllib.parse.unquote(v) if "%" in v else v
    return cookies


def parse_cookies_from_file(filepath):
    """Parse cookies from file. Supports JSON, Netscape, or raw cookie string."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # Try JSON first
    try:
        data = json.loads(content)
        cookies = parse_cookies_from_json(data)
        if cookies.get("NetflixId"):
            return cookies
    except json.JSONDecodeError:
        pass

    # Try raw cookie string
    cookies = parse_cookies_from_string(content)
    if cookies.get("NetflixId"):
        return cookies

    # Try Netscape format (tab-separated)
    for line in content.splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 7:
            name, value = parts[5], parts[6]
            if name in ("NetflixId", "SecureNetflixId", "nfvdid"):
                cookies[name] = urllib.parse.unquote(value) if "%" in value else value

    return cookies


# ─── NFToken Generation ──────────────────────────────────────────────────────

def generate_nftoken(netflix_id, secure_netflix_id="", nfvdid=""):
    """
    Call Netflix API to generate nftoken.
    
    Returns: (token, expires_ms) or raises exception.
    """
    if not netflix_id:
        raise ValueError("NetflixId cookie is required")

    headers = dict(BASE_HEADERS)

    # Build cookie string
    cookie_parts = [f"NetflixId={netflix_id}"]
    if secure_netflix_id:
        cookie_parts.append(f"SecureNetflixId={secure_netflix_id}")
    if nfvdid:
        cookie_parts.append(f"nfvdid={nfvdid}")
    headers["Cookie"] = "; ".join(cookie_parts)

    response = requests.get(
        API_URL,
        params=QUERY_PARAMS,
        headers=headers,
        timeout=30,
        verify=False,
    )
    response.raise_for_status()

    data = response.json()

    # Navigate: value.account.token.default.{token, expires}
    token_data = (
        ((data.get("value") or {}).get("account") or {}).get("token") or {}
    ).get("default") or {}

    token = token_data.get("token")
    expires = token_data.get("expires")

    if not token:
        raise ValueError(
            "No token in response. Cookie might be expired or invalid. "
            "Make sure NetflixId is from an active logged-in session."
        )

    return token, expires


def build_nftoken_link(token):
    """Build the auto-login URL."""
    return "https://netflix.com/?nftoken=" + urllib.parse.quote(token)


# ─── Telegram ────────────────────────────────────────────────────────────────

def send_telegram(message, bot_token, chat_id):
    """Send notification via Telegram bot."""
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


# ─── Main ────────────────────────────────────────────────────────────────────

def load_config(path):
    if path and os.path.exists(path):
        with open(path) as f:
            CONFIG.update(json.load(f))
        log(f"Config loaded: {path}")


def run_oneshot():
    """Generate one nftoken link and exit."""
    netflix_id = CONFIG.get("netflix_id", "")
    if not netflix_id:
        log("ERROR: netflix_id is empty. Set it in config.json or pass --netflix-id")
        sys.exit(1)

    try:
        token, expires = generate_nftoken(
            netflix_id,
            CONFIG.get("secure_netflix_id", ""),
            CONFIG.get("nfvdid", ""),
        )
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)

    link = build_nftoken_link(token)
    ttl = seconds_until_expiry(expires)

    print()
    print("=" * 60)
    print("  Netflix NFToken Generated")
    print("=" * 60)
    print()
    print(f"  Link:    {link}")
    print()
    print(f"  Expires: {format_timestamp(expires)}")
    print(f"  TTL:     {ttl} seconds ({ttl // 60} minutes)")
    print()
    print("  How to use:")
    print("    Send the link above to anyone.")
    print("    When they open it, they will be auto-logged into")
    print("    the Netflix account (no password needed).")
    print()
    print("  Note:")
    print("    - Link expires in ~65 minutes")
    print("    - Link may be one-time use")
    print("    - Old links stop working after generating a new one")
    print("=" * 60)
    print()

    # Write to output file if configured
    outfile = CONFIG.get("output_file", "")
    if outfile:
        with open(outfile, "w") as f:
            f.write(link + "\n")
        log(f"Link written to: {outfile}")

    # Send Telegram notification if configured
    tg = CONFIG.get("telegram", {})
    if tg.get("enabled"):
        msg = f"Netflix NFToken\n\nLink: {link}\nExpires: {format_timestamp(expires)}\nTTL: {ttl // 60} minutes"
        send_telegram(msg, tg.get("bot_token", ""), tg.get("chat_id", ""))


def run_daemon():
    """Auto-refresh nftoken link before expiry."""
    netflix_id = CONFIG.get("netflix_id", "")
    if not netflix_id:
        log("ERROR: netflix_id is empty.")
        sys.exit(1)

    interval = CONFIG.get("refresh_interval_sec", 3000)  # default 50 min
    log(f"Daemon mode started")
    log(f"  Refresh interval: {interval} seconds ({interval // 60} minutes)")
    log(f"  NetflixId: {'set' if netflix_id else 'empty'}")
    log(f"  Output file: {CONFIG.get('output_file', 'none')}")

    tg = CONFIG.get("telegram", {})
    if tg.get("enabled"):
        log(f"  Telegram: enabled (chat_id={tg.get('chat_id', '?')})")
    else:
        log(f"  Telegram: disabled")

    log("")

    while True:
        try:
            token, expires = generate_nftoken(
                netflix_id,
                CONFIG.get("secure_netflix_id", ""),
                CONFIG.get("nfvdid", ""),
            )
            link = build_nftoken_link(token)
            ttl = seconds_until_expiry(expires)

            log(f"NFToken generated | TTL: {ttl // 60} min | Expires: {format_timestamp(expires)}")
            log(f"Link: {link[:80]}...")

            # Write to output file
            outfile = CONFIG.get("output_file", "")
            if outfile:
                with open(outfile, "w") as f:
                    f.write(link + "\n")
                log(f"Written to: {outfile}")

            # Telegram notification
            if tg.get("enabled"):
                msg = f"Netflix NFToken Refreshed\n\nLink: {link}\nExpires: {format_timestamp(expires)}\nTTL: {ttl // 60} minutes"
                if send_telegram(msg, tg.get("bot_token", ""), tg.get("chat_id", "")):
                    log("Telegram: sent")
                else:
                    log("Telegram: failed")

            log(f"Next refresh in {interval // 60} minutes...")
            log("")

            time.sleep(interval)

        except KeyboardInterrupt:
            log("Stopped by user.")
            break
        except Exception as e:
            log(f"ERROR: {e}")
            log(f"Retrying in 60 seconds...")
            time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="Netflix NFToken Generator")
    parser.add_argument("--config", type=str, default=None, help="Path to config.json")
    parser.add_argument("--daemon", action="store_true", help="Run in auto-refresh mode")
    parser.add_argument("--interval", type=int, default=None, help="Refresh interval in seconds (daemon mode)")
    parser.add_argument("--netflix-id", type=str, default=None, help="NetflixId cookie value")
    parser.add_argument("--cookie-file", type=str, default=None, help="File containing Netflix cookies (JSON/string)")
    parser.add_argument("--output", type=str, default=None, help="Write link to this file")
    parser.add_argument("--version", action="version", version=f"nftoken-generator {__version__}")
    args = parser.parse_args()

    # Load config
    config_path = args.config
    if not config_path:
        for p in ["./config.json", os.path.expanduser("~/.config/nftoken/config.json")]:
            if os.path.exists(p):
                config_path = p
                break
    load_config(config_path)

    # CLI overrides
    if args.netflix_id:
        CONFIG["netflix_id"] = args.netflix_id
    if args.interval:
        CONFIG["refresh_interval_sec"] = args.interval
    if args.output:
        CONFIG["output_file"] = args.output

    # Load cookies from file if specified
    if args.cookie_file:
        cookies = parse_cookies_from_file(args.cookie_file)
        if cookies.get("NetflixId"):
            CONFIG["netflix_id"] = cookies["NetflixId"]
            if cookies.get("SecureNetflixId"):
                CONFIG["secure_netflix_id"] = cookies["SecureNetflixId"]
            if cookies.get("nfvdid"):
                CONFIG["nfvdid"] = cookies["nfvdid"]
            log(f"Cookies loaded from: {args.cookie_file}")
        else:
            log(f"ERROR: No NetflixId found in {args.cookie_file}")
            sys.exit(1)

    # Run
    if args.daemon:
        run_daemon()
    else:
        run_oneshot()


if __name__ == "__main__":
    main()
