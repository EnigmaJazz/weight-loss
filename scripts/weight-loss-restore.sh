#!/usr/bin/env bash
# Restore the Weight Loss Tracker from the most recent backup.
#
# Usage:
#   weight-loss-restore.sh            # restore latest backup
#   weight-loss-restore.sh <stamp>    # restore a specific backup dir name
#
# Stops the service, copies the snapshot back, restarts. The pre-restore DB
# is saved aside (weight_loss.db.pre-restore) as a safety net.

set -euo pipefail

APP_DIR="${APP_DIR:-/home/james/weight_loss}"
BACKUP_ROOT="${1:+$1}"
BACKUP_ROOT_DEFAULT="/mnt/ai_storage/backups/weight-loss"

STAMP="${1:-}"
if [ -z "$STAMP" ]; then
    BACKUP_DIR="$(ls -1dt "$BACKUP_ROOT_DEFAULT"/*/ | head -1)"
else
    BACKUP_DIR="$BACKUP_ROOT_DEFAULT/$STAMP"
fi
BACKUP_DIR="${BACKUP_DIR%/}"
[ -f "$BACKUP_DIR/weight_loss.db" ] || { echo "no snapshot in $BACKUP_DIR" >&2; exit 1; }

systemctl --user stop weight-loss.service

# Safety net: keep the current (possibly newer) DB aside.
cp "$APP_DIR/weight_loss.db" "$APP_DIR/weight_loss.db.pre-restore"

cp "$BACKUP_DIR/weight_loss.db" "$APP_DIR/weight_loss.db"
if [ -f "$BACKUP_DIR/vapid_keys.json" ]; then
    cp "$BACKUP_DIR/vapid_keys.json" "$APP_DIR/vapid_keys.json"
fi

systemctl --user start weight-loss.service

echo "restored from $BACKUP_DIR (previous DB kept as weight_loss.db.pre-restore)"
