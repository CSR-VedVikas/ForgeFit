#!/usr/bin/env bash
# ForgeFit — Postgres backup.
#
# Nothing else in this repo backs the database up, and the restore rehearsal
# is still an open pre-launch item. This is the ten-minute version: a nightly
# compressed dump with a retention window.
#
# Install on the host (adjust the path):
#
#   chmod +x ~/ForgeFit/deploy/backup.sh
#   crontab -e
#   15 3 * * * /home/ubuntu/ForgeFit/deploy/backup.sh >> /home/ubuntu/forgefit-backup.log 2>&1
#
# Restore (this WILL replace current data — read RESTORE below first):
#
#   gunzip -c backups/forgefit-YYYY-MM-DD.sql.gz | \
#     docker compose --env-file deploy/production.env exec -T db psql -U forgefit -d forgefit

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${FORGEFIT_BACKUP_DIR:-$REPO/backups}"
ENV_FILE="$REPO/deploy/production.env"
KEEP_DAYS="${FORGEFIT_BACKUP_KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

stamp="$(date +%F-%H%M)"
out="$BACKUP_DIR/forgefit-$stamp.sql.gz"

echo "[$(date -Is)] dumping to $out"

# --clean --if-exists so the dump can be replayed over an existing database.
docker compose --env-file "$ENV_FILE" -f "$REPO/docker-compose.yml" \
  exec -T db pg_dump -U forgefit -d forgefit --clean --if-exists \
  | gzip -9 > "$out.partial"

# Only promote once the pipeline succeeded, so a failed run never leaves a
# truncated file that looks like a good backup.
mv "$out.partial" "$out"

size=$(du -h "$out" | cut -f1)
echo "[$(date -Is)] ok, $size"

# A dump that restores to nothing is worse than no dump — refuse to keep it.
if [ "$(gunzip -c "$out" | head -c 100 | wc -c)" -lt 100 ]; then
  echo "[$(date -Is)] FAILED: dump looks empty, removing" >&2
  rm -f "$out"
  exit 1
fi

deleted=$(find "$BACKUP_DIR" -name 'forgefit-*.sql.gz' -mtime "+$KEEP_DAYS" -print -delete | wc -l)
echo "[$(date -Is)] pruned $deleted backup(s) older than $KEEP_DAYS days"

# RESTORE
# -------
# Test this BEFORE you need it. On a scratch database:
#
#   docker compose --env-file deploy/production.env exec -T db \
#     psql -U forgefit -d postgres -c 'CREATE DATABASE restore_test;'
#   gunzip -c backups/<file>.sql.gz | docker compose --env-file deploy/production.env \
#     exec -T db psql -U forgefit -d restore_test
#   docker compose --env-file deploy/production.env exec -T db \
#     psql -U forgefit -d restore_test -c 'SELECT count(*) FROM users;'
#
# If that row count matches production, the backup is real.
