#!/bin/bash
# Core Accounting database backup (production Compose project).
# Usage, from the repository root, with the production stack running:
#   ./backups/backup.sh
#   ./backups/backup.sh --restore backups/core_accounting_YYYYMMDD-HHMMSS.sql.gz
#
# DB_CONTAINER, when set, uses `docker exec` against that container instead of
# `docker compose exec` (older installs).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/docker-compose.prod.yml}"
DB_USER="${DB_USER:-accounting}"
DB_NAME="${DB_NAME:-core_accounting}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/core_accounting_${TIMESTAMP}.sql.gz"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
error(){ echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

dump_cmd() {
    if [[ -n "${DB_CONTAINER:-}" ]]; then
        docker exec "${DB_CONTAINER}" pg_dump \
            -U "${DB_USER}" \
            -d "${DB_NAME}" \
            --no-owner \
            --no-acl \
            --clean \
            --if-exists
    else
        docker compose -f "${COMPOSE_FILE}" exec -T db pg_dump \
            -U "${DB_USER}" \
            -d "${DB_NAME}" \
            --no-owner \
            --no-acl \
            --clean \
            --if-exists
    fi
}

restore_cmd() {
    if [[ -n "${DB_CONTAINER:-}" ]]; then
        docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}"
    else
        docker compose -f "${COMPOSE_FILE}" exec -T db psql -U "${DB_USER}" -d "${DB_NAME}"
    fi
}

do_backup() {
    log "Starting database backup..."
    mkdir -p "${BACKUP_DIR}"

    dump_cmd | gzip > "${BACKUP_FILE}"

    log "Backup saved: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

    find "${BACKUP_DIR}" -name "core_accounting_*.sql.gz" -mtime +30 -delete
    log "Cleaned up backups older than 30 days"
}

do_restore() {
    local restore_file="$1"
    if [[ ! -f "${restore_file}" ]]; then
        error "File not found: ${restore_file}"
    fi

    log "WARNING: This will overwrite current database!"
    log "Restoring from: ${restore_file}"
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Aborted."
        exit 0
    fi

    gunzip -c "${restore_file}" | restore_cmd

    log "Restore complete."
}

case "${1:-backup}" in
    --restore)
        if [[ -z "${2:-}" ]]; then
            error "Usage: $0 --restore <filename>"
        fi
        do_restore "$2"
        ;;
    backup|*)
        do_backup
        ;;
esac
