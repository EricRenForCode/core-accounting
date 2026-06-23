#!/bin/bash
# Core Accounting Database Backup Script
# Usage: ./backups/backup.sh [--restore <filename>]

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-$(dirname "$0")}"
DB_CONTAINER="${DB_CONTAINER:-core-accounting-db-1}"
DB_USER="${DB_USER:-accounting}"
DB_NAME="${DB_NAME:-core_accounting}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/core_accounting_${TIMESTAMP}.sql.gz"

# ── Colors ──────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
error(){ echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Backup ──────────────────────────────────────────────────

do_backup() {
    log "Starting database backup..."
    mkdir -p "${BACKUP_DIR}"

    docker exec "${DB_CONTAINER}" pg_dump \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists \
        | gzip > "${BACKUP_FILE}"

    log "Backup saved: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

    # Keep last 30 days of backups
    find "${BACKUP_DIR}" -name "core_accounting_*.sql.gz" -mtime +30 -delete
    log "Cleaned up backups older than 30 days"
}

# ── Restore ─────────────────────────────────────────────────

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

    gunzip -c "${restore_file}" \
        | docker exec -i "${DB_CONTAINER}" psql \
            -U "${DB_USER}" \
            -d "${DB_NAME}"

    log "Restore complete."
}

# ── Main ────────────────────────────────────────────────────

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
