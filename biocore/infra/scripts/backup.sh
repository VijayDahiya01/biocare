#!/usr/bin/env bash
# BioCore backup — PostgreSQL (always), MinIO objects + Milvus vectors (if reachable).
# Doc 5 §3.3: daily dump retained 30 days; Milvus & MinIO daily snapshot.
#
#   BACKUP_DIR=/backups RETENTION_DAYS=30 ./backup.sh
#
# IMPORTANT: run as a SUPERUSER (or a role with BYPASSRLS). Our tables use
# FORCE ROW LEVEL SECURITY, which filters even the table owner — so a dump by the
# app role (biocore) errors. The superuser bypasses RLS and dumps every row.
#
# Env:
#   BACKUP_DATABASE_URL  postgresql://postgres@host:port/db  (superuser; +psycopg stripped)
#   PG_BIN               optional dir holding pg_dump (else taken from PATH)
#   MINIO_ALIAS          optional `mc` alias for the MinIO server (enables object backup)
#   BACKUP_DIR           default ./backups     RETENTION_DAYS  default 30
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Prefer a dedicated superuser URL; fall back to DATABASE_URL. Strip +psycopg.
PG_URL="${BACKUP_DATABASE_URL:-${DATABASE_URL:-postgresql://postgres@localhost:5432/biocore}}"
PG_URL="${PG_URL/+psycopg/}"
PG_DUMP="${PG_BIN:+$PG_BIN/}pg_dump"

echo "[backup] PostgreSQL -> $BACKUP_DIR/pg-$STAMP.dump"
# ownership preserved (no --no-owner) so a superuser restore recreates biocore-owned tables.
"$PG_DUMP" --format=custom --dbname="$PG_URL" --file="$BACKUP_DIR/pg-$STAMP.dump"

# MinIO objects (documents, consent scans, receipts) — needs the `mc` client + alias.
if [[ -n "${MINIO_ALIAS:-}" ]] && command -v mc >/dev/null 2>&1; then
  echo "[backup] MinIO -> $BACKUP_DIR/minio-$STAMP/"
  mc mirror --overwrite "$MINIO_ALIAS" "$BACKUP_DIR/minio-$STAMP/"
else
  echo "[backup] MinIO skipped (set MINIO_ALIAS + install mc to enable)"
fi

# Milvus vectors — use the milvus-backup tool against the collection.
if command -v milvus-backup >/dev/null 2>&1; then
  echo "[backup] Milvus snapshot via milvus-backup"
  milvus-backup create -n "biocore-$STAMP"
else
  echo "[backup] Milvus skipped (install github.com/zilliztech/milvus-backup to enable)"
fi

echo "[backup] pruning dumps older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name 'pg-*.dump' -mtime +"$RETENTION_DAYS" -delete || true
echo "[backup] done: pg-$STAMP.dump"
