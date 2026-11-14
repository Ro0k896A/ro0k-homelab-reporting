#!/usr/bin/env python3
"""Collect SMART health per disk as one JSON line. Needs root. Exit: 0 ok, 1 partial, 2 fatal."""
import json, os, subprocess, sys
from datetime import datetime
from zoneinfo import ZoneInfo

OUT = os.environ.get("G600_RAW_DIR", "/srv/data/reports/raw")
errors = {}

def smart(dev):
    try:
        r = subprocess.run(["smartctl", "-j", "-H", "-A", f"/dev/{dev}"],
                           capture_output=True, text=True, timeout=30)
        d = json.loads(r.stdout)  # exit code is a bitmask; judge by parsed JSON
    except Exception as e:
        errors[dev] = str(e); return {"dev": dev, "passed": None}
    attrs = {a["id"]: a["raw"]["value"] for a in d.get("ata_smart_attributes", {}).get("table", [])}
    return {
        "dev": dev, "model": d.get("model_name"),
        "passed": d.get("smart_status", {}).get("passed"),
        "temp_c": d.get("temperature", {}).get("current"),
        "power_on_hours": d.get("power_on_time", {}).get("hours"),
        "reallocated": attrs.get(5), "pending": attrs.get(197),
    }

def main():
    if os.geteuid() != 0:
        print("FATAL: must run as root", file=sys.stderr); return 2
    now = datetime.now(ZoneInfo("America/New_York"))
    try:
        out = subprocess.run(["lsblk", "-dno", "NAME,TYPE"], capture_output=True, text=True, timeout=10).stdout
        devs = [l.split()[0] for l in out.splitlines() if len(l.split()) == 2 and l.split()[1] == "disk"]
    except Exception as e:
        print(f"FATAL lsblk: {e}", file=sys.stderr); return 2
    rec = {"ts": now.isoformat(timespec="seconds"), "disks": [smart(d) for d in devs]}
    rec["failing"] = [d["dev"] for d in rec["disks"] if d["passed"] is False]
    rec["unknown"] = [d["dev"] for d in rec["disks"] if d["passed"] is None]
    rec["errors"] = errors
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, f"smart-{now:%Y-%m-%d}.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        print(f"FATAL write: {e}", file=sys.stderr); return 2
    print(json.dumps(rec, indent=2))
    return 1 if (errors or rec["unknown"] or rec["failing"]) else 0

sys.exit(main())
