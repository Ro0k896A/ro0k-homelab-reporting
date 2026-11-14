#!/usr/bin/env python3
"""Collect container state as one JSON line. Exit: 0 ok, 1 partial, 2 fatal write."""
import json, os, re, subprocess, sys
from datetime import datetime
from zoneinfo import ZoneInfo

OUT = os.environ.get("G600_RAW_DIR", "/srv/data/reports/raw")
EXPECTED = os.environ.get("G600_EXPECTED", "prometheus,grafana,jellyfin,postgres,vaultwarden,forgejo").split(",")
ERR = re.compile(r"\b(error|fatal|panic|critical)\b", re.I)
errors = {}

def run(key, cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            errors[key] = r.stderr.strip()[:200]
            return None
        return r.stdout
    except Exception as e:
        errors[key] = str(e)
        return None

def log_errors(name):
    try:
        r = subprocess.run(["docker", "logs", "--since", "24h", name],
                           capture_output=True, text=True, timeout=30)
        return sum(1 for l in (r.stdout + r.stderr).splitlines() if ERR.search(l))
    except Exception as e:
        errors[f"logs:{name}"] = str(e)
        return None

def main():
    now = datetime.now(ZoneInfo("America/New_York"))
    ids = run("docker_ps", ["docker", "ps", "-aq"])
    containers = []
    if ids is not None and ids.split():
        raw = run("docker_inspect", ["docker", "inspect"] + ids.split())
        for c in (json.loads(raw) if raw else []):
            s = c["State"]; name = c["Name"].lstrip("/")
            containers.append({
                "name": name, "status": s.get("Status"),
                "health": (s.get("Health") or {}).get("Status"),  # null = no healthcheck defined
                "restarts": c.get("RestartCount"), "started_at": s.get("StartedAt"),
                "exit_code": s.get("ExitCode"), "oom_killed": s.get("OOMKilled"),
                "log_error_lines_24h": log_errors(name),
            })
    present = {c["name"] for c in containers}
    rec = {
        "ts": now.isoformat(timespec="seconds"),
        "containers": containers,
        "missing_expected": sorted(set(EXPECTED) - present),
        "not_running": sorted(c["name"] for c in containers if c["status"] != "running"),
        "unhealthy": sorted(c["name"] for c in containers if c["health"] == "unhealthy"),
        "errors": errors,
    }
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, f"docker-{now:%Y-%m-%d}.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        print(f"FATAL write: {e}", file=sys.stderr); return 2
    print(json.dumps(rec, indent=2))
    return 1 if errors else 0

sys.exit(main())
