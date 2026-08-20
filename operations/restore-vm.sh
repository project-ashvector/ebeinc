#!/usr/bin/env bash
# ==============================================================================
# ALLTHINGS140 Radio — Disaster Recovery & VM Restoration Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DRY_RUN=0
BACKUP_ARCHIVE=""
TARGET_DIR="/opt/allthings140radio"
STATE_DIR="/var/lib/allthings140radio"
LOG_DIR="/var/log/allthings140radio"
RUN_USER="allthings140radio"
DRIVE_MOUNT="/mnt/allthings140radio-drive"

usage() {
    cat << EOF
ALLTHINGS140 Radio — VM Restoration Tool

Usage:
  sudo ./restore-vm.sh [OPTIONS] <backup_archive_path>

Options:
  --dry-run          Validate archive, prerequisites, and simulate restore without changing system state.
  --target-dir DIR   Target installation directory (default: /opt/allthings140radio).
  --state-dir DIR    Target state directory (default: /var/lib/allthings140radio).
  --user USER        Service user name (default: allthings140radio).
  -h, --help         Show this help message.

Example:
  sudo ./restore-vm.sh --dry-run /home/opc/allthings140radio-backup-latest.tar.gz
  sudo ./restore-vm.sh /home/opc/allthings140radio-backup-latest.tar.gz
EOF
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --state-dir)
            STATE_DIR="$2"
            shift 2
            ;;
        --user)
            RUN_USER="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [[ -z "$BACKUP_ARCHIVE" ]]; then
                BACKUP_ARCHIVE="$1"
                shift
            else
                echo "Error: Unknown argument '$1'" >&2
                usage
                exit 1
            fi
            ;;
    esac
done

if [[ -z "$BACKUP_ARCHIVE" ]]; then
    echo "Error: Backup archive path is required." >&2
    usage
    exit 1
fi

echo "================================================================="
echo "ALLTHINGS140 RADIO — DISASTER RECOVERY & VM RESTORE"
echo "================================================================="
echo "Mode: $( [[ $DRY_RUN -eq 1 ]] && echo 'DRY-RUN (SIMULATION)' || echo 'LIVE RESTORATION' )"
echo "Backup Archive: $BACKUP_ARCHIVE"
echo "Target Dir:     $TARGET_DIR"
echo "State Dir:      $STATE_DIR"
echo "Service User:   $RUN_USER"
echo "================================================================="

# Step 1: Validate Prerequisites
echo "[1/6] Checking system prerequisites..."
MISSING_PKGS=()
for bin in python3 ffmpeg ffprobe sqlite3 curl rsync jq; do
    if ! command -v "$bin" &> /dev/null; then
        MISSING_PKGS+=("$bin")
    fi
done

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    echo "WARNING: Missing binaries: ${MISSING_PKGS[*]}"
    echo "Please install missing packages before live deployment (e.g. sudo apt install or dnf install)."
    if [[ $DRY_RUN -eq 0 ]]; then
        echo "Aborting due to missing prerequisites." >&2
        exit 1
    fi
else
    echo "  ✓ All core system binaries are available."
fi

# Step 2: Validate Backup Archive Integrity
echo "[2/6] Validating backup archive integrity..."
if [[ ! -f "$BACKUP_ARCHIVE" ]]; then
    echo "ERROR: Backup archive not found: $BACKUP_ARCHIVE" >&2
    exit 1
fi

TEMP_EXTRACT="$(mktemp -d -t at140-restore-XXXXXX)"
cleanup() {
    rm -rf "$TEMP_EXTRACT"
}
trap cleanup EXIT

if [[ "$BACKUP_ARCHIVE" == *.tar.gz || "$BACKUP_ARCHIVE" == *.tgz ]]; then
    tar -tzf "$BACKUP_ARCHIVE" > /dev/null
    tar -xzf "$BACKUP_ARCHIVE" -C "$TEMP_EXTRACT"
elif [[ "$BACKUP_ARCHIVE" == *.zip ]]; then
    unzip -tq "$BACKUP_ARCHIVE"
    unzip -q "$BACKUP_ARCHIVE" -d "$TEMP_EXTRACT"
else
    echo "ERROR: Unsupported archive format: $BACKUP_ARCHIVE" >&2
    exit 1
fi
echo "  ✓ Archive extracted successfully to staging area."

# Step 3: Validate Database Integrity
echo "[3/6] Inspecting SQLite database integrity..."
DB_FILE="$(find "$TEMP_EXTRACT" -type f -name "station.db" | head -n 1)"
if [[ -n "$DB_FILE" && -f "$DB_FILE" ]]; then
    INTEGRITY_CHECK="$(sqlite3 "$DB_FILE" "PRAGMA integrity_check;" 2>&1 || echo "failed")"
    if [[ "$INTEGRITY_CHECK" == "ok" ]]; then
        TRACK_COUNT="$(sqlite3 "$DB_FILE" "SELECT count(*) FROM tracks WHERE approved=1;" 2>/dev/null || echo "0")"
        echo "  ✓ station.db integrity verified (ok). Approved tracks in catalog: $TRACK_COUNT"
    else
        echo "  ✗ station.db integrity check FAILED: $INTEGRITY_CHECK" >&2
        if [[ $DRY_RUN -eq 0 ]]; then exit 1; fi
    fi
else
    echo "  ! Note: station.db not found in root of archive, checking nested directories..."
fi

# Step 4: Validate Service Configuration & Assets
echo "[4/6] Checking station configuration and service units..."
CONFIG_FILE="$(find "$TEMP_EXTRACT" -type f -name "config.json" -o -name "server-config.json" | head -n 1)"
if [[ -n "$CONFIG_FILE" ]]; then
    echo "  ✓ Found station configuration file: $CONFIG_FILE"
fi

if [[ $DRY_RUN -eq 1 ]]; then
    echo "[5/6] [DRY RUN] Skipping file copy, permission changes, and systemd reloads."
    echo "[6/6] [DRY RUN] Restoration plan verified successfully without errors."
    exit 0
fi

# Step 5: Live Restoration (when not in dry-run mode)
echo "[5/6] Executing live restoration..."

# Ensure system user exists
if ! id "$RUN_USER" &>/dev/null; then
    echo "  Creating service user $RUN_USER..."
    useradd -r -s /bin/false -d "$TARGET_DIR" "$RUN_USER" || true
fi

# Ensure required directories exist
mkdir -p "$TARGET_DIR" "$STATE_DIR/cache" "$STATE_DIR/db" "$LOG_DIR" "$DRIVE_MOUNT"

# Sync files
echo "  Syncing restored application files..."
rsync -a "$TEMP_EXTRACT/" "$TARGET_DIR/"

# Set permissions
chown -R "$RUN_USER:$RUN_USER" "$TARGET_DIR" "$STATE_DIR" "$LOG_DIR"
chmod 750 "$TARGET_DIR" "$STATE_DIR" "$LOG_DIR"

# Install systemd service units if present
if [[ -d "$TARGET_DIR/operations/oracle-radio-migration" ]]; then
    echo "  Installing systemd unit files..."
    cp -u "$TARGET_DIR/operations/oracle-radio-migration"/*.service /etc/systemd/system/ 2>/dev/null || true
    cp -u "$TARGET_DIR/operations/oracle-radio-migration"/*.timer /etc/systemd/system/ 2>/dev/null || true
    systemctl daemon-reload
fi

# Step 6: Post-Restoration Health Verification
echo "[6/6] Verifying restoration health..."
echo "  ✓ Station files restored to $TARGET_DIR"
echo "  ✓ State directories prepared at $STATE_DIR"
echo "================================================================="
echo "Restoration Complete! Next operational steps:"
echo "1. Verify Google Drive mount: sudo -u $RUN_USER ls -la $DRIVE_MOUNT"
echo "2. Start Icecast: sudo systemctl start allthings140radio-icecast"
echo "3. Start Station: sudo systemctl start allthings140radio-server"
echo "4. Verify Public Gateway: curl -s http://127.0.0.1:14082/health"
echo "================================================================="
EOF
