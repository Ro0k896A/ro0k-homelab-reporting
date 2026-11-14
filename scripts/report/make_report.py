#!/usr/bin/env python3
"""Build a Markdown report from raw JSONL. Usage: make_report.py weekly|monthly|quarterly
Missing data prints as n/a, never 0. Exit: 0 ok, 1 no data found."""
import glob, json, os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DAYS = {"weekly": 7, "monthly": 31, "quarterly": 92}
RAW = os.environ.get("G600_RAW_DIR", "/srv/data/reports/raw")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
period = sys.argv[1] if len(sys.argv) > 1 else "weekly"
now = datetime.now(ZoneInfo("America/New_York"))
cut = now - timedelta(days=DAYS[period])

def load(kind):
    rows = []
    for p in sorted(glob.glob(os.path.join(RAW, f"{kind}-*.jsonl"))):
        for line in open(p):
            try:
                r = json.loads(line)
                if datetime.fromisoformat(r["ts"]) >= cut: rows.append(r)
            except Exception: continue
    return rows

def vals(rows, f):
    out = []
    for r in rows:
        try:
            v = f(r)
            if v is not None: out.append(v)
        except Exception: pass
    return out

def fmt(v, nd=1): return "n/a" if v is None else f"{v:.{nd}f}"
def avg(x): return sum(x)/len(x) if x else None
def mx(x): return max(x) if x else None
def mn(x): return min(x) if x else None

host, dock, smart = load("host"), load("docker"), load("smart")
if not (host or dock or smart):
    print(f"No data in {RAW} for the last {DAYS[period]} days", file=sys.stderr); sys.exit(1)

L = [f"# G600 {period.capitalize()} Report", "",
     f"Generated {now:%Y-%m-%d %H:%M %Z} | window: last {DAYS[period]} days | "
     f"samples: host={len(host)} docker={len(docker) if (docker:=dock) else 0} smart={len(smart)}", ""]

L += ["## Host", "", "| Metric | Avg | Max/Min |", "|---|---|---|"]
for name, f, agg, lab in [
    ("Load (1m)", lambda r: r["load"]["1m"], mx, "max"),
    ("CPU util % (5m)", lambda r: r["cpu_util_pct_5m"], mx, "max"),
    ("CPU temp C", lambda r: r["cpu_temp_c"], mx, "max"),
    ("RAM available MB", lambda r: r["mem_avail_mb"], mn, "min")]:
    v = vals(host, f)
    L.append(f"| {name} | {fmt(avg(v))} | {fmt(agg(v))} ({lab}) |")
if host:
    h = host[-1]
    d = (h.get("disks") or [None])[0]
    L += ["", f"- Latest uptime: {fmt(h['uptime_s']/86400 if h.get('uptime_s') is not None else None)} days",
          f"- Filesystem used: {fmt(d['pct']) + '%' if d else 'n/a'} (/srv/data and /srv/backup share one filesystem)",
          f"- Swap used MB: {fmt(h['swap_total_mb']-h['swap_free_mb'] if h.get('swap_total_mb') is not None else None, 0)}",
          f"- Failed systemd units: {h.get('failed_units', 'n/a')} | Pending updates: {h.get('pending_updates', 'n/a')}",
          f"- SSH failed-login signals (24h, peak in window): {fmt(mx(vals(host, lambda r: r['ssh_failed_24h'])), 0)}"]
    boots = sorted({r["boot_epoch"]//60 for r in host if r.get("boot_epoch")})
    L.append(f"- Reboots detected in window: {max(len(boots)-1, 0)}")
else:
    L.append("\nNo host data.")

L += ["", "## Docker", ""]
if dock:
    k = dock[-1]
    L += ["| Container | Status | Health | Restarts | Error lines 24h |", "|---|---|---|---|---|"]
    for c in k["containers"]:
        L.append(f"| {c['name']} | {c['status']} | {c['health'] or 'no check'} | "
                 f"{c['restarts'] if c['restarts'] is not None else 'n/a'} | "
                 f"{c['log_error_lines_24h'] if c['log_error_lines_24h'] is not None else 'n/a'} |")
    L.append(f"\nMissing expected: {', '.join(k['missing_expected']) or 'none'} | "
             f"Not running: {', '.join(k['not_running']) or 'none'} | Unhealthy: {', '.join(k['unhealthy']) or 'none'}")
else:
    L.append("No Docker data.")

L += ["", "## SMART", ""]
if smart:
    L += ["| Disk | Model | Passed | Temp C | Power-on h | Reallocated | Pending |", "|---|---|---|---|---|---|---|"]
    for d in smart[-1]["disks"]:
        g = lambda k: "n/a" if d.get(k) is None else d[k]
        L.append(f"| {d['dev']} | {g('model')} | {g('passed')} | {g('temp_c')} | {g('power_on_hours')} | {g('reallocated')} | {g('pending')} |")
else:
    L.append("No SMART data.")

L += ["", "## Backups", "", "Restic status not assessed (setup deferred).", "", "## Known issues", ""]
ki = os.path.join(REPO, "config", "known_issues.txt")
L += [f"- {l.strip()}" for l in open(ki) if l.strip()] if os.path.exists(ki) else ["- none recorded"]

outdir = os.path.join(REPO, "reports", period); os.makedirs(outdir, exist_ok=True)
path = os.path.join(outdir, f"{period}-{now:%Y-%m-%d}.md")
open(path, "w").write("\n".join(L) + "\n")
print(path)
