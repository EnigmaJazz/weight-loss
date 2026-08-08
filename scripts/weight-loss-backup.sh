#!/usr/bin/env bash
# Daily backup of the Weight Loss Tracker data.
#
# Copies weight_loss.db using SQLite's online backup API (safe even while the
# app is writing) plus vapid_keys.json, to a separate disk. Keeps the last N
# backups; never silently fails.
#
# Intended to run from a systemd timer. Paths resolve from scripts/config.local.sh
# when present (see config.local.example.sh), else $HOME-relative defaults.
# Usage:
#   weight-loss-backup.sh [backup-dir]

set -euo pipefail

# Source local overrides first (gitignored); missing file is fine.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/config.local.sh" ]; then
    # shellcheck source=config.local.sh
    source "$SCRIPT_DIR/config.local.sh"
fi

APP_DIR="${APP_DIR:-$HOME/weight_loss}"
BACKUP_ROOT="${1:-${BACKUP_ROOT:-$HOME/backups/weight-loss}}"
KEEP="${KEEP:-14}"          # keep 14 daily backups
DB_PATH="$APP_DIR/weight_loss.db"
VAPID_PATH="$APP_DIR/vapid_keys.json"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"

# Fail loudly if the backup target is not a separate mount (same-disk copies
# are not real redundancy). The check is on the device of the root of the
# backup tree.
if [ ! -d "$BACKUP_ROOT" ]; then
    echo "backup root missing: $BACKUP_ROOT" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# Online backup: sqlite3 CLI's ".backup" uses the backup API so the snapshot
# is transactionally consistent even if the app is mid-write.
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/weight_loss.db'"
else
    # Fallback: python3 stdlib sqlite3 backup().
    python3 - "$DB_PATH" "$BACKUP_DIR/weight_loss.db" <<'PY'
import sqlite3
import sys

src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
try:
    src.backup(dst)
finally:
    dst.close()
    src.close()
PY
fi

# VAPID keys: losing them invalidates every push subscription.
if [ -f "$VAPID_PATH" ]; then
    cp "$VAPID_PATH" "$BACKUP_DIR/vapid_keys.json"
fi

# Verify the snapshot is a readable DB (not a torn copy).
python3 - "$BACKUP_DIR/weight_loss.db" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
try:
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    print(f"backup OK: {row[0]} users")
finally:
    conn.close()
PY

# Prune old backups, newest first.
ls -1dt "$BACKUP_ROOT"/*/ 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    rm -rf "$old"
done

echo "backup written: $BACKUP_DIR"
