#!/bin/bash
# scripts/restore-db.sh — manually restore database from a backup file

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

if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found at $BACKUP_FILE"
    exit 1
fi

echo "Restoring database from $BACKUP_FILE..."
gunzip -c "$BACKUP_FILE" | docker exec -i ytagent-mysql mysql \
  -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" ytagent

if [ ${PIPESTATUS[0]} -eq 0 ] && [ ${PIPESTATUS[1]} -eq 0 ]; then
    echo "Database restore completed successfully."
else
    echo "Error: Database restore failed!"
    exit 1
fi
