#!/usr/bin/env bash
# Tägliches Datenbank-Backup (per Cron: 0 3 * * * /opt/n8n/backup.sh)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
docker compose exec -T postgres pg_dump -U n8n n8n | gzip > "backups/n8n-$(date +%F).sql.gz"
find backups -name 'n8n-*.sql.gz' -mtime +14 -delete
