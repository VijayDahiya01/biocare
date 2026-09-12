#!/usr/bin/env bash
# BioCore restore — restore a PostgreSQL custom-format dump.
# Doc 5 §3.3: "a backup you haven't restored is not a backup" — run this monthly.
#
#   ./restore.sh ./backups/pg-20260616-020000.dump
#
# Run as a SUPERUSER (restore recreates biocore-owned, FORCE-RLS tables).
# Env:
#   BACKUP_DATABASE_URL  superuser URL (falls back to DATABASE_URL; +psycopg stripped)
#   PG_BIN               optional dir holding pg_restore
set -euo pipefail

DUMP="${1:?usage: restore.sh <dump-file>}"
PG_URL="${BACKUP_DATABASE_URL:-${DATABASE_URL:-postgresql://postgres@localhost:5432/biocore}}"
PG_URL="${PG_URL/+psycopg/}"
PG_RESTORE="${PG_BIN:+$PG_BIN/}pg_restore"

echo "[restore] restoring $DUMP -> $PG_URL"
# --clean --if-exists drops existing objects first; run against a fresh/staging DB.
"$PG_RESTORE" --clean --if-exists --no-owner --dbname="$PG_URL" "$DUMP"
echo "[restore] done. Verify row counts + run the app's /api/v1/ready check."
