"""Update the Vast.ai instance public IP in opencode.json (Vastai provider only).

Usage:
  python update_vastai_ip.py               # 1 running instance -> update it; several -> pick
  python update_vastai_ip.py 47991049      # explicit instance ID
  python update_vastai_ip.py --wait        # only update after the new /v1/models answers properly
  python update_vastai_ip.py --wait --timeout 600

API key read from $VASTAI_API_KEY.
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests
import urllib3
from vastai import VastAI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
POLL_INTERVAL = 5


def get_client():
    key = os.environ.get("VASTAI_API_KEY")
    if not key:
        sys.exit("error: VASTAI_API_KEY environment variable is not set")
    return VastAI(api_key=key)


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        sys.exit("error: interactive prompt requires a terminal")


def fmt_uptime(start_date):
    if not start_date:
        return "-"
    secs = max(0, int(time.time() - start_date))
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def pick_instance(running, explicit_id):
    if explicit_id is not None:
        for inst in running:
            if inst["id"] == explicit_id:
                return inst
        ids = ", ".join(str(i["id"]) for i in running)
        sys.exit(f"error: instance {explicit_id} not running (running: {ids})")
    if len(running) == 1:
        return running[0]
    print(f"{len(running)} running instances:")
    for n, inst in enumerate(running, 1):
        ip = inst.get("public_ipaddr") or "no public IP"
        gpu = inst.get("gpu_name") or "-"
        ng = inst.get("num_gpus")
        gpu = f"{int(ng)}x {gpu}" if ng else gpu
        price = inst.get("dph_total")
        price_s = f"${price:.4f}/hr" if price is not None else "-/hr"
        print(f"  {n}. id={inst['id']}  label={inst.get('label') or '-'}  gpu={gpu}  ip={ip}  {price_s}  up {fmt_uptime(inst.get('start_date'))}")
    while True:
        text = ask("Pick number to update: ")
        if text.isdigit() and 1 <= int(text) <= len(running):
            return running[int(text) - 1]
        print("invalid number")


def swap_ip(old_base, new_ip):
    p = urlparse(old_base)
    netloc = f"{new_ip}:{p.port}" if p.port else new_ip
    return urlunparse(p._replace(netloc=netloc))


def endpoint_ready(base, timeout_s):
    """Poll <base>/models until it answers in the OpenAI list format. (ok, detail)"""
    url = base.rstrip("/") + "/models"
    deadline = time.time() + timeout_s
    last_err = "not started"
    while time.time() < deadline:
        payload = None
        try:
            r = requests.get(url, verify=False, timeout=15)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                payload = r.json()
                if payload.get("object") == "list" and payload.get("data"):
                    models = ", ".join(str(m.get("id")) for m in payload["data"])
                    return True, f"ready: {models}"
            last_err = f"status {r.status_code}" if payload is None else "body not a model list"
        except Exception as e:
            last_err = str(e)
        time.sleep(POLL_INTERVAL)
    return False, f"not ready within {timeout_s:.0f}s (last: {last_err})"


def update_config(old_base, new_base):
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if cfg["provider"]["Vastai"]["options"]["baseURL"] != old_base:
        sys.exit("error: config changed since read; re-run")
    text = CONFIG_PATH.read_text(encoding="utf-8")
    needle = f'"{old_base}"'
    if needle not in text:
        sys.exit("error: exact baseURL string not found in opencode.json; file untouched")
    new_text = text.replace(needle, f'"{new_base}"', 1)
    parsed = json.loads(new_text)
    if parsed["provider"]["Vastai"]["options"]["baseURL"] != new_base:
        sys.exit("error: sanity check failed; file untouched")
    shutil.copy2(CONFIG_PATH, str(CONFIG_PATH) + ".bak")
    CONFIG_PATH.write_text(new_text, encoding="utf-8")
    final = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if final["provider"]["Vastai"]["options"]["baseURL"] != new_base:
        sys.exit("error: post-write check failed")
    print(f"backup: {str(CONFIG_PATH)} -> {str(CONFIG_PATH)}.bak")


def main(argv):
    wait = False
    timeout = 300.0
    explicit = None
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--wait":
            wait = True
        elif a == "--timeout":
            i += 1
            if i >= len(argv):
                sys.exit("error: --timeout needs a value in seconds")
            timeout = float(argv[i])
        elif a in ("--help", "-h"):
            print(__doc__.strip())
            return 0
        else:
            rest.append(a)
        i += 1
    if len(rest) > 1:
        sys.exit("error: expected at most one instance ID")
    if rest:
        if not rest[0].isdigit():
            sys.exit(f"error: {rest[0]!r} is not an instance ID")
        explicit = int(rest[0])

    client = get_client()
    running = [i for i in client.show_instances() if i.get("actual_status") == "running"]
    if not running:
        sys.exit("error: no running instances")

    inst = pick_instance(running, explicit)
    new_ip = inst.get("public_ipaddr")
    if not new_ip:
        sys.exit(f"error: instance {inst['id']} has no public IP")

    old_base = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["provider"]["Vastai"]["options"]["baseURL"]
    new_base = swap_ip(old_base, new_ip)
    print(f"instance {inst['id']} public IP: {new_ip}")
    print(f"Vastai baseURL: {old_base} -> {new_base}")
    if new_base == old_base:
        print("already up to date; no changes")
        return 0

    if wait:
        print(f"waiting up to {timeout:.0f}s for {new_base}/models ...")
        ok, detail = endpoint_ready(new_base, timeout)
        if not ok:
            sys.exit(f"error: {detail}; opencode.json unchanged")
        print(detail)

    update_config(old_base, new_base)
    print(f"updated {CONFIG_PATH}")
    print("restart opencode to pick up the new config")
    if not wait:
        print("hint: the model server may still be booting; re-run with --wait to verify")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
