# G600 Homelab Reporting

Automated monitoring, operational reporting, and historical documentation
for the HP ProDesk 600 G2 SFF homelab server.

## Objectives
- Monitor host and service health.
- Collect system performance data.
- Track Docker services and storage.
- Generate scheduled operational reports.
- Maintain a reproducible reporting workflow.

## Reporting Schedule

| Frequency | Activity | GitHub |
|---|---|---|
| Daily | Health collection | No |
| Weekly | Operational summary | Yes |
| Monthly | Infrastructure review | Yes |
| Quarterly | Historical review | Yes |

## Architecture
- Host: Ubuntu Server
- Monitoring: Prometheus and Grafana
- Containers: Docker
- Automation: Python and cron
- Version control: Git

## Directory Structure
- docs/: Architecture and methodology
- scripts/: Collection and reporting scripts
- reports/: Generated reports
- logs/: Automation logs

## Privacy
No credentials, private keys, or sensitive user data
should be committed to this repository.
