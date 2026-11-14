#!/usr/bin/env python3
"""Collect host health as one JSON line. Missing data -> null + errors entry.
Exit: 0 ok, 1 partial (some errors), 2 fatal (cannot write)."""
import json, os, shutil, socket, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

PROM = os.environ.get("PROM_URL", "http://172.17.0.1:9091")
OUT = os.environ.get("G600_RAW_DIR", "/srv/data/reports/raw")
errors = {}

def run(key, cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception as e:
        errors[key] = str(e)
        return None

def prom(key, q):
    try:
        u = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": q})
        d = json.load(urllib.request.urlopen(u, timeout=5))
        return round(float(d["data"]["result"][0]["value"][1]), 2)
    except Exception as e:
        errors[key] = str(e)
        return None

def meminfo():
    try:
        m = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
        mb = lambda k: round(m[k] / 1024)
        return {"mem_total_mb": mb("MemTotal"), "mem_avail_mb": mb("MemAvailable"),
                "swap_total_mb": mb("SwapTotal"), "swap_free_mb": mb("SwapFree")}
    except Exception as e:
        errors["meminfo"] = str(e)
        return {}

def cpu_temp():
    out = run("cpu_temp", ["sensors", "-j"])
    try:
        return json.loads(out)["coretemp-isa-0000"]["Package id 0"]["temp1_input"]
    except Exception as e:
        errors["cpu_temp"] = str(e)
        return None

def disk(path):
    try:
        u = shutil.disk_usage(path)
        return {"path": path, "total_gb": round(u.total/1e9, 1), "used_gb": round(u.used/1e9, 1),
                "pct": round(u.used/(u.used+u.free)*100, 1), "dev": os.stat(path).st_dev}
    except Exception as e:
        errors[f"disk:{path}"] = str(e)
        return None

def count_lines(key, cmd, skip=0):
    out = run(key, cmd)
    return None if out is None else max(len([l for l in out.splitlines() if l.strip()]) - skip, 0)

def main():
    now = datetime.now(ZoneInfo("America/New_York"))
    up = None
    try: up = int(float(open("/proc/uptime").read().split()[0]))
    except Exception as e: errors["uptime"] = str(e)
    try: l1, l5, l15 = (float(x) for x in open("/proc/loadavg").read().split()[:3])
    except Exception as e: l1 = l5 = l15 = None; errors["loadavg"] = str(e)
    ssh = run("ssh_failed", ["journalctl", "-u", "ssh", "--since", "-24h", "--no-pager", "-o", "cat"])
    ssh_failed = None if ssh is None else sum(("Failed password" in l or "Invalid user" in l or "invalid user" in l) for l in ssh.splitlines())
    rec = {
        "ts": now.isoformat(timespec="seconds"), "host": socket.gethostname(),
        "load": {"1m": l1, "5m": l5, "15m": l15},
        "cpu_util_pct_5m": prom("cpu_util", '100-avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))*100'),
        "cpu_temp_c": cpu_temp(), **meminfo(),
        "uptime_s": up, "boot_epoch": int(time.time()-up) if up is not None else None,
        "disks": [d for d in (disk("/srv/data"), disk("/srv/backup")) if d],
        "failed_units": count_lines("failed_units", ["systemctl", "--failed", "--plain", "--no-legend"]),
        "pending_updates": count_lines("updates", ["sh", "-c", "apt list --upgradable 2>/dev/null"], skip=1),
        "ssh_failed_24h": ssh_failed,
    }
    rec["errors"] = errors
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, f"host-{now:%Y-%m-%d}.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        print(f"FATAL write: {e}", file=sys.stderr); return 2
    print(json.dumps(rec, indent=2))
    return 1 if errors else 0

sys.exit(main())
