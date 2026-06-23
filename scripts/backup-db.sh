#!/bin/bash
# scripts/backup-db.sh — runs via crontab daily at 03:00 WIB

# Get directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PARENT_DIR/.env" ]; then
    export $(grep -v '^#' "$PARENT_DIR/.env" | xargs)
else
    echo "Error: .env file not found at $PARENT_DIR/.env"
    exit 1
fi

# Define backup directory on mounted OMV
BACKUP_DIR="${OMV_MOUNT_PATH}/backups/mysql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "Starting database backup..."
docker exec -i ytagent-mysql mysqldump \
  -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" ytagent \
  | gzip > "$BACKUP_DIR/ytagent_$TIMESTAMP.sql.gz"

if [ ${PIPESTATUS[0]} -eq 0 ] && [ ${PIPESTATUS[1]} -eq 0 ]; then
    echo "Backup complete: ytagent_$TIMESTAMP.sql.gz"
    # Keep only last 14 days
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +14 -delete
    echo "Old backups cleaned up."
else
    echo "Error: Database backup failed!"
    exit 1
fi
