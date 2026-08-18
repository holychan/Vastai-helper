"""Stop a Vast.ai instance.

Usage:
  python stop_instance.py            # interactive: list running instances, pick by number
  python stop_instance.py 12345      # stop instance 12345 directly
  python stop_instance.py 12345 --yes   # skip confirmation (for scripting)
  python stop_instance.py 12345 --force # also permit stopping the instance serving this opencode session
  python stop_instance.py --stop_opencode_session  # stop the instance serving this opencode session, no confirmation

API key read from $VASTAI_API_KEY.
"""

import json
import os
import re
import socket
import sqlite3
import sys
import time
from pathlib import Path

from vastai import VastAI

try:
    import psutil
except ImportError:
    psutil = None

CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def get_client():
    key = os.environ.get("VASTAI_API_KEY")
    if not key:
        sys.exit("error: VASTAI_API_KEY environment variable is not set")
    return VastAI(api_key=key)


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


def fmt_disk(inst):
    used, total = inst.get("disk_usage"), inst.get("disk_space")
    if used is None or used < 0 or total is None:
        return "-"
    return f"{used:.1f}/{total:.0f}"


def print_table(running, cur_ids=frozenset()):
    rows = []
    for inst in running:
        gpu = inst.get("gpu_name") or "-"
        n = inst.get("num_gpus")
        gpu = f"{int(n)}x {gpu}" if n else gpu
        price = inst.get("dph_total")
        rows.append([
            str(len(rows) + 1),
            str(inst["id"]),
            inst.get("label") or "-",
            gpu,
            inst.get("geolocation") or "-",
            inst.get("public_ipaddr") or "-",
            f"${price:.4f}" if price is not None else "-",
            str(inst.get("machine_id", "-")),
            fmt_uptime(inst.get("start_date")),
            fmt_disk(inst),
            "<- you" if inst["id"] in cur_ids else "",
        ])
    headers = ["#", "ID", "LABEL", "GPU", "LOCATION", "PUBLIC IP", "$/HR", "MACHINE", "UPTIME", "DISK (GB)", "CUR"]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))


def stop_instances(client, ids):
    ok = True
    for iid in ids:
        result = client.stop_instance(iid)
        print(f"stop {iid}: {result}")
        if not result.get("success", True):
            ok = False
    return ok


def parse_numbers(text, valid):
    nums = []
    for tok in text.split():
        if not tok.isdigit() or int(tok) not in valid:
            sys.exit(f"error: {tok!r} is not a table number above")
        nums.append(int(tok))
    return nums


def opencode_pids():
    pids = set()
    for p in psutil.process_iter(["name"]):
        if "opencode" in (p.info["name"] or "").lower():
            pids.add(p.pid)
    return pids


def live_provider_ips():
    """Remote IPs of established connections owned by opencode processes."""
    ips = set()
    pids = opencode_pids()
    for c in psutil.net_connections(kind="inet"):
        if c.status == psutil.CONN_ESTABLISHED and c.raddr and c.pid in pids:
            ips.add(c.raddr.ip)
    return ips


def host_to_ips(host):
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host):
        return {host}
    try:
        return {a[4][0] for a in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        return set()


def config_provider_ips():
    """Fallback: newest active session's provider (DB) -> its baseURL host (config)."""
    cfg = json.loads(CONFIG_PATH.read_text())
    provider = None
    if DB_PATH.exists():
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            row = con.execute(
                "select model from session where time_archived is null "
                "order by time_updated desc limit 1"
            ).fetchone()
            if row and row[0]:
                provider = json.loads(row[0]).get("providerID")
        finally:
            con.close()
    if not provider:
        model = cfg.get("model") or ""
        provider = model.split("/", 1)[0] if model else None
    if not provider:
        raise LookupError("no active provider found")
    base = cfg["provider"][provider]["options"]["baseURL"]
    host = base.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0]
    return host_to_ips(host)


def find_current_ips():
    """(ips, notes) — instances serving this opencode session, best effort."""
    ips, notes = set(), []
    if psutil:
        try:
            ips |= live_provider_ips()
            notes.append("live opencode connections")
        except Exception as e:
            notes.append(f"live connections: {e}")
    if not ips:
        try:
            ips |= config_provider_ips()
            notes.append("opencode session db + config")
        except Exception as e:
            notes.append(f"config fallback: {e}")
    return ips, notes


def main(argv):
    yes = force = stop_current = False
    args = []
    for a in argv:
        if a == "--yes":
            yes = True
        elif a == "--force":
            force = True
        elif a == "--stop_opencode_session":
            stop_current = True
        elif a in ("--help", "-h"):
            print(__doc__.strip())
            return 0
        else:
            args.append(a)
    if args:
        for tok in args:
            if not tok.isdigit():
                sys.exit(f"error: {tok!r} is not an instance ID")
        direct_ids = [int(a) for a in args]
    else:
        direct_ids = None

    client = get_client()
    running = [i for i in client.show_instances() if i.get("actual_status") == "running"]

    cur_ips, cur_notes = find_current_ips()
    cur_ids = {i["id"] for i in running if {i.get("public_ipaddr"), i.get("ssh_host")} & cur_ips}
    if cur_ids:
        print(f"note: instance(s) {sorted(cur_ids)} serve your opencode session ({', '.join(cur_notes)})")
    elif cur_notes:
        print(f"warning: could not detect current opencode instance ({'; '.join(cur_notes)})")

    if stop_current:
        if not cur_ids:
            sys.exit("error: could not detect the instance serving this opencode session")
        ids = sorted(cur_ids)
        print(f"stopping instance(s) {ids} (serving this opencode session)")
        return 0 if stop_instances(client, ids) else 1

    if not running:
        if direct_ids:
            sys.exit("error: no running instances")
        print("No running instances.")
        return 0

    if direct_ids:
        valid = {i["id"] for i in running}
        unknown = [d for d in direct_ids if d not in valid]
        if unknown:
            sys.exit(f"error: instance(s) {unknown} not in running list")
        hitting = [d for d in direct_ids if d in cur_ids]
        if hitting and not force:
            sys.exit(f"error: instance(s) {hitting} serve your current opencode session; add --force to stop anyway")
        if not yes and not force:
            answer = input(f"Stop instance(s) {direct_ids}? [y/N] ").strip().lower()
            if answer != "y":
                print("aborted")
                return 1
        return 0 if stop_instances(client, direct_ids) else 1

    print_table(running, cur_ids)
    print()
    num_to_id = {i: inst["id"] for i, inst in enumerate(running, start=1)}
    while True:
        text = input("Number to stop (space-separated for multiple, q to quit): ").strip()
        if text.lower() == "q":
            return 0
        if not text:
            continue
        nums = parse_numbers(text, num_to_id)
        ids = [num_to_id[n] for n in nums]
        desc = ", ".join(f"#{n} ({i})" for n, i in zip(nums, ids))
        answer = input(f"Stop instance(s) {desc}? [y/N] ").strip().lower()
        if answer != "y":
            continue
        hitting = [i for i in ids if i in cur_ids]
        if hitting:
            answer2 = input(f"warning: {hitting} serve your current opencode session and will die. Stop anyway? [y/N] ").strip().lower()
            if answer2 != "y":
                continue
        if stop_instances(client, ids):
            return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
