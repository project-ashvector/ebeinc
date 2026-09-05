#!/usr/bin/env python3
"""AllThings140Radio server.

A dependency-light LAN radio control server for Zorin/Ubuntu systems. It owns
accounts, the approved music library, AutoDJ process, review queue, settings,
and the public listener page.
"""
from __future__ import annotations

import base64
import array
import audioop
import hashlib
import hmac
import html
import ipaddress
import json
import mimetypes
import os
import random
import re
import secrets
import shutil
import signal
import socket
import struct
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from radio_extensions import AlertBus, ArchiveManager, FailureNotifier
from ai_host import AIConfig, AIHost, Takeover, AnnouncementScheduler, takeover_context
from support_system import SupportError, SupportService
from subscription_system import SubscriptionService
from catalog_integrity import scan_catalog

APP_NAME = "AllThings140Radio"
VERSION = "0.8.0"
STATION_GENERATION_ID = uuid.uuid4().hex
CONFIG_DIR = Path(os.environ.get("ALLTHINGS140_CONFIG_DIR", "/etc/allthings140radio"))
DATA_DIR = Path(os.environ.get("ALLTHINGS140_DATA_DIR", "/var/lib/allthings140radio"))
MUSIC_DIR = Path(os.environ.get("ALLTHINGS140_MUSIC_DIR", DATA_DIR / "music"))
FALLBACK_MUSIC_DIR_VALUE = os.environ.get("ALLTHINGS140_FALLBACK_MUSIC_DIR", "").strip()
FALLBACK_MUSIC_DIR = Path(FALLBACK_MUSIC_DIR_VALUE) if FALLBACK_MUSIC_DIR_VALUE else None
CACHE_DIR = Path(os.environ.get("ALLTHINGS140_CACHE_DIR", "/srv/allthings140radio/cache"))
CACHE_INDEX_PATH = CACHE_DIR / "cache-index.json"
INTEGRITY_STATE_PATH = DATA_DIR / "catalog-integrity.json"
INTEGRITY_SUMMARY_PATH = DATA_DIR / "catalog-integrity-summary.json"
CACHE_ONLY = os.environ.get("ALLTHINGS140_CACHE_ONLY", "false").lower() in {"1", "true", "yes", "on"}
TRASH_DIR = Path(os.environ.get("ALLTHINGS140_TRASH_DIR", DATA_DIR / "trash"))
QUARANTINE_DIR = Path(os.environ.get("ALLTHINGS140_QUARANTINE_DIR", DATA_DIR / "music-quarantine"))
TAKEOVER_LOGO_DIR = Path(os.environ.get("ALLTHINGS140_TAKEOVER_LOGO_DIR", DATA_DIR / "takeover-logos"))
AD_DIR = Path(os.environ.get("ALLTHINGS140_AD_DIR", "/opt/allthings140radio-server/ads"))
AD_META_PATH = Path(os.environ.get("ALLTHINGS140_AD_META_PATH", DATA_DIR / "ads.json"))
EVENT_LOG_PATH = Path(os.environ.get("ALLTHINGS140_EVENT_LOG_PATH", DATA_DIR / "events.jsonl"))
ROTATION_STATE_PATH = Path(os.environ.get("ALLTHINGS140_ROTATION_STATE_PATH", DATA_DIR / "rotation-state.json"))
DB_PATH = Path(os.environ.get("ALLTHINGS140_DB_PATH", DATA_DIR / "station.db"))
CONFIG_PATH = Path(os.environ.get("ALLTHINGS140_CONFIG_PATH", CONFIG_DIR / "config.json"))
HOST = os.environ.get("ALLTHINGS140_HOST", "0.0.0.0")
PORT = int(os.environ.get("ALLTHINGS140_PORT", "14080"))
ICECAST_PORT = int(os.environ.get("ALLTHINGS140_ICECAST_PORT", "14000"))
DISCOVERY_PORT = int(os.environ.get("ALLTHINGS140_DISCOVERY_PORT", "14081"))
PUBLIC_GATEWAY_PORT = int(os.environ.get("ALLTHINGS140_PUBLIC_GATEWAY_PORT", "14082"))
TRAKTOR_INGEST_PORT = int(os.environ.get("ALLTHINGS140_TRAKTOR_PORT", "14083"))
MIC_OVERLAY_HOST = "127.0.0.1"
MIC_OVERLAY_PORT = int(os.environ.get("ALLTHINGS140_MIC_OVERLAY_PORT", "14085"))
DEFAULT_PASSWORD = "allthings140"
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
MAX_UPLOAD = 2 * 1024 * 1024 * 1024
EVENT_LOG_MAX_BYTES = 10 * 1024 * 1024
EVENT_LOG_LOCK = threading.RLock()
CACHE_INDEX_LOCK = threading.RLock()
_CACHE_INDEX: dict[str, str] = {}
_CACHE_INDEX_MTIME = 0.0


class SlidingWindowLimiter:
    """Small bounded in-process limiter for unauthenticated public writes."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self.lock:
            bucket = self.events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            if len(self.events) > 10_000:
                for candidate in list(self.events)[:1_000]:
                    if not self.events[candidate] or self.events[candidate][-1] <= cutoff:
                        self.events.pop(candidate, None)
            return True, 0


PUBLIC_WRITE_LIMITER = SlidingWindowLimiter()


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    TAKEOVER_LOGO_DIR.mkdir(parents=True, exist_ok=True)
    AD_DIR.mkdir(parents=True, exist_ok=True)


def event_log(event: str, **fields: Any) -> None:
    """Append one bounded JSONL operational event without affecting playback."""
    payload = {"ts": int(time.time()), "event": str(event)}
    payload.update(fields)
    try:
        with EVENT_LOG_LOCK:
            if EVENT_LOG_PATH.exists() and EVENT_LOG_PATH.stat().st_size >= EVENT_LOG_MAX_BYTES:
                rotated = EVENT_LOG_PATH.with_suffix(".jsonl.1")
                try:
                    rotated.unlink(missing_ok=True)
                except OSError:
                    pass
                EVENT_LOG_PATH.replace(rotated)
            with EVENT_LOG_PATH.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except OSError:
        # Logging must never take the station off air.
        pass


def disk_status() -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(DATA_DIR)
        free_percent = round(usage.free / usage.total * 100, 1) if usage.total else 0.0
        return {"path": str(DATA_DIR), "free_bytes": usage.free, "total_bytes": usage.total, "free_percent": free_percent, "state": "critical" if free_percent < 5 else ("warning" if free_percent < 10 else "healthy")}
    except OSError as exc:
        return {"path": str(DATA_DIR), "state": "error", "error": str(exc)}


def cache_status() -> dict[str, Any]:
    """Read the cache manager's bounded summary without touching audio files."""
    path = CACHE_DIR / "cache-state.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        summary = value.get("_summary", {}) if isinstance(value, dict) else {}
        if isinstance(summary, dict):
            return summary
    except (OSError, ValueError, TypeError):
        pass
    return {"status": "unknown", "tracks_ready": 0, "minutes_ready": 0.0, "cache_bytes": 0, "max_bytes": 0}


def load_ad_meta() -> dict[str, Any]:
    default = {
        "interval_seconds": 900,
        "server_stream_alert_injection_enabled": False,
        "client_account_alerts_enabled": True,
        "ads": {},
    }
    try:
        if AD_META_PATH.exists():
            loaded = json.loads(AD_META_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                default.update(loaded)
                if not isinstance(default.get("ads"), dict):
                    default["ads"] = {}
    except (OSError, ValueError, TypeError):
        event_log("ad_metadata_read_failed")
    return default


def shared_stream_asset_allowed(path: Path, meta: dict[str, Any] | None = None) -> bool:
    """Fail closed for account-sensitive audio entering the common stream.

    The global switch is retained only as an emergency legacy override.  With
    it disabled, an asset must be explicitly classified as common station
    programming; uploaded/unclassified ads and client-delivery alerts stay out
    of Icecast.
    """
    meta = meta or load_ad_meta()
    if bool(meta.get("server_stream_alert_injection_enabled", False)):
        return True
    ads = meta.get("ads", {}) if isinstance(meta.get("ads"), dict) else {}
    info = ads.get(path.name, {}) if isinstance(ads.get(path.name), dict) else {}
    category = str(info.get("category", "")).strip().casefold()
    common_categories = {"station_id", "station_branding", "jingle", "dj_drop", "takeover"}
    return (
        bool(info.get("common_stream_programming", False))
        and not bool(info.get("client_delivery_enabled", False))
        and category in common_categories
    )


def save_ad_meta(meta: dict[str, Any]) -> None:
    temp = AD_META_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(AD_META_PATH)


def measure_loudness(path: Path) -> dict[str, float | None]:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=180, check=False,
    )
    values: dict[str, float | None] = {"mean_volume_db": None, "peak_db": None}
    for line in result.stderr.splitlines():
        if "mean_volume:" in line:
            try:
                values["mean_volume_db"] = float(line.split("mean_volume:", 1)[1].split("dB", 1)[0].strip())
            except ValueError:
                pass
        elif "max_volume:" in line:
            try:
                values["peak_db"] = float(line.split("max_volume:", 1)[1].split("dB", 1)[0].strip())
            except ValueError:
                pass
    return values


def probe_audio_file(path: Path | str, timeout: float = 30.0) -> dict[str, Any]:
    """Probe audio file with ffprobe and return metadata or raise ValueError on failure."""
    path_str = str(path)
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,sample_rate,channels,sample_fmt,bit_rate:format=duration,format_name,size",
        "-of", "json",
        path_str,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Audio probe timed out after {timeout}s") from exc
    except Exception as exc:
        raise ValueError(f"Audio probe failed to execute ffprobe: {exc}") from exc

    if res.returncode != 0:
        err = (res.stderr or "").strip() or f"ffprobe exit code {res.returncode}"
        raise ValueError(f"Invalid audio format or corrupt file: {err}")

    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Could not parse ffprobe output") from exc

    streams = data.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_name")), None)
    fmt = data.get("format", {})
    duration_str = fmt.get("duration") or (audio_stream.get("duration") if audio_stream else None)
    try:
        duration = float(duration_str or 0.0)
    except (ValueError, TypeError):
        duration = 0.0

    if duration <= 0.0 or not audio_stream:
        raise ValueError("File contains no valid playable audio stream or zero duration")

    return {
        "duration": duration,
        "codec": audio_stream.get("codec_name", "unknown"),
        "sample_rate": int(audio_stream.get("sample_rate") or 44100),
        "channels": int(audio_stream.get("channels") or 2),
        "sample_fmt": audio_stream.get("sample_fmt", ""),
        "format_name": fmt.get("format_name", ""),
        "size_bytes": int(fmt.get("size") or (Path(path).stat().st_size if Path(path).exists() else 0)),
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_music_path(filename: str) -> Path:
    """Resolve a fully local cache file before consulting master storage."""
    global _CACHE_INDEX_MTIME, _CACHE_INDEX
    try:
        mtime = CACHE_INDEX_PATH.stat().st_mtime
        with CACHE_INDEX_LOCK:
            if mtime != _CACHE_INDEX_MTIME:
                loaded = json.loads(CACHE_INDEX_PATH.read_text(encoding="utf-8"))
                _CACHE_INDEX = loaded if isinstance(loaded, dict) else {}
                _CACHE_INDEX_MTIME = mtime
            cached = _CACHE_INDEX.get(filename)
        if cached and Path(cached).is_file():
            return Path(cached)
    except (OSError, ValueError, TypeError):
        pass
    if CACHE_ONLY:
        if FALLBACK_MUSIC_DIR is not None:
            fallback = FALLBACK_MUSIC_DIR / filename
            if fallback.exists():
                return fallback
        return CACHE_DIR / "MISSING" / filename
    primary = MUSIC_DIR / filename
    try:
        if primary.exists():
            return primary
    except OSError as exc:
        event_log("primary_music_storage_unavailable", filename=filename, error=str(exc))
    if FALLBACK_MUSIC_DIR is not None:
        fallback = FALLBACK_MUSIC_DIR / filename
        try:
            if fallback.exists():
                return fallback
        except OSError:
            pass
    return primary


def resolve_stored_music_path(filename: str) -> Path:
    """Resolve master/emergency storage independently of playback cache policy."""
    primary = MUSIC_DIR / filename
    try:
        if primary.is_file():
            return primary
    except OSError:
        pass
    if FALLBACK_MUSIC_DIR is not None:
        fallback = FALLBACK_MUSIC_DIR / filename
        try:
            if fallback.is_file():
                return fallback
        except OSError:
            pass
    return primary


def primary_music_storage_available() -> bool:
    try:
        return os.path.ismount(MUSIC_DIR) and MUSIC_DIR.is_dir()
    except OSError:
        return False


def normalized_track_text(value: Any) -> str:
    return "".join(character.lower() for character in str(value or "") if character.isalnum())


def rights_filter_allows(track: dict[str, Any] | sqlite3.Row) -> bool:
    return bool(track["rights_confirmed"] or CONFIG.get("allow_unlicensed_test_mode", False))


def catalog_counts() -> tuple[int, int, int]:
    """Return total, playback-ready approved, and truly missing approved rows."""
    with DB_LOCK, db_connect() as db:
        rows = db.execute(
            "SELECT filename,rights_confirmed FROM tracks WHERE approved=1 AND enabled=1"
        ).fetchall()
        total = int(db.execute("SELECT COUNT(*) FROM tracks").fetchone()[0])
    eligible = [row for row in rows if rights_filter_allows(row)]
    playable = sum(1 for row in eligible if resolve_music_path(row["filename"]).exists())
    missing = 0
    try:
        cached = json.loads(INTEGRITY_STATE_PATH.read_text(encoding="utf-8"))
        missing = int(cached.get("counts", {}).get("missing_approved_audio", 0))
    except (OSError, ValueError, TypeError):
        pass
    return total, playable, missing


def catalog_integrity_snapshot(compute_hashes: bool = False) -> dict[str, Any]:
    report = scan_catalog(
        DB_PATH, MUSIC_DIR, FALLBACK_MUSIC_DIR, resolve_music_path,
        EVENT_LOG_PATH, compute_hashes=compute_hashes,
    )
    try:
        temporary = INTEGRITY_STATE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(temporary, INTEGRITY_STATE_PATH)
        summary = {
            "schema": report.get("schema", 1),
            "generated_at": report.get("generated_at", int(time.time())),
            "health": report.get("health", "unknown"),
            "counts": report.get("counts", {}),
        }
        summary_temporary = INTEGRITY_SUMMARY_PATH.with_suffix(".tmp")
        summary_temporary.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        os.replace(summary_temporary, INTEGRITY_SUMMARY_PATH)
    except OSError:
        pass
    return report


def cached_catalog_integrity() -> dict[str, Any]:
    try:
        value = json.loads(INTEGRITY_STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


_INTEGRITY_SUMMARY_LOCK = threading.Lock()
_INTEGRITY_SUMMARY_CACHE: dict[str, Any] = {"mtime_ns": -1, "value": {}}


def cached_catalog_integrity_summary() -> dict[str, Any]:
    """Cache only the small public integrity summary between report updates."""
    try:
        mtime_ns = INTEGRITY_SUMMARY_PATH.stat().st_mtime_ns
    except OSError:
        return {}
    with _INTEGRITY_SUMMARY_LOCK:
        if _INTEGRITY_SUMMARY_CACHE["mtime_ns"] == mtime_ns:
            return dict(_INTEGRITY_SUMMARY_CACHE["value"])
        try:
            report = json.loads(INTEGRITY_SUMMARY_PATH.read_text(encoding="utf-8"))
            value = {
                "health": report.get("health", "unknown"),
                "counts": dict(report.get("counts", {})),
            }
        except (OSError, ValueError, TypeError):
            return dict(_INTEGRITY_SUMMARY_CACHE["value"])
        _INTEGRITY_SUMMARY_CACHE.update({"mtime_ns": mtime_ns, "value": value})
        return dict(value)


def rotation_audit_snapshot() -> dict[str, Any]:
    """Return read-only rotation diversity metrics for the DJ operations view."""
    total, approved, missing = catalog_counts()
    cutoff = int(time.time()) - 86400
    starts: list[dict[str, Any]] = []
    try:
        lines = EVENT_LOG_PATH.read_text(encoding="utf-8").splitlines()[-5000:]
        for line in lines:
            row = json.loads(line)
            if row.get("event") == "track_started" and int(row.get("ts", 0)) >= cutoff:
                starts.append(row)
    except (OSError, ValueError, TypeError):
        starts = []
    artists: dict[str, int] = {}
    for row in starts:
        artist = str(row.get("artist") or "Unknown artist").strip() or "Unknown artist"
        artists[artist] = artists.get(artist, 0) + 1
    repeated = sorted(({"artist": artist, "plays": count} for artist, count in artists.items() if count > 1), key=lambda item: (-item["plays"], item["artist"]))[:10]
    return {"catalog_tracks": total, "approved_tracks": approved, "missing_approved_tracks": missing,
            "plays_last_24h": len(starts), "unique_tracks_last_24h": len({row.get("track_id") for row in starts}),
            "repeated_artists_last_24h": repeated, "window_seconds": 86400, "generated_at": int(time.time())}


def load_config() -> dict[str, Any]:
    ensure_dirs()
    default = {
        "station_name": "AllThings140Radio",
        "station_description": "140 BPM and bass music, live around the clock.",
        "icecast_host": "127.0.0.1",
        "icecast_port": ICECAST_PORT,
        "icecast_encoder_port": int(os.environ.get("ALLTHINGS140_ICECAST_ENCODER_PORT", "14001")),
        "icecast_mount": "/live.mp3",
        "autodj_mount": "/live.mp3",
        "source_password": "local-relay",
        "public_host": "",
        "public_stream_url": "https://stream.ebeinc.online/live.mp3",
        "website_url": "https://allthings140radio.online/",
        "soundcloud_client_id": "",
        "soundcloud_client_secret": "",
        "soundcloud_access_token": "",
        "soundcloud_refresh_token": "",
        "soundcloud_token_expires": 0,
        "soundcloud_test_enabled": True,
        "allow_unlicensed_test_mode": False,
        "ad_interval_seconds": 900,
        "archive_storage_provider": "local",
        "archive_retention_mode": "keep_all",
        "archive_retention_days": 0,
        "silence_warning_seconds": 20,
        "watchdog_recovery_cooldown_seconds": 30,
        "artist_cooldown_tracks": 6,
        "disk_warning_free_percent": 10,
        "disk_critical_free_percent": 5,
        "failure_alert_cooldown_seconds": 900,
        "soundcloud_test_url": "https://soundcloud.com/ebmarah",
        "soundcloud_test_title": "Ebmarah — All Tracks",
    }
    if CONFIG_PATH.exists():
        try:
            current = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            default.update(current)
            if default.get("website_url") == "https://ebeinc.online/radio/":
                default["website_url"] = "https://allthings140radio.online/"
            public_stream = str(default.get("public_stream_url", "")).strip()
            if not public_stream or "tail9b0b89.ts.net" in public_stream:
                default["public_stream_url"] = "https://stream.ebeinc.online/live.mp3"
        except Exception:
            pass
    CONFIG_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except PermissionError:
        pass
    return default


CONFIG = load_config()
AI_CONFIG_PATH = Path(os.environ.get("ALLTHINGS140_AI_CONFIG_PATH", DATA_DIR / "ai-dj.json"))
AI_VOICE_ROOT = Path(os.environ.get("ALLTHINGS140_AI_VOICE_ROOT", DATA_DIR / "voices"))
AI_PERSONA_ROOT = Path(os.environ.get("ALLTHINGS140_AI_PERSONA_ROOT", DATA_DIR / "personas"))
AI_OUTPUT_ROOT = Path(os.environ.get("ALLTHINGS140_AI_OUTPUT_ROOT", DATA_DIR / "ai-cache"))
AI_TRIGGER_PATH = Path(os.environ.get("ALLTHINGS140_AI_TRIGGER_PATH", DATA_DIR / "ai-trigger-next"))
AI_NOW_TRIGGER_PATH = Path(os.environ.get("ALLTHINGS140_AI_NOW_TRIGGER_PATH", DATA_DIR / "ai-trigger-now"))

def load_ai_host() -> AIHost:
    try:
        data = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8")) if AI_CONFIG_PATH.exists() else {}
    except (OSError, ValueError):
        data = {}
    allowed = {key: value for key, value in data.items() if key in AIConfig.__dataclass_fields__}
    if "humorLevel" in allowed: allowed["humorLevel"] = str(allowed["humorLevel"]).upper()
    return AIHost(AIConfig(**allowed), AI_VOICE_ROOT, AI_PERSONA_ROOT, AI_OUTPUT_ROOT)

AI_HOST = load_ai_host()
DB_LOCK = threading.RLock()
AUTODJ_RESTART = threading.Event()
SHUTDOWN = threading.Event()


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt64, digest64 = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt64)
        expected = base64.b64decode(digest64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False


def init_db() -> None:
    ensure_dirs()
    with DB_LOCK, db_connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'dj',
                must_change_password INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL UNIQUE,
                source_url TEXT NOT NULL DEFAULT '',
                rights_confirmed INTEGER NOT NULL DEFAULT 0,
                approved INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                added_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS upload_receipts (
                upload_id TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                response_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (upload_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL,
                genre TEXT NOT NULL DEFAULT '',
                bpm REAL,
                artwork_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT NOT NULL DEFAULT '',
                added_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                action TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalog_operations (
                operation_id TEXT PRIMARY KEY,
                operation_type TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_by INTEGER REFERENCES users(id),
                request_json TEXT NOT NULL,
                result_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalog_operation_items (
                operation_id TEXT NOT NULL REFERENCES catalog_operations(operation_id) ON DELETE CASCADE,
                track_id INTEGER NOT NULL,
                result TEXT NOT NULL,
                detail_json TEXT NOT NULL DEFAULT '{}',
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (operation_id, track_id)
            );
            CREATE TABLE IF NOT EXISTS quarantine_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT NOT NULL,
                track_id INTEGER,
                original_path TEXT NOT NULL,
                quarantine_path TEXT NOT NULL UNIQUE,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'QUARANTINED',
                created_at INTEGER NOT NULL,
                restored_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS track_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL DEFAULT '',
                client_hash TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS takeovers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                starts_at INTEGER NOT NULL,
                ends_at INTEGER NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                socials_json TEXT NOT NULL DEFAULT '[]',
                created_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS takeover_invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                created_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                submitted_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS reminder_subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                consent INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                unsubscribe_token TEXT NOT NULL UNIQUE,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS guest_invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT NOT NULL UNIQUE,
                guest_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'invited',
                created_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                connected_at INTEGER NOT NULL DEFAULT 0,
                ended_at INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(guest_invites)").fetchall()}
        if "invite_type" not in columns:
            db.execute("ALTER TABLE guest_invites ADD COLUMN invite_type TEXT NOT NULL DEFAULT 'browser'")
        if "credential_hash" not in columns:
            db.execute("ALTER TABLE guest_invites ADD COLUMN credential_hash TEXT NOT NULL DEFAULT ''")
        if "source_mount" not in columns:
            db.execute("ALTER TABLE guest_invites ADD COLUMN source_mount TEXT NOT NULL DEFAULT ''")
        takeover_columns = {row[1] for row in db.execute("PRAGMA table_info(takeovers)").fetchall()}
        if "timezone" not in takeover_columns:
            db.execute("ALTER TABLE takeovers ADD COLUMN timezone TEXT NOT NULL DEFAULT 'America/Los_Angeles'")
        if "logo_name" not in takeover_columns:
            db.execute("ALTER TABLE takeovers ADD COLUMN logo_name TEXT NOT NULL DEFAULT ''")
        if "status" not in takeover_columns:
            db.execute("ALTER TABLE takeovers ADD COLUMN status TEXT NOT NULL DEFAULT 'published'")
        invite_columns = {row[1] for row in db.execute("PRAGMA table_info(takeover_invites)").fetchall()}
        if "email" not in invite_columns:
            db.execute("ALTER TABLE takeover_invites ADD COLUMN email TEXT NOT NULL DEFAULT ''")
        for username, role in (("ebmarah", "admin"), ("eyewitnis", "manager")):
            db.execute(
                "INSERT OR IGNORE INTO users(username,password_hash,role,must_change_password,created_at) VALUES(?,?,?,?,?)",
                (username, password_hash(DEFAULT_PASSWORD), role, 1, int(time.time())),
            )
        db.commit()


def audit(user_id: int | None, action: str, detail: str = "") -> None:
    with DB_LOCK, db_connect() as db:
        db.execute(
            "INSERT INTO audit_log(user_id,action,detail,created_at) VALUES(?,?,?,?)",
            (user_id, action, detail[:1000], int(time.time())),
        )
        db.commit()


def public_client_hash(handler: BaseHTTPRequestHandler) -> str:
    candidate = str(handler.headers.get("CF-Connecting-IP") or handler.headers.get("X-Client-IP") or handler.client_address[0]).split(",", 1)[0].strip()
    try:
        candidate = str(ipaddress.ip_address(candidate))
    except ValueError:
        candidate = handler.client_address[0]
    return hashlib.sha256(candidate.encode("utf-8", "replace")).hexdigest()


def public_write(handler: BaseHTTPRequestHandler, path: str, data: dict[str, Any]) -> tuple[dict[str, Any], int, int]:
    """Validate, throttle, and persist public listener writes."""
    client_hash = public_client_hash(handler)
    honeypot = str(data.get("website", "")).strip()
    if honeypot:
        event_log("public_write_honeypot", endpoint=path, client=client_hash[:12])
        return {"ok": True}, 202, 0
    started_at = int(data.get("started_at") or 0)
    if started_at and int(time.time() * 1000) - started_at < 1500:
        return {"error": "Please wait a moment and try again."}, 429, 2
    if path == "/api/public/submissions":
        allowed, retry = PUBLIC_WRITE_LIMITER.allow(f"submission:{client_hash}", 4, 3600)
        if not allowed:
            return {"error": "Submission limit reached. Please try again later."}, 429, retry
        submission_type = str(data.get("submission_type", "track")).strip().lower()
        if submission_type not in {"track", "recorded_mix"}:
            return {"error": "Choose either a released track or a prerecorded DJ mix."}, 400, 0
        title = str(data.get("title", "")).strip()[:180]
        artist = str(data.get("artist", "")).strip()[:180]
        track_url = str(data.get("track_url", "")).strip()[:1000]
        email = str(data.get("email", "")).strip().lower()[:240]
        if not title or not artist or not re.fullmatch(r"https?://[^\s]+", track_url) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return {"error": "Artist or DJ, title, a valid HTTPS audio link, and email are required."}, 400, 0
        try:
            duration_minutes = int(data.get("duration_minutes") or 0)
        except (TypeError, ValueError):
            duration_minutes = 0
        rights_confirmed = bool(data.get("rights_confirmed", False))
        if submission_type == "recorded_mix" and (duration_minutes < 1 or duration_minutes > 720 or not rights_confirmed):
            return {"error": "Recorded mixes require a length and confirmation that every recording may be broadcast."}, 400, 0
        fingerprint = hashlib.sha256(f"{email}\0{track_url.lower()}".encode()).hexdigest()
        allowed, retry = PUBLIC_WRITE_LIMITER.allow(f"submission-item:{fingerprint}", 2, 86400)
        if not allowed:
            return {"error": "That audio was already submitted. Please wait before sending it again."}, 429, retry
        details = json.dumps({
            "submission_type": submission_type,
            "email": email,
            "order_id": str(data.get("order_id", "")).strip()[:120],
            "duration_minutes": duration_minutes or None,
            "genres": str(data.get("genres", "")).strip()[:240],
            "tracklist": str(data.get("tracklist", "")).strip()[:5000],
            "preferred_air_date": str(data.get("preferred_air_date", "")).strip()[:10],
            "rights_confirmed": rights_confirmed,
            "notes": str(data.get("notes", "")).strip()[:1000],
            "client": client_hash[:12],
        }, ensure_ascii=False)
        with DB_LOCK, db_connect() as db:
            cursor = db.execute(
                """INSERT INTO review_queue(title,artist,source_url,genre,bpm,artwork_url,status,notes,added_by,created_at)
                   VALUES(?,?,?,?,NULL,'','pending',?,NULL,?)""",
                (title, artist, track_url, "public recorded mix" if submission_type == "recorded_mix" else "public submission", details, int(time.time())),
            )
            db.commit()
        event_log("public_submission_received", review_id=int(cursor.lastrowid), submission_type=submission_type, client=client_hash[:12])
        return {"ok": True, "message": "Submission received for review."}, 201, 0
    if path == "/api/public/requests":
        allowed, retry = PUBLIC_WRITE_LIMITER.allow(f"request:{client_hash}", 12, 600)
        if not allowed:
            return {"error": "Request limit reached. Please try again shortly."}, 429, retry
        title = str(data.get("title", "")).strip()[:100]
        artist = str(data.get("artist", "")).strip()[:80]
        if not title:
            return {"error": "Track title is required."}, 400, 0
        with DB_LOCK, db_connect() as db:
            cursor = db.execute(
                "INSERT INTO track_requests(title,artist,client_hash,status,created_at) VALUES(?,?,?,'pending',?)",
                (title, artist, client_hash, int(time.time())),
            )
            db.commit()
        event_log("public_track_request_received", request_id=int(cursor.lastrowid), client=client_hash[:12])
        return {"ok": True, "message": "Request sent to the hosts."}, 201, 0
    if path == "/api/public/newsletter":
        allowed, retry = PUBLIC_WRITE_LIMITER.allow(f"newsletter:{client_hash}", 5, 3600)
        if not allowed:
            return {"error": "Signup limit reached. Please try again later."}, 429, retry
        email = str(data.get("email", "")).strip().lower()[:240]
        if not bool(data.get("consent")) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return {"error": "A valid email and reminder consent are required."}, 400, 0
        with DB_LOCK, db_connect() as db:
            db.execute("INSERT INTO reminder_subscribers(email,consent,status,unsubscribe_token,created_at) VALUES(?,1,'active',?,?) ON CONFLICT(email) DO UPDATE SET consent=1,status='active'", (email, secrets.token_urlsafe(24), int(time.time())))
            db.commit()
        event_log("takeover_reminder_signup", client=client_hash[:12])
        return {"ok": True, "message": "You’re signed up for takeover reminders."}, 201, 0
    if path == "/api/public/takeover-interest":
        allowed, retry = PUBLIC_WRITE_LIMITER.allow(f"takeover-interest:{client_hash}", 4, 86400)
        if not allowed:
            return {"error": "Request limit reached. Please try again tomorrow."}, 429, retry
        email = str(data.get("email", "")).strip().lower()[:240]
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return {"error": "Enter a valid email address."}, 400, 0
        fingerprint = hashlib.sha256(email.encode()).hexdigest()
        allowed, retry = PUBLIC_WRITE_LIMITER.allow(f"takeover-interest-email:{fingerprint}", 2, 86400)
        if not allowed:
            return {"error": "A takeover form was already sent to this email."}, 429, retry
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with DB_LOCK, db_connect() as db:
            db.execute("INSERT INTO takeover_invites(token_hash,label,status,created_by,created_at,expires_at,email) VALUES(?,?,'open',NULL,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), "Interested artist", now, now + 14 * 86400, email))
            db.commit()
        event_log("public_takeover_interest", client=client_hash[:12])
        return {"ok": True, "email": email, "link": f"https://allthings140radio.online/takeover/#{token}", "message": "Check your email for your private takeover form."}, 201, 0
    return {"error": "Not found"}, 404, 0


def valid_timezone(value: Any) -> str:
    timezone = str(value or "America/Los_Angeles").strip()[:80]
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Choose a valid timezone")
    return timezone


def store_takeover_logo(data_url: Any) -> str:
    value = str(data_url or "")
    if not value:
        return ""
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\r\n]+)", value)
    if not match:
        raise ValueError("Logo must be a PNG, JPEG, or WebP image")
    try:
        payload = base64.b64decode(match.group(2), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Logo image is invalid") from exc
    if not payload or len(payload) > 2 * 1024 * 1024:
        raise ValueError("Logo must be smaller than 2 MB")
    mime = match.group(1)
    valid = (mime == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n")) or (mime == "image/jpeg" and payload.startswith(b"\xff\xd8\xff")) or (mime == "image/webp" and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP")
    if not valid:
        raise ValueError("Logo contents do not match the selected image type")
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[mime]
    name = secrets.token_hex(16) + extension
    (TAKEOVER_LOGO_DIR / name).write_bytes(payload)
    return name


def takeover_rows(public_only: bool = True) -> list[dict[str, Any]]:
    now = int(time.time())
    where = "WHERE ends_at >= ? AND status='published'" if public_only else ""
    values = (now,) if public_only else ()
    with DB_LOCK, db_connect() as db:
        rows = db.execute(
            f"SELECT id,artist,title,starts_at,ends_at,details,socials_json,timezone,logo_name,status FROM takeovers {where} ORDER BY starts_at ASC LIMIT 100",
            values,
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["socials"] = json.loads(item.pop("socials_json"))
        except (ValueError, TypeError):
            item["socials"] = []
        logo_name = str(item.pop("logo_name", "") or "")
        item["logo_url"] = f"/api/public/takeover-logo/{logo_name}" if logo_name else "/assets/takeover-fallback-logo.webp"
        result.append(item)
    return result


def takeover_invite(token: str) -> sqlite3.Row | None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    with DB_LOCK, db_connect() as db:
        return db.execute("SELECT * FROM takeover_invites WHERE token_hash=?", (digest,)).fetchone()


def active_takeover(now: int | None = None) -> dict[str, Any] | None:
    timestamp = int(now or time.time())
    with DB_LOCK, db_connect() as db:
        row = db.execute(
            "SELECT id,artist,title,starts_at,ends_at,details,socials_json,timezone,logo_name,status FROM takeovers WHERE status='published' AND starts_at<=? AND ends_at>? ORDER BY starts_at DESC LIMIT 1",
            (timestamp, timestamp),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item["socials"] = json.loads(item.pop("socials_json"))
    except (ValueError, TypeError):
        item["socials"] = []
    logo_name = str(item.pop("logo_name", "") or "")
    item["logo_url"] = f"/api/public/takeover-logo/{logo_name}" if logo_name else "/assets/takeover-fallback-logo.webp"
    return item


def serve_takeover_logo(handler: BaseHTTPRequestHandler, name: str) -> None:
    responder = getattr(handler, "_json", None) or getattr(handler, "json_response")
    if not re.fullmatch(r"[a-f0-9]{32}\.(?:png|jpg|webp)", name):
        return responder({"error": "Logo not found"}, 404)
    path = TAKEOVER_LOGO_DIR / name
    if not path.is_file():
        return responder({"error": "Logo not found"}, 404)
    body = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "public, max-age=31536000, immutable")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)


def submit_takeover_invite(token: str, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    invite = takeover_invite(token)
    now = int(time.time())
    if not invite or invite["status"] != "open" or int(invite["expires_at"]) < now:
        return {"error": "This artist form link is invalid, expired, or already used."}, 404
    artist = str(data.get("artist", "")).strip()[:100]
    title = str(data.get("title", "")).strip()[:140]
    details = str(data.get("details", "")).strip()[:500]
    starts_at, ends_at = int(data.get("starts_at") or 0), int(data.get("ends_at") or 0)
    try:
        timezone = valid_timezone(data.get("timezone"))
        logo_name = store_takeover_logo(data.get("logo_data"))
    except ValueError as exc:
        return {"error": str(exc)}, 400
    socials = []
    for entry in data.get("socials", []) if isinstance(data.get("socials"), list) else []:
        platform, url = str(entry.get("platform", "")).strip()[:30], str(entry.get("url", "")).strip()[:500]
        if platform and re.fullmatch(r"https?://[^\s]+", url):
            socials.append({"platform": platform, "url": url})
    if not artist or starts_at <= now or ends_at <= starts_at:
        return {"error": "Artist and valid future start/end times are required."}, 400
    with DB_LOCK, db_connect() as db:
        cursor = db.execute(
            "INSERT INTO takeovers(artist,title,starts_at,ends_at,details,socials_json,timezone,logo_name,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (artist, title, starts_at, ends_at, details, json.dumps(socials), timezone, logo_name, "pending", invite["created_by"], now, now),
        )
        db.execute("UPDATE takeover_invites SET status='submitted',submitted_at=? WHERE id=?", (now, invite["id"]))
        db.commit()
    event_log("artist_takeover_submitted", takeover_id=int(cursor.lastrowid), artist=artist)
    return {"ok": True, "id": int(cursor.lastrowid), "message": "Your takeover request was sent to the station for approval."}, 201


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = int(time.time()) + 30 * 24 * 3600
    with DB_LOCK, db_connect() as db:
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (token_hash, user_id, expires))
        db.commit()
    return token


def session_user(token: str) -> sqlite3.Row | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with DB_LOCK, db_connect() as db:
        return db.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.expires_at>?""",
            (token_hash, int(time.time())),
        ).fetchone()


def safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = "".join(ch if ch.isalnum() or ch in "._- ()[]" else "_" for ch in base).strip(". ")
    return cleaned[:180] or f"track-{int(time.time())}.mp3"


def write_json_config(updates: dict[str, Any]) -> dict[str, Any]:
    global CONFIG
    text_allowed = {
        "station_name", "station_description", "public_host",
        "public_stream_url", "website_url",
        "soundcloud_client_id", "soundcloud_client_secret",
        "soundcloud_test_url", "soundcloud_test_title",
    }
    for key, value in updates.items():
        if key in text_allowed:
            CONFIG[key] = str(value).strip()
        elif key == "soundcloud_test_enabled":
            CONFIG[key] = bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}
        elif key == "allow_unlicensed_test_mode":
            CONFIG[key] = bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}
        elif key == "ad_interval_seconds":
            CONFIG[key] = max(60, min(3600, int(value)))
        elif key in {"silence_warning_seconds", "watchdog_recovery_cooldown_seconds", "failure_alert_cooldown_seconds"}:
            CONFIG[key] = max(10, min(86400, int(value)))
        elif key in {"disk_warning_free_percent", "disk_critical_free_percent"}:
            CONFIG[key] = max(1, min(50, int(value)))
        elif key == "archive_retention_days":
            CONFIG[key] = max(0, min(3650, int(value)))
        elif key == "archive_retention_mode":
            mode = str(value).strip().lower()
            if mode not in {"keep_all", "manual", "after_remote_upload"}:
                raise ValueError("Invalid archive retention mode")
            CONFIG[key] = mode
    fallback_url = str(CONFIG.get("soundcloud_test_url", "")).strip()
    if fallback_url and not fallback_url.startswith(("https://soundcloud.com/", "http://soundcloud.com/", "https://on.soundcloud.com/", "http://on.soundcloud.com/")):
        raise ValueError("SoundCloud test rotation must use a soundcloud.com link")
    CONFIG_PATH.write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except PermissionError:
        pass
    return CONFIG


@dataclass
class AutoDJState:
    running: bool = False
    pid: int | None = None
    mode: str = "starting"
    last_error: str = ""
    tracks: int = 0
    current_track_id: int | None = None
    current_title: str = ""
    current_artist: str = ""
    started_at: int = 0
    position_seconds: float = 0.0
    duration_seconds: float = 0.0
    next_track_id: int | None = None
    next_title: str = ""
    next_artist: str = ""
    transition_reason: str = "startup"
    ad_playing: bool = False
    ad_name: str = ""
    sequence: int = 0


class MicOverlayMixer:
    """Bounded non-blocking loopback overlay. Every error returns music unchanged."""
    MAGIC = b"ATMP"
    ACK = b"ATACK"
    HEADER = struct.Struct("!4s8sIB")
    MAX_AGE = 0.30

    def __init__(self, rate: int, channels: int) -> None:
        self.rate, self.channels = rate, channels
        self.socket: socket.socket | None = None
        self.music_gain = 1.0
        self.last_packet_at = self.last_mix_at = 0.0
        self.last_sequence = -1
        self.session = b""
        self.pcm_buffer = bytearray()
        self.last_address: tuple[str, int] | None = None
        self.source = ""
        self.live = False
        self.packets_mixed = self.invalid_packets = 0
        self.bind_error = ""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            sock.bind((MIC_OVERLAY_HOST, MIC_OVERLAY_PORT)); sock.setblocking(False)
            self.socket = sock
            event_log("mic_overlay_ready", host=MIC_OVERLAY_HOST, port=MIC_OVERLAY_PORT)
        except OSError as exc:
            self.bind_error = str(exc)
            event_log("mic_overlay_disabled", error=self.bind_error)

    def _read_current(self, wanted: int) -> tuple[bytes | None, tuple[str, int] | None, bytes, int]:
        if self.socket is None:
            return None, None, b"", -1
        received = []
        for _ in range(32):
            try: packet, address = self.socket.recvfrom(8192)
            except BlockingIOError: break
            except OSError as exc: self.bind_error = str(exc); break
            now = time.monotonic()
            if len(packet) <= self.HEADER.size:
                self.invalid_packets += 1; continue
            magic, session, sequence, source_id = self.HEADER.unpack_from(packet)
            payload = packet[self.HEADER.size:]
            if magic != self.MAGIC or len(payload) % (self.channels * 2):
                self.invalid_packets += 1; continue
            received.append((now, payload, address, session, sequence, source_id))
        if received:
            session = received[-1][3]
            current = [item for item in received if item[3] == session]
            if session != self.session:
                self.pcm_buffer.clear()
            self.pcm_buffer.extend(b"".join(item[1] for item in current))
            latest = current[-1]
            self.last_packet_at, self.last_sequence, self.session = latest[0], latest[4], latest[3]
            self.last_address = latest[2]
            self.source = "galaxy_watch" if latest[5] == 2 else "phone"
        elif not self.pcm_buffer or time.monotonic()-self.last_packet_at > self.MAX_AGE:
            return None, None, b"", -1
        # Bound latency to at most three mixer blocks. Preserve surplus audio
        # across calls instead of discarding early packets and inserting gaps.
        if len(self.pcm_buffer) > wanted * 3:
            del self.pcm_buffer[:len(self.pcm_buffer) - wanted * 3]
        take = min(wanted, len(self.pcm_buffer))
        pcm = bytes(self.pcm_buffer[:take])
        del self.pcm_buffer[:take]
        if len(pcm) < wanted: pcm += b"\x00" * (wanted-len(pcm))
        return pcm, self.last_address, self.session, self.last_sequence

    def mix(self, music: bytes) -> bytes:
        if not music:
            return music
        try:
            mic, address, session, sequence = self._read_current(len(music))
            active = mic is not None and time.monotonic() - self.last_packet_at <= self.MAX_AGE
            target = 10.0 ** (-12.0 / 20.0) if active else 1.0

            # Instant fast-path when mic is idle and music is at full volume (99.9% of the time)
            if not active and self.music_gain >= 0.999 and target >= 0.999:
                self.music_gain = 1.0
                was_live, self.live = self.live, False
                if was_live:
                    event_log("mic_overlay_off", source=self.source)
                return music

            seconds = max(len(music) / (self.rate * self.channels * 2), .001)
            ramp = .150 if target < self.music_gain else .750
            full_range = 1.0 - 10.0 ** (-12.0 / 20.0)
            step = full_range * seconds / ramp
            end_gain = max(target, self.music_gain - step) if target < self.music_gain else min(target, self.music_gain + step)
            avg_gain = (self.music_gain + end_gain) / 2.0

            # C-accelerated mixing
            scaled_music = audioop.mul(music, 2, avg_gain)
            if mic:
                scaled_mic = audioop.mul(mic, 2, 0.72)
                mixed_bytes = audioop.add(scaled_music, scaled_mic, 2)
            else:
                mixed_bytes = scaled_music

            self.music_gain = end_gain
            was_live, self.live = self.live, active
            if active:
                self.last_mix_at = time.monotonic()
                self.packets_mixed += 1
                if address and self.socket:
                    try:
                        self.socket.sendto(self.ACK + session + struct.pack("!I", sequence), address)
                    except OSError:
                        pass
            if active != was_live:
                event_log("mic_overlay_live" if active else "mic_overlay_off", source=self.source)
            return mixed_bytes
        except Exception as exc:
            self.live = False
            self.music_gain = 1.0
            self.invalid_packets += 1
            event_log("mic_overlay_mix_error", error=str(exc))
            return music

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        return {"enabled": self.socket is not None, "live": self.live and now-self.last_mix_at < self.MAX_AGE,
                "source": self.source if self.live else "", "last_mix_ms": round((now-self.last_mix_at)*1000) if self.last_mix_at else None,
                "packets_mixed": self.packets_mixed, "invalid_packets": self.invalid_packets,
                "music_gain": round(self.music_gain,4), "duck_db": -12.0, "attack_ms": 150, "release_ms": 750,
                "mic_gain": 0.72, "bind": f"{MIC_OVERLAY_HOST}:{MIC_OVERLAY_PORT}", "error": self.bind_error}


class AutoDJManager(threading.Thread):
    """Continuous server-side catalog rotation with DJ transport controls.

    One persistent FFmpeg encoder owns the Icecast AutoDJ connection. Separate
    decoder processes feed PCM into it one track at a time. Skipping or choosing
    a track replaces only the decoder, so the station mount stays connected and
    listeners do not get dropped between catalog songs.
    """

    PCM_RATE = 44_100
    PCM_CHANNELS = 2
    PCM_BYTES_PER_SAMPLE = 2
    PCM_CHUNK_SECONDS = 0.10
    AD_INTERVAL_SECONDS = 7 * 60
    MUSIC_DUCK_GAIN = 0.34
    AD_GAIN = 0.92
    LOUD_ALERT_MUSIC_DUCK_GAIN = 0.04
    LOUD_ALERT_GAIN = 1.04
    LOUD_ALERT_FILENAMES = frozenset({
        "1786419543355-79292e22c94f1240ffec346ee9537f6f.mp3",
        "1786419593707-870977d957210d03bf616cba0576d0c5.mp3",
        "1786419688685-f7a48fc1275e216bbf51a6b9e50e6b68.mp3",
        "1786419753903-47d3f0991ee52d83b2f63925ed74220c.mp3",
        "1786419850217-105046473036617cd40b523baae59575.mp3",
        "1786419906930-7c2e29718382c9c10eaf7eaefc545bf0.mp3",
        "1786420058382-ebdc215b81a02adf5cccc215056034b7.mp3",
        "1786420108730-be0c074b1a6d944e70546295a282a028.mp3",
        "1786420188435-6b3c32798d1170eab2a1e6616aba08e0.mp3",
        "1786420258553-70a6ec77c5983f878a5cf9552568ea95.mp3",
        "1786420351094-961a48d9bca05b13afaba8c398a86c35.mp3",
        "1786420611575-13a4814c4366b74cf2b05364820f9ef1.mp3",
        "audio-2osC1k6mDg4c.mp3",
        "audio-VBpBH97x3wN7.mp3",
    })

    def __init__(self) -> None:
        super().__init__(daemon=True, name="AutoDJ")
        self.encoder: subprocess.Popen[bytes] | None = None
        self.decoder: subprocess.Popen[bytes] | None = None
        self.ad_decoder: subprocess.Popen[bytes] | None = None
        self.state = AutoDJState()
        self.lock = threading.RLock()
        self.control_event = threading.Event()
        self.pending_action: tuple[str, int | None] | None = None
        self.rotation_index = 0
        self.rotation_order: list[int] = []
        self.rotation_seen: set[int] = set()
        self.resume_advance = False
        self.live_pause = threading.Event()
        self.live_handoff_until = 0.0
        self.live_source_seen = False
        self.live_source_last_seen = 0.0
        self.next_ad_at = time.monotonic() + float(load_ad_meta().get("interval_seconds", self.AD_INTERVAL_SECONDS))
        self.ad_pool: list[Path] = []
        self.last_ad: Path | None = None
        self.forced_ad: Path | None = None
        self.current_ad_path: Path | None = None
        self.current_ad_manual = False
        self.current_ad_started_at = 0
        self.mic_overlay = MicOverlayMixer(self.PCM_RATE, self.PCM_CHANNELS)
        self.load_rotation_state()

    def load_rotation_state(self) -> None:
        try:
            data = json.loads(ROTATION_STATE_PATH.read_text(encoding="utf-8"))
            order = data.get("rotation_order", [])
            seen = data.get("rotation_seen", [])
            if not isinstance(order, list) or not all(isinstance(value, int) for value in order):
                raise ValueError("invalid rotation order")
            if len(order) != len(set(order)):
                raise ValueError("duplicate rotation IDs")
            self.rotation_order = order
            self.rotation_seen = {int(value) for value in seen if isinstance(value, int) and value in order}
            self.rotation_index = max(0, int(data.get("rotation_index", 0)))
            # rotation_index is persisted at TRACK_START.  If the process is
            # restarted before TRACK_END, advance once on startup instead of
            # replaying the interrupted song from 0:00.
            self.resume_advance = bool(data.get("updated_at"))
            event_log("rotation_state_restored", tracks=len(order), seen=len(self.rotation_seen))
        except FileNotFoundError:
            return
        except Exception as exc:
            event_log("rotation_state_ignored", error=str(exc))

    def save_rotation_state(self) -> None:
        try:
            payload = {"version": 1, "rotation_order": self.rotation_order, "rotation_seen": sorted(self.rotation_seen), "rotation_index": self.rotation_index, "updated_at": int(time.time())}
            temporary = ROTATION_STATE_PATH.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temporary, ROTATION_STATE_PATH)
        except OSError as exc:
            event_log("rotation_state_save_failed", error=str(exc))

    def load_rotation(self) -> list[dict[str, Any]]:
        with DB_LOCK, db_connect() as db:
            rows = db.execute(
                """SELECT t.id, t.title, t.artist, t.filename, t.source_url, t.rights_confirmed, a.duration
                   FROM tracks t LEFT JOIN audio_assets a ON a.track_id=t.id
                   WHERE t.approved=1 AND t.enabled=1
                   ORDER BY t.id ASC"""
            ).fetchall()
        tracks: list[dict[str, Any]] = []
        for row in rows:
            path = resolve_music_path(row["filename"])
            if path.exists():
                item = dict(row)
                if rights_filter_allows(row):
                    item["path"] = str(path)
                    tracks.append(item)
        ids = {int(item["id"]) for item in tracks}
        with self.lock:
            if ids != set(self.rotation_order):
                self.rotation_order = []
                self.rotation_seen.clear()
            if not self.rotation_order or len(self.rotation_seen) >= len(ids):
                self.rotation_order = self.cooldown_order(tracks, int(CONFIG.get("artist_cooldown_tracks", 6)))
                self.rotation_seen.clear()
                self.save_rotation_state()
            order_index = {track_id: index for index, track_id in enumerate(self.rotation_order)}
        tracks.sort(key=lambda item: order_index.get(int(item["id"]), len(order_index)))
        return tracks

    @staticmethod
    def cooldown_order(tracks: list[dict[str, Any]], cooldown: int = 6) -> list[int]:
        """Greedy randomized order avoiding recent artists when possible."""
        remaining = tracks[:]
        random.shuffle(remaining)
        result: list[int] = []
        recent: list[str] = []
        while remaining:
            choice = next((item for item in remaining if str(item.get("artist", "")).strip().casefold() not in recent), remaining[0])
            remaining.remove(choice); result.append(int(choice["id"]))
            artist = str(choice.get("artist", "")).strip().casefold()
            if artist:
                recent.append(artist); recent = recent[-max(1, cooldown):]
        return result

    @staticmethod
    def probe_duration(path: str) -> float:
        try:
            info = probe_audio_file(path, timeout=30.0)
            return max(0.0, float(info.get("duration", 0.0)))
        except Exception:
            return 0.0

    def stream_target(self) -> str:
        source = urllib.parse.quote(str(CONFIG["source_password"]), safe="")
        return f"icecast://source:{source}@{CONFIG['icecast_host']}:{CONFIG.get('icecast_encoder_port', 14001)}{CONFIG['icecast_mount']}"

    def encoder_command(self) -> list[str]:
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-f", "s16le", "-ar", str(self.PCM_RATE), "-ac", str(self.PCM_CHANNELS), "-i", "pipe:0",
            "-vn", "-codec:a", "libmp3lame", "-b:a", "128k", "-content_type", "audio/mpeg",
            "-ice_name", str(CONFIG.get("station_name", APP_NAME)),
            "-ice_description", str(CONFIG.get("station_description", "")),
            "-f", "mp3", self.stream_target(),
        ]

    def decoder_command(self, track: dict[str, Any]) -> list[str]:
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-re", "-i", str(track["path"]),
            "-vn", "-f", "s16le", "-ar", str(self.PCM_RATE), "-ac", str(self.PCM_CHANNELS), "pipe:1",
        ]

    def ad_decoder_command(self, path: Path) -> list[str]:
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
            "-vn", "-f", "s16le", "-ar", str(self.PCM_RATE), "-ac", str(self.PCM_CHANNELS), "pipe:1",
        ]

    def available_ads(self) -> list[Path]:
        if not AD_DIR.is_dir():
            return []
        ad_meta = load_ad_meta()
        assets = ad_meta.get("ads", {})
        return sorted(path for path in AD_DIR.iterdir() if path.is_file()
                      and path.suffix.lower() in AUDIO_EXTENSIONS
                      and assets.get(path.name, {}).get("enabled", True)
                      and shared_stream_asset_allowed(path, ad_meta))

    def choose_ad(self) -> Path | None:
        available = self.available_ads()
        if not available:
            return None
        # A ready AI clip is consumed at the next normal ad break; it never
        # forces an interruption and is removed from rotation after playback.
        ai_ready = [path for path in available if path.name.startswith("ai-")]
        if ai_ready:
            chosen = sorted(ai_ready)[0]
            self.last_ad = chosen
            return chosen
        if not self.ad_pool:
            self.ad_pool = available[:]
            random.SystemRandom().shuffle(self.ad_pool)
            if len(self.ad_pool) > 1 and self.ad_pool[-1] == self.last_ad:
                self.ad_pool[0], self.ad_pool[-1] = self.ad_pool[-1], self.ad_pool[0]
        chosen = self.ad_pool.pop()
        self.last_ad = chosen
        return chosen

    def start_due_ad(self) -> None:
        if self.ad_decoder or self.live_pause.is_set():
            return
        forced = self.forced_ad
        self.forced_ad = None
        manual = forced is not None
        if forced is not None and forced.exists() and forced.suffix.lower() in AUDIO_EXTENSIONS:
            path = forced
        elif time.monotonic() < self.next_ad_at:
            self.forced_ad = forced
            return
        else:
            path = self.choose_ad()
        if path is not None and not shared_stream_asset_allowed(path):
            event_log("shared_stream_asset_blocked", name=path.name, automatic=not manual)
            path = None
        if path is None:
            self.next_ad_at = time.monotonic() + float(load_ad_meta().get("interval_seconds", self.AD_INTERVAL_SECONDS))
            return
        self.ad_decoder = subprocess.Popen(
            self.ad_decoder_command(path), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        )
        with self.lock:
            self.state.ad_playing = True
            self.state.ad_name = path.stem
            self.state.sequence += 1
        self.current_ad_path = path
        self.current_ad_manual = manual
        self.current_ad_started_at = int(time.time())
        meta = load_ad_meta()
        info = meta.setdefault("ads", {}).setdefault(path.name, {})
        info["last_played"] = self.current_ad_started_at
        info["play_count"] = int(info.get("play_count", 0)) + 1
        save_ad_meta(meta)
        event_log("advertisement_started", name=path.name, automatic=not manual)

    def stop_ad(self, schedule_next: bool = True) -> None:
        proc = self.ad_decoder
        self.ad_decoder = None
        was_automatic = not self.current_ad_manual
        had_ad = self.current_ad_path is not None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        with self.lock:
            self.state.ad_playing = False
            self.state.ad_name = ""
            if had_ad:
                self.state.sequence += 1
        completed_path = self.current_ad_path
        event_log("advertisement_ended", name=completed_path.name if completed_path else "", automatic=not self.current_ad_manual, duration=max(0, int(time.time()) - self.current_ad_started_at), completed=True)
        if completed_path and completed_path.name.startswith("ai-"):
            meta = load_ad_meta()
            info = meta.setdefault("ads", {}).setdefault(completed_path.name, {})
            info["enabled"] = False
            info["last_played"] = int(time.time())
            save_ad_meta(meta)
        self.current_ad_path = None
        self.current_ad_manual = False
        self.current_ad_started_at = 0
        if had_ad and was_automatic:
            AI_PRODUCER.break_completed()
        if schedule_next:
            self.next_ad_at = time.monotonic() + float(load_ad_meta().get("interval_seconds", self.AD_INTERVAL_SECONDS))

    def request_ad(self, path: Path) -> None:
        self.forced_ad = path
        self.next_ad_at = 0.0
        self.control_event.set()
        event_log("advertisement_requested", name=path.name, automatic=False)

    def ad_mix_gains(self) -> tuple[float, float]:
        path = self.current_ad_path
        if path is not None and path.name in self.LOUD_ALERT_FILENAMES:
            return self.LOUD_ALERT_MUSIC_DUCK_GAIN, self.LOUD_ALERT_GAIN
        return self.MUSIC_DUCK_GAIN, self.AD_GAIN

    def mix_ad(self, music: bytes) -> bytes:
        frame_bytes = self.PCM_CHANNELS * self.PCM_BYTES_PER_SAMPLE
        remainder = len(music) % frame_bytes
        if remainder:
            music = music[: len(music) - remainder]
        if not music:
            return b""
        self.start_due_ad()
        proc = self.ad_decoder
        if not proc or not proc.stdout:
            return music
        ad = proc.stdout.read(len(music))
        if not ad:
            self.stop_ad()
            return music
        if len(ad) < len(music):
            ad += b"\x00" * (len(music) - len(ad))
        elif len(ad) > len(music):
            ad = ad[: len(music)]
        music_gain, ad_gain = self.ad_mix_gains()
        scaled_music = audioop.mul(music, 2, music_gain)
        scaled_ad = audioop.mul(ad, 2, ad_gain)
        return audioop.add(scaled_music, scaled_ad, 2)

    @property
    def chunk_bytes(self) -> int:
        return int(self.PCM_RATE * self.PCM_CHANNELS * self.PCM_BYTES_PER_SAMPLE * self.PCM_CHUNK_SECONDS)

    def wait_for_icecast(self, timeout: float = 20.0) -> None:
        deadline = time.time() + timeout
        last_error = ""
        while time.time() < deadline and not SHUTDOWN.is_set():
            try:
                with socket.create_connection((str(CONFIG.get("icecast_host", "127.0.0.1")), int(CONFIG.get("icecast_port", ICECAST_PORT))), timeout=1):
                    return
            except OSError as exc:
                last_error = str(exc)
                time.sleep(0.5)
        raise RuntimeError(f"Icecast is not accepting connections on port {CONFIG.get('icecast_port', ICECAST_PORT)}: {last_error or 'timeout'}")

    def start_encoder(self) -> None:
        if self.live_pause.is_set():
            return
        if self.encoder and self.encoder.poll() is None:
            return
        self.stop_encoder()
        self.wait_for_icecast()
        self.encoder = subprocess.Popen(
            self.encoder_command(), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, bufsize=0,
        )
        with self.lock:
            self.state.running = True
            self.state.pid = self.encoder.pid
            self.state.last_error = ""

    def stop_encoder(self) -> None:
        proc = self.encoder
        self.encoder = None
        with self.lock:
            self.state.running = False
            self.state.pid = None
        if not proc:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    def stop_decoder(self) -> None:
        proc = self.decoder
        self.decoder = None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    def stop_process(self) -> None:
        self.stop_decoder()
        self.stop_ad()
        self.stop_encoder()

    def write_pcm(self, data: bytes) -> None:
        if not data or self.live_pause.is_set():
            return
        last_error = ""
        for attempt in range(3):
            self.start_encoder()
            encoder = self.encoder
            if encoder is None or not encoder.stdin:
                last_error = "AutoDJ encoder input is unavailable"
            else:
                try:
                    encoder.stdin.write(data)
                    encoder.stdin.flush()
                    if attempt:
                        event_log("autodj_encoder_recovered", attempt=attempt + 1, pid=encoder.pid)
                    return
                except (BrokenPipeError, OSError) as exc:
                    last_error = f"AutoDJ encoder disconnected: {exc}"
            event_log("autodj_encoder_connection_lost", attempt=attempt + 1, error=last_error)
            self.stop_encoder()
            if self.live_pause.is_set() or SHUTDOWN.is_set():
                return
            time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(last_error or "AutoDJ encoder could not reconnect")

    def _set_pending(self, action: str, track_id: int | None = None) -> None:
        with self.lock:
            self.pending_action = (action, track_id)
        self.control_event.set()

    def request_next(self) -> None:
        self._set_pending("next")

    def request_previous(self) -> None:
        self._set_pending("previous")

    def request_restart(self) -> None:
        self._set_pending("restart")

    def reshuffle(self) -> None:
        with self.lock:
            self.rotation_order = []
            self.rotation_seen.clear()
            self.rotation_index = 0
            self.save_rotation_state()
        self._set_pending("next")

    def request_track(self, track_id: int) -> None:
        self._set_pending("play", int(track_id))

    def pause_for_live(self, seconds: float = 20.0) -> None:
        """Release /live.mp3 so a DJ source can take over.

        The watchdog automatically restores AutoDJ if the DJ never connects or
        after the live source disconnects, so a crashed DJ app cannot leave
        the station silent.
        """
        with self.lock:
            self.live_handoff_until = time.time() + max(8.0, seconds)
            self.live_source_seen = False
            self.live_source_last_seen = 0.0
            self.state.mode = "handing off to live DJ"
            self.state.transition_reason = "live_handoff"
            self.state.sequence += 1
        self.live_pause.set()
        self.control_event.set()
        self.stop_decoder()
        self.stop_encoder()

    def resume_after_live(self, reason: str = "live_ended") -> None:
        archive_manager = globals().get("ARCHIVES")
        if archive_manager is not None:
            try:
                archive_manager.stop(reason)
            except Exception as exc:
                event_log("takeover_recording_stop_failed", reason=reason, error=str(exc))
        with self.lock:
            self.live_handoff_until = 0.0
            self.live_source_seen = False
            self.live_source_last_seen = 0.0
            self.state.transition_reason = reason
            self.state.sequence += 1
        self.live_pause.clear()
        self._set_pending("refresh")

    def live_handoff_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "paused": self.live_pause.is_set(),
                "deadline": self.live_handoff_until,
                "source_seen": self.live_source_seen,
                "last_seen": self.live_source_last_seen,
            }

    def library_changed(self) -> None:
        with self.lock:
            empty = self.state.current_track_id is None
        if empty:
            self._set_pending("refresh")

    def track_metadata_changed(self, track: dict[str, Any]) -> None:
        track_id = int(track["id"])
        eligible = bool(track["approved"] and track["enabled"] and rights_filter_allows(track))
        with self.lock:
            is_current = self.state.current_track_id == track_id
            if is_current and eligible:
                self.state.current_title = str(track.get("title", ""))
                self.state.current_artist = str(track.get("artist", ""))
            if self.state.next_track_id == track_id and eligible:
                self.state.next_title = str(track.get("title", ""))
                self.state.next_artist = str(track.get("artist", ""))
        if is_current and not eligible:
            self.request_next()
        elif not is_current:
            self.library_changed()

    def consume_action(self) -> tuple[str, int | None] | None:
        with self.lock:
            action = self.pending_action
            self.pending_action = None
        self.control_event.clear()
        return action

    def index_for_action(self, tracks: list[dict[str, Any]], action: tuple[str, int | None] | None) -> int:
        if not tracks:
            return 0
        current_id = self.state.current_track_id
        current_index = next((i for i, item in enumerate(tracks) if item["id"] == current_id), self.rotation_index % len(tracks))
        if not action:
            return self.rotation_index % len(tracks)
        name, target = action
        if name == "play" and target is not None:
            return next((i for i, item in enumerate(tracks) if int(item["id"]) == int(target)), current_index)
        if name == "next":
            return (current_index + 1) % len(tracks)
        if name == "previous":
            return (current_index - 1) % len(tracks)
        if name in ("restart", "refresh"):
            return current_index
        return current_index

    def update_current(self, tracks: list[dict[str, Any]], index: int, reason: str) -> None:
        track = tracks[index]
        self.rotation_seen.add(int(track["id"]))
        nxt = tracks[(index + 1) % len(tracks)] if len(tracks) > 1 else track
        track_duration = float(track.get("duration") or 0.0)
        if track_duration <= 0.0:
            track_duration = self.probe_duration(str(track["path"]))
        with self.lock:
            self.state.mode = "catalog rotation"
            self.state.tracks = len(tracks)
            self.state.current_track_id = int(track["id"])
            self.state.current_title = str(track.get("title", ""))
            self.state.current_artist = str(track.get("artist", ""))
            self.state.started_at = int(time.time())
            self.state.position_seconds = 0.0
            self.state.duration_seconds = track_duration
            self.state.next_track_id = int(nxt["id"])
            self.state.next_title = str(nxt.get("title", ""))
            self.state.next_artist = str(nxt.get("artist", ""))
            self.state.transition_reason = reason
            self.state.sequence += 1
        event_log("track_started", track_id=int(track["id"]), title=str(track.get("title", "")), artist=str(track.get("artist", "")), reason=reason)
        self.save_rotation_state()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            data = dict(self.state.__dict__)
        if data.get("running") and data.get("started_at"):
            elapsed = max(0.0, time.time() - float(data["started_at"]))
            duration = float(data.get("duration_seconds") or 0.0)
            data["position_seconds"] = min(elapsed, duration) if duration else elapsed
            data["progress"] = min(1.0, data["position_seconds"] / duration) if duration else 0.0
        else:
            data["progress"] = 0.0
        data["mic_overlay"] = self.mic_overlay.snapshot()
        return data

    def queue_snapshot(self) -> dict[str, Any]:
        tracks = self.load_rotation()
        snap = self.snapshot()
        current_id = snap.get("current_track_id")
        current_index = next((i for i, item in enumerate(tracks) if item["id"] == current_id), 0)
        ordered = tracks[current_index:] + tracks[:current_index] if tracks else []
        queue = []
        for offset, item in enumerate(ordered):
            queue.append({
                "id": int(item["id"]), "title": item.get("title", ""), "artist": item.get("artist", ""),
                "source_url": item.get("source_url", ""), "is_current": offset == 0 and current_id is not None,
                "is_next": offset == 1 or (len(ordered) == 1 and offset == 0), "queue_position": offset + 1,
            })
        return {"state": snap, "queue": queue}

    def stream_silence_until_catalog(self) -> None:
        with self.lock:
            self.state.mode = "waiting for approved catalog"
            self.state.tracks = 0
            self.state.current_track_id = None
            self.state.current_title = "Upload the Ebmarah catalog"
            self.state.current_artist = "AllThings140Radio"
            self.state.started_at = int(time.time())
            self.state.position_seconds = 0.0
            self.state.duration_seconds = 0.0
            self.state.next_track_id = None
            self.state.next_title = ""
            self.state.next_artist = ""
            self.state.sequence += 1
        silence = b"\x00" * self.chunk_bytes
        while not SHUTDOWN.is_set() and not self.control_event.is_set() and not self.live_pause.is_set():
            self.write_pcm(silence)
            time.sleep(self.PCM_CHUNK_SECONDS)
        self.consume_action()

    def stream_track(self, track: dict[str, Any], allow_fallback: bool = True) -> bool:
        self.stop_decoder()
        track_started_at = time.time()
        self.decoder = subprocess.Popen(
            self.decoder_command(track), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        )
        event_log("decoder_start", track_id=int(track["id"]), path=str(track.get("path", "")), pid=self.decoder.pid)
        assert self.decoder.stdout is not None
        interrupted = False
        while not SHUTDOWN.is_set():
            if self.live_pause.is_set() or self.control_event.is_set():
                interrupted = True
                break
            chunk = self.decoder.stdout.read(self.chunk_bytes)
            if not chunk:
                break
            self.write_pcm(self.mic_overlay.mix(self.mix_ad(chunk)))
        return_code = self.decoder.poll() if self.decoder else None
        if not interrupted:
            if return_code not in (None, 0):
                elapsed = max(0.0, time.time() - track_started_at)
                event_log("decoder_exit", track_id=int(track["id"]), pid=self.decoder.pid if self.decoder else None, return_code=return_code, playback_offset=round(elapsed, 2))
                event_log("track_failed", track_id=int(track["id"]), title=str(track.get("title", "")), return_code=return_code, playback_offset=round(elapsed, 2))
                if allow_fallback and FALLBACK_MUSIC_DIR is not None:
                    fallback = FALLBACK_MUSIC_DIR / str(track.get("filename", ""))
                    if fallback.exists() and str(fallback) != str(track.get("path", "")):
                        # Never replay a partially played song from offset 0.  A
                        # failed source is skipped; the next selected local
                        # track is less disruptive than a conspicuous restart.
                        event_log("track_storage_fallback", track_id=int(track["id"]), filename=fallback.name, action="skip_current_track", playback_offset=round(elapsed, 2))
                event_log("track_skipped", track_id=int(track["id"]), title=str(track.get("title", "")), reason="decoder_failure")
            else:
                event_log("decoder_exit", track_id=int(track["id"]), pid=self.decoder.pid if self.decoder else None, return_code=0, playback_offset=round(max(0.0, time.time() - track_started_at), 2))
                event_log("track_ended", track_id=int(track["id"]), title=str(track.get("title", "")))
        self.stop_decoder()
        # A tiny silent bridge prevents a click while switching decoders.
        if not SHUTDOWN.is_set():
            self.write_pcm(b"\x00" * int(self.chunk_bytes / 2))
        return interrupted

    def run(self) -> None:
        pending_reason = "startup"
        while not SHUTDOWN.is_set():
            try:
                if self.live_pause.is_set():
                    self.stop_process()
                    with self.lock:
                        self.state.running = False
                        self.state.pid = None
                    time.sleep(0.25)
                    continue
                self.start_encoder()
                tracks = self.load_rotation()
                if not tracks:
                    self.stream_silence_until_catalog()
                    continue
                action = self.consume_action()
                self.rotation_index = self.index_for_action(tracks, action)
                if pending_reason == "startup" and self.resume_advance and not action:
                    self.rotation_index = (self.rotation_index + 1) % len(tracks)
                    self.resume_advance = False
                    event_log("startup_advance_after_restart", track_index=self.rotation_index)
                if action:
                    pending_reason = action[0]
                self.update_current(tracks, self.rotation_index, pending_reason)
                pending_reason = "automatic"
                interrupted = self.stream_track(tracks[self.rotation_index])
                if SHUTDOWN.is_set():
                    break
                if interrupted:
                    action = self.consume_action()
                    self.rotation_index = self.index_for_action(tracks, action)
                    pending_reason = action[0] if action else "control"
                else:
                    AI_PRODUCER.track_finished()
                    self.rotation_index = (self.rotation_index + 1) % len(tracks)
                    pending_reason = "automatic"
            except FileNotFoundError as exc:
                with self.lock:
                    self.state.last_error = f"Required audio tool is missing: {exc.filename or exc}"
                time.sleep(8)
            except Exception as exc:
                traceback.print_exc()
                with self.lock:
                    self.state.last_error = str(exc)
                    self.state.mode = "retrying audio source"
                self.stop_process()
                if not SHUTDOWN.is_set():
                    time.sleep(3)
            finally:
                if SHUTDOWN.is_set():
                    self.stop_process()
                    with self.lock:
                        self.state.running = False
                        self.state.pid = None
        self.stop_process()


AUTODJ = AutoDJManager()


class AIAnnouncementProducer(threading.Thread):
    """Prepares short AI clips for the existing advertisement mixer.

    This thread never writes to the Icecast encoder and never interrupts a
    track. It only creates one bounded, verified WAV clip after the normal
    4–7-song gate; AutoDJ decides when that clip can actually be mixed.
    """

    def __init__(self) -> None:
        super().__init__(daemon=True, name="AIAnnouncementProducer")
        self.scheduler = AnnouncementScheduler(4, 7)
        self.wake = threading.Event()
        self.lock = threading.RLock()
        self.last_attempt = 0.0

    def track_finished(self) -> None:
        if self.scheduler.track_finished():
            self.wake.set()

    def break_completed(self) -> None:
        self.scheduler.break_completed()
        self.wake.clear()

    def context(self) -> dict[str, Any]:
        snap = AUTODJ.snapshot()
        rows = takeover_rows(True)
        records = [
            Takeover(
                id=str(row.get("id", "")), artistName=str(row.get("artist", "")),
                displayName=str(row.get("title") or row.get("artist") or ""),
                startDateTime=int(row.get("starts_at", 0) or 0), endDateTime=int(row.get("ends_at", 0) or 0),
                timezone=str(row.get("timezone") or "America/Los_Angeles"),
                description=str(row.get("details") or ""), enabled=str(row.get("status")) == "published",
            )
            for row in rows
        ]
        context: dict[str, Any] = {
            "stationUrl": AI_HOST.config.stationUrl,
            "currentTime": int(time.time()),
            "songsSinceLastAnnouncement": self.scheduler.songs_since_break,
            "previousTrack": {"artist": snap.get("current_artist", ""), "title": snap.get("current_title", "")},
            "nextTrack": {"artist": snap.get("next_artist", ""), "title": snap.get("next_title", "")},
        }
        upcoming = takeover_context(records)
        if upcoming:
            context["upcomingTakeover"] = upcoming
        return context

    def pending_clip(self) -> Path | None:
        meta = load_ad_meta().get("ads", {})
        for path in sorted(AD_DIR.glob("ai-*.wav"), key=lambda item: item.stat().st_mtime if item.exists() else 0):
            if path.exists() and meta.get(path.name, {}).get("enabled", True):
                return path
        return None

    def generate_clip(self) -> None:
        if not AI_HOST.config.enabled or self.pending_clip() or time.monotonic() - self.last_attempt < 45:
            return
        self.last_attempt = time.monotonic()
        context = self.context()
        kind = AI_HOST.select_type(context)
        persona = next((item for item in AI_HOST.personas.discover() if item.enabled), None)
        text = AI_HOST.generate(kind, context, persona)
        if not text:
            event_log("ai_announcement_generation_skipped", announcement_type=kind, reason="model_timeout_or_rejection")
            return
        audio = AI_HOST.synthesize(text, persona.voiceId if persona else "")
        if not audio or not audio.exists():
            event_log("ai_announcement_synthesis_skipped", announcement_type=kind, reason="no_working_voice_provider")
            return
        filename = f"ai-{hashlib.sha256((kind + text).encode()).hexdigest()[:20]}.wav"
        destination = AD_DIR / filename
        try:
            shutil.copy2(audio, destination)
            meta = load_ad_meta()
            meta.setdefault("ads", {})[filename] = {"display_name": f"AI Host — {kind}", "enabled": True, "ai_generated": True, "text": text, "created_at": int(time.time())}
            save_ad_meta(meta)
            event_log("ai_announcement_prepared", name=filename, announcement_type=kind)
        except OSError as exc:
            event_log("ai_announcement_prepare_failed", error=str(exc))

    def trigger_after_next_song(self) -> None:
        """Arm one prepared AI clip for after the current and next track."""
        path = self.pending_clip()
        if not path:
            self.generate_clip()
            path = self.pending_clip()
        if not path:
            event_log("ai_announcement_trigger_failed", reason="no_prepared_clip")
            return
        snap = AUTODJ.snapshot()
        remaining = max(0.0, float(snap.get("duration_seconds") or 0.0) - float(snap.get("position_seconds") or 0.0))
        next_duration = 0.0
        next_id = snap.get("next_track_id")
        if next_id:
            for track in AUTODJ.load_rotation():
                if int(track.get("id", 0)) == int(next_id):
                    next_duration = AUTODJ.probe_duration(str(track.get("path", "")))
                    break
        AUTODJ.forced_ad = path
        AUTODJ.next_ad_at = time.monotonic() + remaining + next_duration + 1.0
        event_log("ai_announcement_trigger_armed", name=path.name, delay_seconds=round(remaining + next_duration + 1.0, 1))

    def trigger_now(self) -> None:
        path = self.pending_clip()
        if not path:
            self.generate_clip()
            path = self.pending_clip()
        if not path:
            event_log("ai_announcement_trigger_failed", reason="no_prepared_clip")
            return
        AUTODJ.forced_ad = path
        AUTODJ.next_ad_at = 0.0
        event_log("ai_announcement_trigger_now_armed", name=path.name)

    def run(self) -> None:
        while not SHUTDOWN.is_set():
            if AI_NOW_TRIGGER_PATH.exists():
                try:
                    AI_NOW_TRIGGER_PATH.unlink()
                except OSError:
                    pass
                try:
                    self.trigger_now()
                except Exception as exc:
                    event_log("ai_announcement_trigger_failed", reason=str(exc))
            if AI_TRIGGER_PATH.exists():
                try:
                    AI_TRIGGER_PATH.unlink()
                except OSError:
                    pass
                try:
                    self.trigger_after_next_song()
                except Exception as exc:
                    event_log("ai_announcement_trigger_failed", reason=str(exc))
            if AI_HOST.config.enabled and self.scheduler.songs_since_break >= self.scheduler.minimum_songs:
                try:
                    self.generate_clip()
                except Exception as exc:
                    event_log("ai_announcement_failed", error=str(exc))
            self.wake.wait(5)
            self.wake.clear()


AI_PRODUCER = AIAnnouncementProducer()


class GuestIngestManager:
    """Feeds authenticated browser audio into the existing live Icecast mount."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.process: subprocess.Popen[bytes] | None = None
        self.invite_id: int | None = None
        self.last_chunk_at = 0.0
        self.last_sequence = -1

    def start(self, invite_id: int) -> None:
        with self.lock:
            if self.process and self.process.poll() is None:
                if self.invite_id != invite_id:
                    raise RuntimeError("Another guest is already live")
                return
            AUTODJ.pause_for_live(35)
            time.sleep(0.8)
            source = urllib.parse.quote(str(CONFIG["source_password"]), safe="")
            target = f"icecast://source:{source}@{CONFIG['icecast_host']}:{CONFIG['icecast_port']}{CONFIG['icecast_mount']}"
            self.process = subprocess.Popen([
                "ffmpeg", "-hide_banner", "-loglevel", "warning", "-f", "webm", "-i", "pipe:0",
                "-vn", "-codec:a", "libmp3lame", "-b:a", "128k", "-content_type", "audio/mpeg",
                "-ice_name", "AllThings140Radio Guest DJ", "-f", "mp3", target,
            ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.invite_id = invite_id
            self.last_chunk_at = time.time()
            self.last_sequence = -1
            with DB_LOCK, db_connect() as db:
                db.execute("UPDATE guest_invites SET status='live',connected_at=? WHERE id=?", (int(time.time()), invite_id))
                db.commit()
                guest = db.execute("SELECT guest_name FROM guest_invites WHERE id=?", (invite_id,)).fetchone()
            archive_start_when_live(str(guest["guest_name"] if guest else "Guest DJ"), "browser_guest")

    def write(self, invite_id: int, sequence: int, chunk: bytes) -> None:
        self.start(invite_id)
        with self.lock:
            if not self.process or self.process.poll() is not None or not self.process.stdin:
                raise RuntimeError("Guest audio encoder is unavailable")
            if sequence <= self.last_sequence:
                return
            if sequence != self.last_sequence + 1:
                raise RuntimeError("Guest audio chunk arrived out of order")
            self.process.stdin.write(chunk)
            self.process.stdin.flush()
            self.last_sequence = sequence
            self.last_chunk_at = time.time()

    def stop(self, reason: str = "guest_ended") -> None:
        with self.lock:
            process, invite_id = self.process, self.invite_id
            self.process = None
            self.invite_id = None
            self.last_chunk_at = 0.0
            self.last_sequence = -1
        if process:
            try:
                if process.stdin:
                    process.stdin.close()
                process.wait(timeout=2)
            except Exception:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except Exception:
                    process.kill()
        if invite_id:
            with DB_LOCK, db_connect() as db:
                db.execute("UPDATE guest_invites SET status='ended',ended_at=? WHERE id=?", (int(time.time()), invite_id))
                db.commit()
        AUTODJ.resume_after_live(reason)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            running = bool(self.process and self.process.poll() is None)
            return {"running": running, "invite_id": self.invite_id, "last_chunk_at": self.last_chunk_at}


GUEST_INGEST = GuestIngestManager()


class TraktorIngestManager:
    """Transcode Traktor's Ogg/Vorbis broadcast into the station MP3 mount."""

    MOUNT = "/traktor.ogg"

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.process: subprocess.Popen[bytes] | None = None
        self.armed = False
        self.worker: threading.Thread | None = None

    def prepare(self) -> None:
        with self.lock:
            if self.armed:
                return
            self.armed = True
            self.worker = threading.Thread(target=self._wait_and_relay, daemon=True, name="TraktorIngest")
            self.worker.start()

    def _source_present(self) -> bool:
        sources = icecast_status().get("sources", [])
        if isinstance(sources, dict):
            sources = [sources]
        return any(str(source.get("listenurl", "")).endswith(self.MOUNT) for source in sources)

    def _wait_and_relay(self) -> None:
        try:
            while not SHUTDOWN.is_set():
                with self.lock:
                    if not self.armed:
                        return
                if self._source_present():
                    break
                time.sleep(0.5)
            if SHUTDOWN.is_set():
                return
            AUTODJ.pause_for_live(35)
            time.sleep(0.8)
            source_password = urllib.parse.quote(str(CONFIG["source_password"]), safe="")
            target = f"icecast://source:{source_password}@{CONFIG['icecast_host']}:{CONFIG['icecast_port']}{CONFIG['icecast_mount']}"
            source = f"http://127.0.0.1:{CONFIG['icecast_port']}{self.MOUNT}"
            process = subprocess.Popen([
                "ffmpeg", "-hide_banner", "-loglevel", "warning", "-i", source, "-vn",
                "-ar", "44100", "-ac", "2", "-codec:a", "libmp3lame", "-b:a", "128k",
                "-content_type", "audio/mpeg", "-ice_name", "AllThings140Radio — Traktor Live",
                "-f", "mp3", target,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.lock:
                if not self.armed:
                    process.terminate()
                self.process = process
            archive_start_when_live("Live DJ", "traktor_local")
            process.wait()
        finally:
            with self.lock:
                self.process = None
                was_armed = self.armed
                self.armed = False
            if was_armed:
                AUTODJ.resume_after_live("traktor_disconnected")

    def stop(self) -> None:
        with self.lock:
            self.armed = False
            process = self.process
        if process and process.poll() is None:
            process.terminate()
        AUTODJ.resume_after_live("traktor_ended")

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"armed": self.armed, "running": bool(self.process and self.process.poll() is None)}


TRAKTOR_INGEST = TraktorIngestManager()


class SecureTraktorGuestManager:
    """Owns the one approved, authenticated native Traktor guest feed."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.process: subprocess.Popen[bytes] | None = None
        self.invite_id: int | None = None

    def stream(self, handler: BaseHTTPRequestHandler, invite: dict[str, Any], initial_audio: bytes) -> None:
        invite_id = int(invite["id"])
        with self.lock:
            if self.process and self.process.poll() is None:
                raise RuntimeError("Another Traktor guest is already live")
            AUTODJ.pause_for_live(35)
            time.sleep(0.8)
            source_password = urllib.parse.quote(str(CONFIG["source_password"]), safe="")
            target = f"icecast://source:{source_password}@{CONFIG['icecast_host']}:{CONFIG['icecast_port']}{CONFIG['icecast_mount']}"
            process = subprocess.Popen([
                "ffmpeg", "-hide_banner", "-loglevel", "warning", "-probesize", "32768",
                "-analyzeduration", "1000000", "-i", "pipe:0",
                "-vn", "-ar", "44100", "-ac", "2", "-codec:a", "libmp3lame", "-b:a", "128k",
                "-content_type", "audio/mpeg", "-ice_name", f"AllThings140Radio Guest — {invite['guest_name']}",
                "-f", "mp3", target,
            ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.process = process
            self.invite_id = invite_id
        with DB_LOCK, db_connect() as db:
            db.execute("UPDATE guest_invites SET status='live',connected_at=? WHERE id=?", (int(time.time()), invite_id))
            db.commit()
        archive_start_when_live(str(invite.get("guest_name") or "Guest DJ"), str(invite.get("invite_type") or "traktor_guest"))
        try:
            if process.stdin and initial_audio:
                process.stdin.write(initial_audio)
                process.stdin.flush()
            while process.poll() is None:
                chunk = handler.rfile.read(64 * 1024)
                if not chunk or not process.stdin:
                    break
                process.stdin.write(chunk)
                process.stdin.flush()
        finally:
            self.stop("traktor_guest_disconnected", preserve_approval=True)

    def stop(self, reason: str, preserve_approval: bool = False) -> None:
        with self.lock:
            process, invite_id = self.process, self.invite_id
            self.process = None
            self.invite_id = None
        if process:
            try:
                if process.stdin:
                    process.stdin.close()
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                process.kill()
        if invite_id and preserve_approval:
            with DB_LOCK, db_connect() as db:
                db.execute("UPDATE guest_invites SET status='approved' WHERE id=? AND status='live'", (invite_id,))
                db.commit()
        AUTODJ.resume_after_live(reason)


SECURE_TRAKTOR_GUEST = SecureTraktorGuestManager()


class TraktorGuestSourceHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("traktor-ingest %s - %s\n" % (self.address_string(), fmt % args))

    def do_SOURCE(self) -> None:
        self._receive_source()

    def do_PUT(self) -> None:
        self._receive_source()

    def _receive_source(self) -> None:
        mount = urllib.parse.urlparse(self.path).path
        auth = self.headers.get("Authorization", "")
        try:
            decoded = base64.b64decode(auth.removeprefix("Basic ")).decode("utf-8")
            _username, password = decoded.split(":", 1)
        except Exception:
            return self.send_error(401, "Source authentication required")
        credential_hash = hashlib.sha256(password.encode()).hexdigest()
        now = int(time.time())
        with DB_LOCK, db_connect() as db:
            row = db.execute(
                "SELECT * FROM guest_invites WHERE invite_type IN ('traktor','mixxx') AND source_mount=? AND credential_hash=?",
                (mount, credential_hash),
            ).fetchone()
        if not row:
            return self.send_error(401, "Invalid guest credentials")
        invite = dict(row)
        if invite["expires_at"] <= now:
            return self.send_error(403, "Invite expired")
        if invite["status"] not in ("approved", "live"):
            return self.send_error(403, "Host approval required")
        try:
            # Confirm the source immediately, then collect a small pre-roll while
            # AutoDJ remains on air. The relay can begin with audio already in
            # hand instead of creating silence during decoder/source startup.
            self.send_response(200, "OK")
            self.send_header("Connection", "close")
            self.end_headers()
            initial_audio = self.rfile.read(32 * 1024)
            if not initial_audio:
                return
            SECURE_TRAKTOR_GUEST.stream(self, invite, initial_audio)
        except RuntimeError as exc:
            # The source connection is already acknowledged; closing it tells
            # Traktor to stop/retry without corrupting the HTTP stream.
            self.log_error("Traktor guest rejected after connect: %s", exc)


class GuestIngestWatchdog(threading.Thread):
    def run(self) -> None:
        while not SHUTDOWN.is_set():
            snap = GUEST_INGEST.snapshot()
            if snap["invite_id"] and (not snap["running"] or time.time() - float(snap["last_chunk_at"] or 0) > 8):
                GUEST_INGEST.stop("guest_audio_timeout")
            time.sleep(1)


def guest_invite_for_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with DB_LOCK, db_connect() as db:
        row = db.execute("SELECT * FROM guest_invites WHERE token_hash=?", (token_hash,)).fetchone()
    if not row:
        return None
    invite = dict(row)
    if invite["expires_at"] <= int(time.time()) and invite["status"] not in ("ended", "revoked"):
        with DB_LOCK, db_connect() as db:
            db.execute("UPDATE guest_invites SET status='expired' WHERE id=?", (invite["id"],))
            db.commit()
        invite["status"] = "expired"
    return invite


class LiveHandoffWatchdog(threading.Thread):
    """Guarantee that a live-DJ handoff can never leave dead air."""

    def run(self) -> None:
        missing_since = 0.0
        while not SHUTDOWN.is_set():
            if not AUTODJ.live_pause.is_set():
                missing_since = 0.0
                time.sleep(0.5)
                continue
            status = icecast_status()
            sources = status.get("sources", []) if isinstance(status, dict) else []
            if isinstance(sources, dict):
                sources = [sources]
            mount = str(CONFIG.get("icecast_mount", "/live.mp3"))
            present = any(str(src.get("listenurl", "")).endswith(mount) for src in sources)
            now = time.time()
            with AUTODJ.lock:
                deadline = AUTODJ.live_handoff_until
                if present:
                    AUTODJ.live_source_seen = True
                    AUTODJ.live_source_last_seen = now
            if present:
                missing_since = 0.0
            else:
                if missing_since == 0.0:
                    missing_since = now
                snap = AUTODJ.live_handoff_snapshot()
                if (not snap["source_seen"] and now >= deadline) or (snap["source_seen"] and now - missing_since >= 3.0):
                    AUTODJ.resume_after_live("live_source_disconnected")
                    missing_since = 0.0
            time.sleep(0.75)


class StationWatchdog(threading.Thread):
    """Bounded health checks for AutoDJ, Icecast, and disk space."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.lock = threading.RLock()
        self.last_check_at = 0
        self.last_recovery_at = 0
        self.recovery_count = 0
        self.last_failure = ""

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"state": "recovering" if self.last_recovery_at and time.time() - self.last_recovery_at < 45 else "healthy", "last_check_at": self.last_check_at, "last_recovery_at": self.last_recovery_at, "recovery_count": self.recovery_count, "last_failure": self.last_failure}

    def run(self) -> None:
        last_recovery = 0.0
        last_icecast_bad = False
        icecast_bad_since = 0.0
        startup_grace_until = time.monotonic() + 25.0
        while not SHUTDOWN.is_set():
            now = time.monotonic()
            with self.lock:
                self.last_check_at = int(time.time())
            snap = AUTODJ.snapshot()
            ice = icecast_status()
            disk = disk_status()
            if disk.get("state") in ("warning", "critical"):
                event_log("disk_warning", **disk)
            if not ice.get("online"):
                if not last_icecast_bad:
                    event_log("icecast_lost", detail=ice.get("error", "unavailable"))
                    icecast_bad_since = now
                last_icecast_bad = True
                if icecast_bad_since and now - icecast_bad_since >= 30:
                    NOTIFIER.notify("icecast_offline", "AllThings140Radio: Icecast offline", "Icecast has remained unavailable for at least 30 seconds. The watchdog is attempting recovery.")
                if now >= startup_grace_until and not AUTODJ.live_pause.is_set() and now - last_recovery >= int(CONFIG.get("watchdog_recovery_cooldown_seconds", 30)):
                    AUTODJ.request_restart()
                    event_log("watchdog_recovery_requested", component="icecast")
                    with self.lock:
                        self.last_recovery_at = int(time.time()); self.recovery_count += 1; self.last_failure = "icecast"
                    last_recovery = now
            else:
                if last_icecast_bad:
                    event_log("icecast_recovered")
                last_icecast_bad = False
                icecast_bad_since = 0.0
            if now >= startup_grace_until and not AUTODJ.live_pause.is_set() and snap.get("running") is False and now - last_recovery >= int(CONFIG.get("watchdog_recovery_cooldown_seconds", 30)):
                AUTODJ.request_restart()
                event_log("watchdog_recovery_requested", component="autodj")
                with self.lock:
                    self.last_recovery_at = int(time.time()); self.recovery_count += 1; self.last_failure = "autodj"
                    if self.recovery_count >= 3:
                        NOTIFIER.notify("repeated_autodj_failure", "AllThings140Radio: repeated AutoDJ failure", f"The station watchdog has requested {self.recovery_count} recoveries.")
                last_recovery = now
            time.sleep(10)


class SilenceMonitor(threading.Thread):
    """Observes prolonged stream silence outside live/ad transitions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.lock = threading.RLock()
        self.silent_since = 0.0
        self.last_audio_at = int(time.time())
        self.state = "starting"
        self.error = ""

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            duration = max(0.0, time.time() - self.silent_since) if self.silent_since else 0.0
            return {"state": self.state, "silent": bool(self.silent_since), "silent_seconds": round(duration, 1), "last_audio_at": self.last_audio_at, "error": self.error}

    def run(self) -> None:
        threshold = int(CONFIG.get("silence_warning_seconds", 20))
        while not SHUTDOWN.is_set():
            process: subprocess.Popen[str] | None = None
            try:
                source = f"http://127.0.0.1:{CONFIG['icecast_port']}{CONFIG['icecast_mount']}"
                process = subprocess.Popen([
                    "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "info", "-i", source,
                    "-af", f"silencedetect=noise=-48dB:d={threshold}", "-f", "null", "-",
                ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, bufsize=1)
                with self.lock:
                    self.state = "healthy"; self.error = ""
                assert process.stderr is not None
                for line in process.stderr:
                    if SHUTDOWN.is_set():
                        break
                    if "silence_start:" in line:
                        with self.lock:
                            self.silent_since = time.time(); self.state = "warning"
                        event_log("silence_detected", threshold_seconds=threshold)
                        snap = AUTODJ.snapshot()
                        if not AUTODJ.live_pause.is_set() and not snap.get("ad_playing"):
                            AUTODJ.request_next()
                            event_log("watchdog_recovery_requested", component="silence", action="skip_track")
                    elif "silence_end:" in line:
                        with self.lock:
                            self.silent_since = 0.0; self.last_audio_at = int(time.time()); self.state = "healthy"
                        event_log("silence_cleared")
                process.wait(timeout=2)
            except Exception as exc:
                with self.lock:
                    self.state = "error"; self.error = str(exc)[:300]
                event_log("silence_monitor_error", error=str(exc))
            finally:
                if process and process.poll() is None:
                    process.terminate()
            SHUTDOWN.wait(10)


STATION_WATCHDOG = StationWatchdog(daemon=True, name="StationWatchdog")
SILENCE_MONITOR = SilenceMonitor(daemon=True, name="SilenceMonitor")


_ICECAST_STATUS_LOCK = threading.Lock()
_ICECAST_STATUS_CACHE: dict[str, Any] = {"checked_at": 0.0, "value": {}}


def icecast_status() -> dict[str, Any]:
    now = time.monotonic()
    with _ICECAST_STATUS_LOCK:
        cached = _ICECAST_STATUS_CACHE["value"]
        if cached and now - float(_ICECAST_STATUS_CACHE["checked_at"]) < 1.0:
            return dict(cached)
        value = _fetch_icecast_status()
        _ICECAST_STATUS_CACHE.update({"checked_at": now, "value": value})
        return dict(value)


def _fetch_icecast_status() -> dict[str, Any]:
    url = f"http://127.0.0.1:{CONFIG['icecast_port']}/status-json.xsl"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        sources = data.get("icestats", {}).get("source", [])
        if isinstance(sources, dict):
            sources = [sources]
        listeners = sum(int(src.get("listeners", 0)) for src in sources)
        live = any(str(src.get("listenurl", "")).endswith(str(CONFIG["icecast_mount"])) for src in sources)
        return {"online": True, "listeners": listeners, "live_source": live, "sources": sources}
    except Exception as exc:
        return {"online": False, "listeners": 0, "live_source": False, "error": str(exc)}


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        sock.close()
        return address
    except Exception:
        return "127.0.0.1"


def public_base(handler: BaseHTTPRequestHandler | None = None) -> str:
    host = str(CONFIG.get("public_host", "")).strip()
    if host:
        return host.rstrip("/")
    if handler:
        header_host = handler.headers.get("Host", "")
        if header_host:
            return f"http://{header_host}"
    return f"http://{local_ip()}:{PORT}"


def stream_url(handler: BaseHTTPRequestHandler | None = None) -> str:
    configured = str(CONFIG.get("public_stream_url", "")).strip()
    if configured:
        return configured
    base = urllib.parse.urlparse(public_base(handler))
    base_host = base.hostname or local_ip()
    scheme = base.scheme or "http"
    # When public_host is an HTTPS reverse proxy, assume it exposes the stream
    # mount on the same origin. Otherwise use Icecast's native port.
    if scheme == "https":
        return f"{scheme}://{base.netloc}{CONFIG['icecast_mount']}"
    return f"http://{base_host}:{CONFIG['icecast_port']}{CONFIG['icecast_mount']}"


ARCHIVES = ArchiveManager(
    DB_PATH,
    DATA_DIR,
    lambda: f"http://127.0.0.1:{CONFIG['icecast_port']}{CONFIG['icecast_mount']}",
    event_log,
    str(CONFIG.get("archive_storage_provider", "local")),
)
ALERTS = AlertBus(event_log)
SUPPORT = SupportService(str(DB_PATH), DB_LOCK, event_log)
SUBSCRIPTIONS = SubscriptionService(str(DB_PATH), DB_LOCK, SUPPORT.stripe_request, event_log)
NOTIFIER = FailureNotifier(event_log, os.environ.get("ALLTHINGS140_DISCORD_WEBHOOK_URL", ""), int(CONFIG.get("failure_alert_cooldown_seconds", 900)))


def archive_start_when_live(host: str, source: str, timeout: float = 25.0) -> None:
    """Begin recording only after a deliberate handoff has a real live source."""
    def worker() -> None:
        deadline = time.monotonic() + timeout
        while not SHUTDOWN.is_set() and time.monotonic() < deadline:
            if not AUTODJ.live_pause.is_set():
                return
            ice = icecast_status()
            if ice.get("online") and ice.get("live_source"):
                ARCHIVES.start(host or "Guest DJ", f"{host or 'Guest DJ'} Live Takeover", source)
                return
            time.sleep(0.75)
        event_log("takeover_recording_not_started", source=source, reason="live_source_timeout")
    threading.Thread(target=worker, daemon=True, name="ArchiveLiveWait").start()


def public_status(handler: BaseHTTPRequestHandler | None = None) -> dict[str, Any]:
    ice = icecast_status()
    sources = ice.get("sources", []) if isinstance(ice, dict) else []
    if isinstance(sources, dict):
        sources = [sources]
    live_mount = str(CONFIG.get("icecast_mount", "/live.mp3"))
    autodj_mount = str(CONFIG.get("autodj_mount", "/autodj.mp3"))
    selected: dict[str, Any] = {}
    mode = "offline"
    handoff = AUTODJ.live_handoff_snapshot()
    for source in sources:
        listen = str(source.get("listenurl", ""))
        if listen.endswith(live_mount):
            selected = source
            mode = "live" if handoff.get("paused") else "autodj"
            break
    if not selected:
        for source in sources:
            listen = str(source.get("listenurl", ""))
            if listen.endswith(autodj_mount):
                selected = source
                mode = "autodj"
                break
    if not selected and sources:
        selected = sources[0]
        mode = "live" if ice.get("live_source") else "autodj"
    raw_title = str(selected.get("title") or selected.get("server_name") or "").strip()
    artist = ""
    title = raw_title
    if " - " in raw_title:
        artist, title = [part.strip() for part in raw_title.split(" - ", 1)]
    autodj = AUTODJ.snapshot()
    live_host = ""
    if mode == "live":
        invite_id = SECURE_TRAKTOR_GUEST.invite_id or GUEST_INGEST.snapshot().get("invite_id")
        if invite_id:
            with DB_LOCK, db_connect() as db:
                invite_row = db.execute("SELECT guest_name FROM guest_invites WHERE id=?", (int(invite_id),)).fetchone()
            if invite_row:
                live_host = str(invite_row["guest_name"] or "").strip()
    if mode == "autodj" and autodj.get("current_title"):
        title = str(autodj.get("current_title", ""))
        artist = str(autodj.get("current_artist", ""))
    integrity = cached_catalog_integrity_summary()
    integrity_counts = integrity.get("counts", {}) if isinstance(integrity, dict) else {}
    # This endpoint is polled by every listener. Never walk the full catalog on
    # the request path: concurrent resolve_music_path() scans can exhaust the
    # public gateway thread/backlog and make a healthy stream appear offline.
    # The background integrity monitor already maintains these exact values.
    if integrity_counts:
        catalog_total = int(integrity_counts.get("total_catalog", 0) or 0)
        approved = int(integrity_counts.get("playback_ready", 0) or 0)
        missing_approved = int(integrity_counts.get("missing_approved_audio", 0) or 0)
    else:
        catalog_total, approved, missing_approved = catalog_counts()
    takeover = active_takeover()
    return {
        "station_name": CONFIG.get("station_name", APP_NAME),
        "description": CONFIG.get("station_description", ""),
        "website_url": CONFIG.get("website_url", ""),
        "stream_url": stream_url(handler),
        "online": bool(selected),
        "listeners": int(ice.get("listeners", 0) or 0),
        "mode": mode,
        "live": mode == "live",
        "live_host": live_host,
        "active_takeover": takeover,
        "current_title": title,
        "current_artist": artist,
        "current_track_id": autodj.get("current_track_id") if mode == "autodj" else None,
        "started_at": autodj.get("started_at", 0) if mode == "autodj" else 0,
        "position_seconds": autodj.get("position_seconds", 0.0) if mode == "autodj" else 0.0,
        "duration_seconds": autodj.get("duration_seconds", 0.0) if mode == "autodj" else 0.0,
        "progress": autodj.get("progress", 0.0) if mode == "autodj" else 0.0,
        "next_title": autodj.get("next_title", "") if mode == "autodj" else "",
        "next_artist": autodj.get("next_artist", "") if mode == "autodj" else "",
        "station_generation_id": STATION_GENERATION_ID,
        "station_sequence": int(autodj.get("sequence", 0) or 0),
        "server_time": time.time(),
        "stream_status": "online" if bool(selected) else "offline",
        "approved_tracks": int(approved),
        "catalog_tracks": int(catalog_total),
        "missing_approved_tracks": int(missing_approved),
        "catalog_health": integrity.get("health", "unknown"),
        "stored_not_playback_ready": int(integrity.get("counts", {}).get("stored_not_playback_ready", 0)),
        "cache": cache_status(),
        "soundcloud_fallback": {
            "enabled": bool(CONFIG.get("soundcloud_test_enabled", False)),
            "url": str(CONFIG.get("soundcloud_test_url", "")).strip(),
            "title": str(CONFIG.get("soundcloud_test_title", "SoundCloud Test Rotation")).strip() or "SoundCloud Test Rotation",
            "provider": "soundcloud",
        },
        "playback_source": "radio" if bool(selected) else ("soundcloud" if CONFIG.get("soundcloud_test_enabled") and CONFIG.get("soundcloud_test_url") else "offline"),
        "updated_at": int(time.time()),
        "version": VERSION,
    }


def soundcloud_access_token() -> str:
    now = int(time.time())
    if CONFIG.get("soundcloud_access_token") and int(CONFIG.get("soundcloud_token_expires", 0)) > now + 60:
        return str(CONFIG["soundcloud_access_token"])
    client_id = str(CONFIG.get("soundcloud_client_id", ""))
    client_secret = str(CONFIG.get("soundcloud_client_secret", ""))
    if not client_id or not client_secret:
        raise RuntimeError("Add SoundCloud API credentials in Server Settings first.")
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    request = urllib.request.Request(
        "https://secure.soundcloud.com/oauth/token",
        data=body,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        token_data = json.loads(response.read().decode())
    CONFIG["soundcloud_access_token"] = token_data["access_token"]
    CONFIG["soundcloud_refresh_token"] = token_data.get("refresh_token", "")
    CONFIG["soundcloud_token_expires"] = now + int(token_data.get("expires_in", 3600))
    CONFIG_PATH.write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    return str(CONFIG["soundcloud_access_token"])


def soundcloud_search(query: str, genres: str, bpm_from: str, bpm_to: str, limit: int = 30) -> list[dict[str, Any]]:
    token = soundcloud_access_token()
    params: dict[str, str] = {
        "q": query,
        "genres": genres,
        "access": "playable",
        "limit": str(min(max(limit, 1), 50)),
        "linked_partitioning": "true",
    }
    if bpm_from:
        params["bpm[from]"] = bpm_from
    if bpm_to:
        params["bpm[to]"] = bpm_to
    url = "https://api.soundcloud.com/tracks?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": f"OAuth {token}", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode())
    collection = payload.get("collection", payload if isinstance(payload, list) else [])
    results = []
    for item in collection:
        results.append({
            "title": item.get("title", "Untitled"),
            "artist": (item.get("user") or {}).get("username", ""),
            "source_url": item.get("permalink_url", ""),
            "genre": item.get("genre", ""),
            "bpm": item.get("bpm"),
            "artwork_url": item.get("artwork_url") or (item.get("user") or {}).get("avatar_url", ""),
        })
    return results


class DiscoveryResponder(threading.Thread):
    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(1)
        while not SHUTDOWN.is_set():
            try:
                data, addr = sock.recvfrom(2048)
                if data.strip() == b"ALLTHINGS140_DISCOVER":
                    payload = json.dumps({
                        "name": CONFIG.get("station_name", APP_NAME),
                        "url": f"http://{local_ip()}:{PORT}",
                    }).encode()
                    sock.sendto(payload, addr)
            except socket.timeout:
                continue
            except Exception:
                time.sleep(1)
        sock.close()


def serve_archive_file(handler: BaseHTTPRequestHandler, archive_id: str, kind: str) -> None:
    resolved = ARCHIVES.public_file(archive_id, kind)
    if not resolved:
        body = json.dumps({"error": "Archive media not found"}).encode()
        handler.send_response(404)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        if handler.command != "HEAD":
            handler.wfile.write(body)
        return
    path, mime = resolved
    total = path.stat().st_size
    start, end, status = 0, max(0, total - 1), 200
    range_header = handler.headers.get("Range", "")
    if range_header.startswith("bytes="):
        try:
            left, right = range_header[6:].split("-", 1)
            start = int(left) if left else 0
            end = min(total - 1, int(right)) if right else total - 1
            if start < 0 or end < start or start >= total:
                raise ValueError
            status = 206
        except ValueError:
            handler.send_response(416)
            handler.send_header("Content-Range", f"bytes */{total}")
            handler.end_headers()
            return
    length = end - start + 1
    handler.send_response(status)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(length))
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Cache-Control", "public, max-age=3600")
    handler.send_header("Access-Control-Allow-Origin", "*")
    if status == 206:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{total}")
    handler.end_headers()
    if handler.command == "HEAD":
        return
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = length
        while remaining:
            chunk = stream.read(min(64 * 1024, remaining))
            if not chunk:
                break
            try:
                handler.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                break
            remaining -= len(chunk)


class PublicGatewayHandler(BaseHTTPRequestHandler):
    """Public-only gateway used by the HTTPS tunnel.

    This listener deliberately exposes only the read-only public status and the
    shared MP3 mount. Authentication, uploads, DJ controls, settings, and the
    private listener page remain on the LAN control port.
    """

    server_version = f"AllThings140Radio-Public/{VERSION}"

    def setup(self) -> None:
        super().setup()
        # Metadata clients must never occupy a bounded gateway request thread
        # indefinitely after abandoning a Cloudflare connection. The live MP3
        # route bypasses this gateway and connects directly to Icecast.
        self.connection.settimeout(10.0)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("public-gateway %s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Range, Icy-MetaData, X-Guest-Token, X-Audio-Sequence")

    def _json(self, payload: Any, status: int = 200, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self._cors()
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                # Streaming clients and health probes frequently disconnect as
                # soon as they have enough data. That is not a server failure.
                self.close_connection = True

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 5 and parts[:3] == ["api", "public", "archive"] and parts[4] in {"audio", "waveform"}:
            return serve_archive_file(self, parts[3], parts[4])
        if len(parts) == 4 and parts[:3] == ["api", "public", "takeover-logo"]:
            return serve_takeover_logo(self, parts[3])
        if parsed.path in ("/api/public/status", "/public/status.json", "/api/public/archive", "/api/public/schedule", "/health"):
            return self._json({"ok": True})
        if parsed.path == "/live.mp3":
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Accept-Ranges", "none")
            self._cors()
            self.end_headers()
            return
        self._json({"error": "Not found"}, 404)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in ("/api/public/status", "/public/status.json"):
            return self._json(public_status(self))
        if path == "/api/public/archive":
            query = urllib.parse.parse_qs(parsed.query)
            return self._json(ARCHIVES.list_public(
                query.get("limit", ["20"])[0], query.get("offset", ["0"])[0],
                query.get("host", [""])[0], query.get("search", [""])[0],
            ))
        if path == "/api/public/alerts":
            query = urllib.parse.parse_qs(parsed.query)
            return self._json({"alerts": ALERTS.since(int(query.get("since", ["0"])[0]))})
        if path == "/api/public/schedule":
            return self._json({"takeovers": takeover_rows(True)})
        if path == "/api/public/support":
            query = urllib.parse.parse_qs(parsed.query)
            return self._json(SUPPORT.public_state(int(query.get("since", ["0"])[0])))
        if path == "/api/public/support/status":
            query = urllib.parse.parse_qs(parsed.query)
            try:
                return self._json(SUPPORT.checkout_status(query.get("session_id", [""])[0]))
            except SupportError as exc:
                return self._json({"error": str(exc)}, exc.status)
        if path == "/api/account/plus/status":
            try:
                return self._json(SUBSCRIPTIONS.status(self.headers.get("Authorization", "")))
            except SupportError as exc:
                return self._json({"error": str(exc)}, exc.status)
        if path.startswith("/api/public/takeover-logo/"):
            return serve_takeover_logo(self, path.rsplit("/", 1)[-1])
        if path.startswith("/api/public/takeover-invite/"):
            token = path.rsplit("/", 1)[-1]
            invite = takeover_invite(token)
            valid = bool(invite and invite["status"] == "open" and int(invite["expires_at"]) >= int(time.time()))
            return self._json({"valid": valid, "label": invite["label"] if valid else ""}, 200 if valid else 404)
        if path.startswith("/api/public/archive/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                item = ARCHIVES.public_item(parts[3])
                return self._json(item if item else {"error": "Archive not found"}, 200 if item else 404)
            if len(parts) == 5 and parts[4] in {"audio", "waveform"}:
                return serve_archive_file(self, parts[3], parts[4])
        if path == "/health":
            return self._json({"ok": True, "name": CONFIG.get("station_name", APP_NAME), "version": VERSION})
        if path == "/api/guest/session":
            invite = guest_invite_for_token(self.headers.get("X-Guest-Token", "").strip())
            if not invite:
                return self._json({"error": "Guest link is invalid"}, 401)
            ingest = GUEST_INGEST.snapshot()
            return self._json({
                "id": invite["id"], "guest_name": invite["guest_name"], "status": invite["status"],
                "expires_at": invite["expires_at"], "live": ingest.get("invite_id") == invite["id"] and ingest.get("running"),
            })
        if path == "/live.mp3":
            return self.proxy_audio()
        if path == "/":
            return self._json({
                "name": CONFIG.get("station_name", APP_NAME),
                "status": "/api/public/status",
                "stream": "/live.mp3",
                "version": VERSION,
            })
        return self._json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/public/support/webhook":
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 256 * 1024:
                return self._json({"error": "Invalid webhook size"}, 400)
            raw = self.rfile.read(length)
            try:
                signature = self.headers.get("Stripe-Signature", "")
                SUPPORT.verify_signature(raw, signature)
                SUBSCRIPTIONS.stripe_event(json.loads(raw.decode("utf-8")))
                return self._json(SUPPORT.process_webhook(raw, signature))
            except SupportError as exc:
                return self._json({"error": str(exc)}, exc.status)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._json({"error": "Invalid Stripe event."}, 400)
        if path in {"/api/account/plus/checkout", "/api/account/plus/portal"}:
            try:
                action = SUBSCRIPTIONS.checkout if path.endswith("/checkout") else SUBSCRIPTIONS.portal
                return self._json(action(self.headers.get("Authorization", "")), 201)
            except SupportError as exc:
                return self._json({"error": str(exc)}, exc.status)
        if path == "/api/public/support/checkout":
            client_hash = public_client_hash(self)
            allowed, retry = PUBLIC_WRITE_LIMITER.allow(f"support:{client_hash}", 8, 600)
            if not allowed:
                return self._json({"error": "Too many checkout attempts. Please wait and try again."}, 429, {"Retry-After": str(retry)})
            length = min(int(self.headers.get("Content-Length", "0")), 16 * 1024)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                return self._json(SUPPORT.create_checkout(data), 201)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._json({"error": "Invalid JSON body"}, 400)
            except SupportError as exc:
                return self._json({"error": str(exc)}, exc.status)
        if path in {"/api/public/submissions", "/api/public/requests", "/api/public/newsletter", "/api/public/takeover-interest"}:
            length = min(int(self.headers.get("Content-Length", "0")), 32 * 1024)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._json({"error": "Invalid JSON body"}, 400)
            payload, status, retry = public_write(self, path, data)
            return self._json(payload, status, {"Retry-After": str(retry)} if retry else None)
        if path.startswith("/api/public/takeover-invite/"):
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > 3 * 1024 * 1024:
                return self._json({"error": "Logo upload is too large"}, 413)
            length = content_length
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._json({"error": "Invalid JSON body"}, 400)
            payload, status = submit_takeover_invite(path.rsplit("/", 1)[-1], data)
            return self._json(payload, status)
        token = self.headers.get("X-Guest-Token", "").strip()
        invite = guest_invite_for_token(token)
        if not invite:
            return self._json({"error": "Guest link is invalid"}, 401)
        if invite["status"] in ("expired", "revoked", "ended"):
            return self._json({"error": f"Guest session is {invite['status']}"}, 403)
        if path == "/api/guest/join":
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            except Exception:
                data = {}
            guest_name = str(data.get("guest_name", invite["guest_name"])).strip()[:80] or invite["guest_name"]
            with DB_LOCK, db_connect() as db:
                db.execute("UPDATE guest_invites SET guest_name=?,status=CASE WHEN status='invited' THEN 'waiting' ELSE status END WHERE id=?", (guest_name, invite["id"]))
                db.commit()
            return self._json({"ok": True, "status": "waiting", "guest_name": guest_name})
        if path == "/api/guest/audio":
            if invite["status"] not in ("approved", "live"):
                return self._json({"error": "Waiting for host approval"}, 409)
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2 * 1024 * 1024:
                return self._json({"error": "Invalid audio chunk"}, 400)
            try:
                sequence = int(self.headers.get("X-Audio-Sequence", "-1"))
                chunk = self.rfile.read(length)
                GUEST_INGEST.write(int(invite["id"]), sequence, chunk)
                return self._json({"ok": True, "sequence": sequence, "status": "live"})
            except Exception as exc:
                if GUEST_INGEST.snapshot().get("invite_id") == invite["id"]:
                    GUEST_INGEST.stop("guest_audio_error")
                return self._json({"error": str(exc)}, 503)
        if path == "/api/guest/end":
            if GUEST_INGEST.snapshot().get("invite_id") == invite["id"]:
                GUEST_INGEST.stop("guest_ended")
            return self._json({"ok": True, "status": "ended"})
        return self._json({"error": "Not found"}, 404)

    def proxy_audio(self) -> None:
        # Cloudflare Tunnel buffers ordinary long-running HTTP responses. When
        # a separate streaming endpoint (currently Tailscale Funnel) is set,
        # requests arriving on the Cloudflare hostname are redirected there.
        configured = str(CONFIG.get("public_stream_url", "")).strip()
        request_host = self.headers.get("Host", "").split(":", 1)[0].lower()
        configured_host = (urllib.parse.urlparse(configured).hostname or "").lower() if configured else ""
        if configured and configured_host and request_host and configured_host != request_host:
            self.send_response(302)
            self.send_header("Location", configured)
            self.send_header("Cache-Control", "no-store, max-age=0")
            self._cors()
            self.end_headers()
            return

        origin = f"http://127.0.0.1:{CONFIG['icecast_port']}{CONFIG['icecast_mount']}"
        request = urllib.request.Request(
            origin,
            headers={
                "User-Agent": f"AllThings140Radio-PublicGateway/{VERSION}",
                # Track information is supplied by /api/public/status. Avoid
                # injecting ICY metadata bytes into the browser audio stream.
                "Icy-MetaData": "0",
                "Cache-Control": "no-cache",
            },
        )
        headers_sent = False
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self.send_response(getattr(response, "status", 200))
                self.send_header("Content-Type", response.headers.get("Content-Type", "audio/mpeg"))
                icy_name = response.headers.get("icy-name")
                if icy_name:
                    self.send_header("icy-name", icy_name)
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("Connection", "close")
                self._cors()
                self.end_headers()
                headers_sent = True
                # Small chunks let browsers begin playback quickly. The HTTP/1.0
                # connection remains open for the duration of the live stream.
                while not SHUTDOWN.is_set():
                    chunk = response.read(4096)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                self.close_connection = True
        except urllib.error.HTTPError as exc:
            if not headers_sent:
                self._json({"error": "Radio source unavailable", "detail": str(exc)}, 503)
        except Exception as exc:
            if not headers_sent:
                try:
                    self._json({"error": "Radio source unavailable", "detail": str(exc)}, 503)
                except (BrokenPipeError, ConnectionResetError):
                    pass


class Handler(BaseHTTPRequestHandler):
    server_version = f"AllThings140Radio/{VERSION}"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))

    def json_response(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def text_response(self, body: str, content_type: str = "text/html; charset=utf-8", status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 3 * 1024 * 1024:
            raise ValueError("Request too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def auth_user(self, required: bool = True) -> sqlite3.Row | None:
        auth = self.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
        user = session_user(token)
        if required and not user:
            self.json_response({"error": "Authentication required"}, 401)
            return None
        return user

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            if path == "/":
                return self.listener_page()
            if path == "/api/health":
                return self.json_response({"ok": True, "name": CONFIG.get("station_name"), "version": VERSION, "autodj": AUTODJ.snapshot(), "icecast": icecast_status(), "disk": disk_status(), "cache": cache_status(), "watchdog": STATION_WATCHDOG.snapshot(), "silence": SILENCE_MONITOR.snapshot(), "recording": ARCHIVES.snapshot(), "storage": {"provider": ARCHIVES.storage_provider, "remote_available": ARCHIVES.storage_provider == "r2"}, "ads": {"playing": AUTODJ.snapshot().get("ad_playing", False), "name": AUTODJ.snapshot().get("ad_name", "")}})
            if path in ("/api/public/status", "/public/status.json"):
                return self.json_response(public_status(self))
            if path == "/api/public/archive":
                return self.json_response(ARCHIVES.list_public(
                    query.get("limit", ["20"])[0], query.get("offset", ["0"])[0],
                    query.get("host", [""])[0], query.get("search", [""])[0],
                ))
            if path == "/api/public/alerts":
                return self.json_response({"alerts": ALERTS.since(int(query.get("since", ["0"])[0]))})
            if path == "/api/public/schedule":
                return self.json_response({"takeovers": takeover_rows(True)})
            if path == "/api/public/support":
                return self.json_response(SUPPORT.public_state(int(query.get("since", ["0"])[0])))
            if path == "/api/public/support/status":
                return self.json_response(SUPPORT.checkout_status(query.get("session_id", [""])[0]))
            if path == "/api/account/plus/status":
                return self.json_response(SUBSCRIPTIONS.status(self.headers.get("Authorization", "")))
            if path.startswith("/api/public/takeover-logo/"):
                return serve_takeover_logo(self, path.rsplit("/", 1)[-1])
            if path.startswith("/api/public/takeover-invite/"):
                token = path.rsplit("/", 1)[-1]
                invite = takeover_invite(token)
                valid = bool(invite and invite["status"] == "open" and int(invite["expires_at"]) >= int(time.time()))
                return self.json_response({"valid": valid, "label": invite["label"] if valid else ""}, 200 if valid else 404)
            if path.startswith("/api/public/archive/"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    item = ARCHIVES.public_item(parts[3])
                    return self.json_response(item if item else {"error": "Archive not found"}, 200 if item else 404)
                if len(parts) == 5 and parts[4] in {"audio", "waveform"}:
                    return serve_archive_file(self, parts[3], parts[4])
            if path == "/api/status":
                user = self.auth_user()
                if not user:
                    return
                catalog_total, approved, missing_approved = catalog_counts()
                with DB_LOCK, db_connect() as db:
                    review = db.execute("SELECT COUNT(*) FROM review_queue WHERE status='pending'").fetchone()[0]
                ice = icecast_status()
                integrity = cached_catalog_integrity()
                return self.json_response({
                    "station_name": CONFIG.get("station_name"),
                    "description": CONFIG.get("station_description"),
                    "stream_url": stream_url(self),
                    "listener_page": public_base(self),
                    "website_url": CONFIG.get("website_url", ""),
                    "soundcloud_fallback": {
                        "enabled": bool(CONFIG.get("soundcloud_test_enabled", False)),
                        "url": CONFIG.get("soundcloud_test_url", ""),
                        "title": CONFIG.get("soundcloud_test_title", "SoundCloud Test Rotation"),
                    },
                    "autodj": AUTODJ.snapshot(),
                    "rotation": AUTODJ.queue_snapshot().get("queue", []),
                    "current_track_id": AUTODJ.snapshot().get("current_track_id"),
                    "current_title": AUTODJ.snapshot().get("current_title", ""),
                    "current_artist": AUTODJ.snapshot().get("current_artist", ""),
                    "icecast": ice,
                    "approved_tracks": approved,
                    "catalog_tracks": catalog_total,
                    "missing_approved_tracks": missing_approved,
                    "catalog_integrity": {"health": integrity.get("health", "unknown"), "counts": integrity.get("counts", {}), "generated_at": integrity.get("generated_at", 0)},
                    "pending_reviews": review,
                    "disk": disk_status(),
                    "cache": cache_status(),
                    "watchdog": STATION_WATCHDOG.snapshot(),
                    "silence": SILENCE_MONITOR.snapshot(),
                    "recording": ARCHIVES.snapshot(),
                    "storage": {"provider": ARCHIVES.storage_provider, "remote_available": ARCHIVES.storage_provider == "r2", "retention": CONFIG.get("archive_retention_mode", "keep_all")},
                    "ads": {"playing": AUTODJ.snapshot().get("ad_playing", False), "name": AUTODJ.snapshot().get("ad_name", "")},
                })
            if path == "/api/events":
                user = self.auth_user()
                if not user:
                    return
                limit = max(1, min(200, int(query.get("limit", ["50"])[0])))
                try:
                    lines = EVENT_LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
                    events = [json.loads(line) for line in lines if line.strip()]
                except (OSError, ValueError):
                    events = []
                return self.json_response({"events": events})
            if path == "/api/ai/status":
                user = self.auth_user()
                if not user:
                    return
                return self.json_response(AI_HOST.status())
            if path == "/api/rotation-audit":
                user = self.auth_user()
                if not user:
                    return
                return self.json_response(rotation_audit_snapshot())
            if path == "/api/takeovers":
                user = self.auth_user()
                if not user:
                    return
                return self.json_response({"takeovers": takeover_rows(False)})
            if path == "/api/archive":
                user = self.auth_user()
                if not user:
                    return
                return self.json_response(ARCHIVES.list_all(100))
            if path == "/api/ads":
                user = self.auth_user()
                if not user:
                    return
                meta = load_ad_meta()
                ads = []
                if AD_DIR.is_dir():
                    for item in sorted(AD_DIR.iterdir(), key=lambda candidate: candidate.name.lower()):
                        if not item.is_file() or item.suffix.lower() not in AUDIO_EXTENSIONS:
                            continue
                        info = meta.get("ads", {}).get(item.name, {})
                        ads.append({"filename": item.name, "name": info.get("display_name", item.stem), "enabled": info.get("enabled", True), "size": item.stat().st_size, "duration": AUTODJ.probe_duration(str(item)), "last_played": info.get("last_played"), "play_count": info.get("play_count", 0), "mean_volume_db": info.get("mean_volume_db"), "peak_db": info.get("peak_db")})
                history = []
                try:
                    for line in reversed(EVENT_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1000:]):
                        row = json.loads(line)
                        if str(row.get("event", "")).startswith("advertisement_") and row.get("event") in {"advertisement_started", "advertisement_ended"}:
                            history.append(row)
                            if len(history) >= 50: break
                except (OSError, ValueError):
                    pass
                return self.json_response({"ads": ads, "interval_seconds": int(meta.get("interval_seconds", 900)), "history": history})
            if path == "/api/me":
                user = self.auth_user()
                if not user:
                    return
                return self.json_response({"username": user["username"], "role": user["role"], "must_change_password": bool(user["must_change_password"])})
            if path == "/api/tracks":
                user = self.auth_user()
                if not user:
                    return
                with DB_LOCK, db_connect() as db:
                    rows = db.execute("SELECT id,title,artist,filename,source_url,rights_confirmed,approved,enabled,created_at FROM tracks ORDER BY id DESC").fetchall()
                return self.json_response([dict(row) for row in rows])
            if path == "/api/catalog-integrity":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                return self.json_response(catalog_integrity_snapshot(False))
            if path.startswith("/api/catalog-operations/"):
                user = self.auth_user()
                if not user:
                    return
                operation_id = path.rsplit("/", 1)[-1]
                with DB_LOCK, db_connect() as db:
                    operation = db.execute("SELECT * FROM catalog_operations WHERE operation_id=?", (operation_id,)).fetchone()
                    items = db.execute("SELECT * FROM catalog_operation_items WHERE operation_id=? ORDER BY track_id", (operation_id,)).fetchall()
                if not operation:
                    return self.json_response({"error": "Operation not found"}, 404)
                payload = dict(operation)
                payload["request"] = json.loads(payload.pop("request_json"))
                payload["result"] = json.loads(payload.pop("result_json"))
                payload["items"] = [{**dict(item), "detail": json.loads(item["detail_json"])} for item in items]
                return self.json_response(payload)
            if path == "/api/tracks/prune-preview":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                current_id = AUTODJ.snapshot().get("current_track_id")
                with DB_LOCK, db_connect() as db:
                    rows = [dict(row) for row in db.execute(
                        "SELECT id,title,artist,filename,rights_confirmed,approved,enabled FROM tracks ORDER BY id"
                    ).fetchall()]
                candidates = []
                for row in rows:
                    missing = not resolve_stored_music_path(row["filename"]).exists()
                    ineligible = not (row["approved"] and row["enabled"] and rights_filter_allows(row))
                    if missing or ineligible:
                        row["reason"] = "missing audio file" if missing else "not approved/enabled/rights-cleared"
                        row["is_current"] = int(row["id"]) == int(current_id or 0)
                        candidates.append(row)
                return self.json_response({"candidates": candidates, "count": len(candidates)})
            if path == "/api/tracks/prune":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                return self.json_response({"error": "Legacy bulk prune is disabled. Review records in Catalog Integrity; missing-audio evidence is never bulk-deleted."}, 409)
            if path == "/api/tracks/duplicates":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                with DB_LOCK, db_connect() as db:
                    rows = [dict(row) for row in db.execute(
                        "SELECT id,title,artist,filename,approved,enabled FROM tracks ORDER BY id"
                    ).fetchall()]
                report = catalog_integrity_snapshot(True)
                by_id = {int(row["id"]): row for row in report["records"]}
                groups = []
                for group in report["duplicate_groups"]:
                    tracks = []
                    for track_id in group["track_ids"]:
                        record = by_id[track_id]
                        tracks.append({
                            "id": track_id, "artist": record["artist"], "title": record["title"],
                            "filename": record["filename"], "resolved_path": record["master"]["path"],
                            "canonical_path": record["master"]["canonical_path"],
                            "size_bytes": record["master"]["size_bytes"], "duration": record.get("duration"),
                            "sha256": record.get("sha256") or group.get("sha256", ""),
                            "approved": record["approved"], "enabled": record["enabled"],
                            "created_at": record["created_at"],
                            "shared_filename_ids": record["shared_filename_ids"],
                        })
                    groups.append({**group, "reason": group["classification"].replace("_", " ").title(), "tracks": tracks})
                return self.json_response({
                    "groups": groups,
                    "exact_duplicate_groups": report["counts"]["exact_duplicate_groups"],
                    "probable_duplicate_groups": report["counts"]["probable_duplicate_groups"],
                    "automatic_cleanup_disabled": True,
                })
            if path == "/api/guest-invites":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                with DB_LOCK, db_connect() as db:
                    rows = [dict(row) for row in db.execute(
                        "SELECT id,guest_name,status,created_at,expires_at,connected_at,ended_at,invite_type FROM guest_invites ORDER BY id DESC LIMIT 30"
                    ).fetchall()]
                return self.json_response({"invites": rows, "ingest": GUEST_INGEST.snapshot()})
            if path == "/api/reviews":
                user = self.auth_user()
                if not user:
                    return
                with DB_LOCK, db_connect() as db:
                    rows = db.execute("SELECT * FROM review_queue ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, id DESC").fetchall()
                return self.json_response([dict(row) for row in rows])
            if path == "/api/autodj/queue":
                user = self.auth_user()
                if not user:
                    return
                return self.json_response(AUTODJ.queue_snapshot())
            if path == "/api/broadcast-config":
                user = self.auth_user()
                if not user:
                    return
                AUTODJ.pause_for_live()
                archive_start_when_live(str(user["username"] or "Live DJ"), "dj_app")
                request_host = self.headers.get("Host", "").split(":", 1)[0].strip()
                host = request_host or local_ip()
                return self.json_response({
                    "host": host,
                    "port": int(CONFIG["icecast_port"]),
                    "mount": CONFIG["icecast_mount"],
                    "source_password": CONFIG["source_password"],
                    "bitrate": 128,
                })
            if path == "/api/traktor-config":
                user = self.auth_user()
                if not user:
                    return
                TRAKTOR_INGEST.prepare()
                request_host = self.headers.get("Host", "").split(":", 1)[0].strip()
                return self.json_response({
                    "host": request_host or local_ip(),
                    "port": int(CONFIG["icecast_port"]),
                    "mount": TRAKTOR_INGEST.MOUNT,
                    "password": CONFIG["source_password"],
                    "format": "Ogg Vorbis, 44100 Hz, 128 kBit/s",
                    "status": TRAKTOR_INGEST.snapshot(),
                })
            if path == "/api/settings":
                user = self.auth_user()
                if not user:
                    return
                safe = {k: CONFIG.get(k, "") for k in (
                    "station_name", "station_description", "public_host", "public_stream_url",
                    "website_url", "soundcloud_client_id", "soundcloud_test_url", "soundcloud_test_title"
                )}
                safe["soundcloud_test_enabled"] = bool(CONFIG.get("soundcloud_test_enabled", False))
                safe["allow_unlicensed_test_mode"] = bool(CONFIG.get("allow_unlicensed_test_mode", False))
                safe["soundcloud_configured"] = bool(CONFIG.get("soundcloud_client_id") and CONFIG.get("soundcloud_client_secret"))
                return self.json_response(safe)
            if path == "/api/support/dashboard":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                return self.json_response(SUPPORT.dashboard())
            if path == "/api/soundcloud/search":
                user = self.auth_user()
                if not user:
                    return
                try:
                    results = soundcloud_search(
                        query.get("q", [""])[0], query.get("genres", [""])[0],
                        query.get("bpm_from", [""])[0], query.get("bpm_to", [""])[0],
                    )
                    return self.json_response(results)
                except Exception as exc:
                    return self.json_response({"error": str(exc)}, 400)
            return self.json_response({"error": "Not found"}, 404)
        except Exception as exc:
            traceback.print_exc()
            return self.json_response({"error": str(exc)}, 500)

    def do_POST(self) -> None:
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/api/public/support/webhook":
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 256 * 1024:
                    return self.json_response({"error": "Invalid webhook size"}, 400)
                raw = self.rfile.read(length)
                signature = self.headers.get("Stripe-Signature", "")
                SUPPORT.verify_signature(raw, signature)
                SUBSCRIPTIONS.stripe_event(json.loads(raw.decode("utf-8")))
                return self.json_response(SUPPORT.process_webhook(raw, signature))
            if path in {"/api/account/plus/checkout", "/api/account/plus/portal"}:
                action = SUBSCRIPTIONS.checkout if path.endswith("/checkout") else SUBSCRIPTIONS.portal
                return self.json_response(action(self.headers.get("Authorization", "")), 201)
            if path == "/api/public/support/checkout":
                allowed, retry = PUBLIC_WRITE_LIMITER.allow(f"support:{public_client_hash(self)}", 8, 600)
                if not allowed:
                    return self.json_response({"error": f"Too many checkout attempts. Try again in {retry} seconds."}, 429)
                return self.json_response(SUPPORT.create_checkout(self.read_json()), 201)
            if path in {"/api/public/submissions", "/api/public/requests", "/api/public/newsletter", "/api/public/takeover-interest"}:
                data = self.read_json()
                payload, status, retry = public_write(self, path, data)
                if retry:
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Retry-After", str(retry))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                return self.json_response(payload, status)
            if path == "/api/ai/test":
                user = self.auth_user()
                if not user:
                    return
                data = self.read_json()
                announcement_type = str(data.get("announcementType") or "STATION_ID")
                if announcement_type not in AI_HOST.config.weights and announcement_type not in ("ARTIST_TAKEOVER_ACTIVE", "ARTIST_TAKEOVER_STARTING", "ARTIST_TAKEOVER_TODAY"):
                    return self.json_response({"error": "Unknown announcement type"}, 400)
                context = data.get("context") if isinstance(data.get("context"), dict) else {"stationUrl": AI_HOST.config.stationUrl}
                text = AI_HOST.generate(announcement_type, context)
                return self.json_response({"ok": bool(text), "enabled": AI_HOST.config.enabled, "text": text or "AI host is disabled or unavailable; music was not interrupted."})
            if path == "/api/ai/disable":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                data = self.read_json()
                enabled = bool(data.get("enabled", False))
                current = {}
                try: current = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8")) if AI_CONFIG_PATH.exists() else {}
                except (OSError, ValueError): current = {}
                current["enabled"] = enabled
                AI_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
                temporary = AI_CONFIG_PATH.with_suffix(".json.tmp")
                temporary.write_text(json.dumps(current, indent=2), encoding="utf-8")
                os.replace(temporary, AI_CONFIG_PATH)
                AI_HOST.config.enabled = enabled
                event_log("ai_host_enabled" if enabled else "ai_host_disabled", user=user["username"])
                return self.json_response({"ok": True, "enabled": enabled})
            if path.startswith("/api/public/takeover-invite/"):
                payload, status = submit_takeover_invite(path.rsplit("/", 1)[-1], self.read_json())
                return self.json_response(payload, status)
            if path == "/api/login":
                data = self.read_json()
                username = str(data.get("username", "")).strip()
                password = str(data.get("password", ""))
                with DB_LOCK, db_connect() as db:
                    user = db.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone()
                if not user or not verify_password(password, user["password_hash"]):
                    time.sleep(0.35)
                    return self.json_response({"error": "Incorrect username or password"}, 401)
                try:
                    remote_is_global = ipaddress.ip_address(self.client_address[0]).is_global
                except ValueError:
                    remote_is_global = True
                if user["must_change_password"] and remote_is_global:
                    return self.json_response({"error": "First login must be completed on the local network or a private VPN such as Tailscale."}, 403)
                token = create_session(int(user["id"]))
                audit(int(user["id"]), "login")
                return self.json_response({
                    "token": token, "username": user["username"], "role": user["role"],
                    "must_change_password": bool(user["must_change_password"]),
                })
            if path == "/api/change-password":
                user = self.auth_user()
                if not user:
                    return
                data = self.read_json()
                current = str(data.get("current_password", ""))
                new = str(data.get("new_password", ""))
                if not verify_password(current, user["password_hash"]):
                    return self.json_response({"error": "Current password is incorrect"}, 400)
                if len(new) < 10:
                    return self.json_response({"error": "Use at least 10 characters"}, 400)
                if new == DEFAULT_PASSWORD:
                    return self.json_response({"error": "Choose a password other than the temporary password"}, 400)
                with DB_LOCK, db_connect() as db:
                    db.execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?", (password_hash(new), user["id"]))
                    db.commit()
                audit(int(user["id"]), "password_changed")
                return self.json_response({"ok": True})
            if path == "/api/takeovers":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                data = self.read_json()
                artist = str(data.get("artist", "")).strip()[:100]
                title = str(data.get("title", "")).strip()[:140]
                details = str(data.get("details", "")).strip()[:500]
                starts_at = int(data.get("starts_at") or 0)
                ends_at = int(data.get("ends_at") or 0)
                try:
                    timezone = valid_timezone(data.get("timezone"))
                    logo_name = store_takeover_logo(data.get("logo_data"))
                except ValueError as exc:
                    return self.json_response({"error": str(exc)}, 400)
                socials = []
                for entry in data.get("socials", []) if isinstance(data.get("socials"), list) else []:
                    platform = str(entry.get("platform", "")).strip()[:30]
                    url = str(entry.get("url", "")).strip()[:500]
                    if platform and re.fullmatch(r"https?://[^\s]+", url):
                        socials.append({"platform": platform, "url": url})
                if not artist or starts_at <= 0 or ends_at <= starts_at:
                    return self.json_response({"error": "Artist, start time, and a valid end time are required"}, 400)
                now = int(time.time())
                with DB_LOCK, db_connect() as db:
                    cursor = db.execute(
                        "INSERT INTO takeovers(artist,title,starts_at,ends_at,details,socials_json,timezone,logo_name,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (artist, title, starts_at, ends_at, details, json.dumps(socials), timezone, logo_name, "published", user["id"], now, now),
                    )
                    db.commit()
                event_log("takeover_scheduled", takeover_id=int(cursor.lastrowid), artist=artist, starts_at=starts_at)
                return self.json_response({"ok": True, "id": int(cursor.lastrowid)})
            if path == "/api/takeover-invites":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                data = self.read_json()
                label = str(data.get("label", "Guest DJ")).strip()[:100] or "Guest DJ"
                days = max(1, min(60, int(data.get("expires_days") or 14)))
                token = secrets.token_urlsafe(32)
                now = int(time.time())
                with DB_LOCK, db_connect() as db:
                    db.execute("INSERT INTO takeover_invites(token_hash,label,status,created_by,created_at,expires_at) VALUES(?,?,'open',?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), label, user["id"], now, now + days * 86400))
                    db.commit()
                return self.json_response({"ok": True, "link": f"https://allthings140radio.online/takeover/#{token}", "expires_at": now + days * 86400})
            if path == "/api/takeovers/delete":
                user = self.auth_user()
                if not user:
                    return
                data = self.read_json()
                takeover_id = int(data.get("id") or 0)
                with DB_LOCK, db_connect() as db:
                    row = db.execute("SELECT logo_name FROM takeovers WHERE id=?", (takeover_id,)).fetchone()
                    db.execute("DELETE FROM takeovers WHERE id=?", (takeover_id,))
                    db.commit()
                if row and row["logo_name"]:
                    (TAKEOVER_LOGO_DIR / str(row["logo_name"])).unlink(missing_ok=True)
                event_log("takeover_schedule_deleted", takeover_id=takeover_id)
                return self.json_response({"ok": True})
            if path == "/api/takeovers/status":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                data = self.read_json()
                takeover_id = int(data.get("id") or 0)
                status = str(data.get("status") or "").strip()
                if status not in {"published", "rejected"}:
                    return self.json_response({"error": "Invalid takeover status"}, 400)
                now = int(time.time())
                with DB_LOCK, db_connect() as db:
                    db.execute("UPDATE takeovers SET status=?,updated_at=? WHERE id=?", (status, now, takeover_id))
                    db.commit()
                event_log("takeover_status_changed", takeover_id=takeover_id, status=status)
                row = next((item for item in takeover_rows(False) if item["id"] == takeover_id), None)
                return self.json_response({"ok": True, "takeover": row})
            if path == "/api/upload":
                user = self.auth_user()
                if not user:
                    return
                upload_id = self.headers.get("X-Upload-ID", "").strip()
                if upload_id and (len(upload_id) > 64 or not upload_id.isalnum()):
                    return self.json_response({"error": "Invalid upload request id"}, 400)
                if upload_id:
                    with DB_LOCK, db_connect() as db:
                        receipt = db.execute(
                            "SELECT response_json FROM upload_receipts WHERE upload_id=? AND user_id=?",
                            (upload_id, int(user["id"])),
                        ).fetchone()
                    if receipt:
                        return self.json_response(json.loads(receipt["response_json"]))
                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in content_type or "boundary=" not in content_type:
                    return self.json_response({"error": "Expected multipart upload"}, 400)
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length > MAX_UPLOAD:
                    return self.json_response({"error": "File exceeds 2 GB limit"}, 413)
                boundary_text = content_type.split("boundary=", 1)[1].strip().strip('"')
                boundary = boundary_text.encode("utf-8")
                remaining = content_length

                def read_line() -> bytes:
                    nonlocal remaining
                    if remaining <= 0:
                        return b""
                    line = self.rfile.readline()
                    remaining -= len(line)
                    return line

                first = read_line()
                if first.strip() != b"--" + boundary:
                    return self.json_response({"error": "Malformed multipart request"}, 400)
                fields: dict[str, str] = {}
                staging_dir = (CACHE_DIR / "tmp_uploads") if CACHE_DIR.is_dir() else (DATA_DIR / "tmp_uploads")
                staging_dir.mkdir(parents=True, exist_ok=True)
                temp_destination: Path | None = None
                original_name = ""
                file_received = False
                while True:
                    headers: dict[str, str] = {}
                    while True:
                        line = read_line()
                        if line in (b"\r\n", b"\n", b""):
                            break
                        if b":" in line:
                            key, value = line.decode("utf-8", "replace").split(":", 1)
                            headers[key.lower().strip()] = value.strip()
                    disposition = headers.get("content-disposition", "")
                    params = {}
                    for piece in disposition.split(";")[1:]:
                        if "=" in piece:
                            key, value = piece.strip().split("=", 1)
                            params[key] = value.strip().strip('"')
                    field_name = params.get("name", "")
                    original_name = params.get("filename", "")
                    if original_name:
                        filename = safe_filename(original_name)
                        if Path(filename).suffix.lower() not in AUDIO_EXTENSIONS:
                            while remaining > 0:
                                line = read_line()
                                if not line or line.startswith(b"--" + boundary):
                                    break
                            return self.json_response({"error": f"Unsupported audio format '{Path(filename).suffix}'"}, 400)
                        upload_kind = fields.get("kind", "track").strip().lower()
                        if upload_kind not in ("track", "ad"):
                            return self.json_response({"error": "Invalid upload kind"}, 400)
                        if upload_kind == "ad" and Path(filename).suffix.lower() != ".mp3":
                            return self.json_response({"error": "Station advertisements must be MP3 files"}, 400)
                        temp_destination = staging_dir / f"upload_{uuid.uuid4().hex}_{filename}"
                        marker = b"\r\n--" + boundary
                        tail_size = len(marker) + 8
                        buffer = b""
                        with temp_destination.open("wb") as out:
                            while remaining > 0:
                                to_read = min(65536, remaining)
                                chunk = self.rfile.read(to_read)
                                if not chunk:
                                    break
                                remaining -= len(chunk)
                                buffer += chunk
                                idx = buffer.find(marker)
                                if idx >= 0:
                                    out.write(buffer[:idx])
                                    buffer = buffer[idx:]
                                    break
                                if len(buffer) > tail_size:
                                    out.write(buffer[:-tail_size])
                                    buffer = buffer[-tail_size:]
                        file_received = True
                        break
                    value_lines = []
                    while True:
                        line = read_line()
                        if line.startswith(b"--" + boundary):
                            final = line.strip().endswith(b"--")
                            break
                        if not line:
                            final = True
                            break
                        value_lines.append(line)
                    fields[field_name] = b"".join(value_lines).decode("utf-8", "replace").rstrip("\r\n")
                    if final:
                        break

                # Drain trailing multipart boundary
                try:
                    while remaining > 0:
                        chunk = self.rfile.read(min(65536, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                except Exception:
                    pass

                if not file_received or temp_destination is None or not temp_destination.is_file():
                    if temp_destination:
                        temp_destination.unlink(missing_ok=True)
                    return self.json_response({"error": "No audio file received or empty upload"}, 400)

                # Validate audio with ffprobe (30.0s timeout)
                try:
                    probe_info = probe_audio_file(temp_destination, timeout=30.0)
                except ValueError as exc:
                    temp_destination.unlink(missing_ok=True)
                    return self.json_response({"error": f"Uploaded file is not valid playable audio: {exc}"}, 400)

                sha256 = file_sha256(temp_destination)
                filename = safe_filename(original_name)
                upload_kind = fields.get("kind", "track").strip().lower()

                if upload_kind == "ad":
                    ad_target = AD_DIR / filename
                    shutil.move(str(temp_destination), str(ad_target))
                    os.chmod(str(ad_target), 0o664)
                    meta = load_ad_meta()
                    ads = meta.setdefault("ads", {})
                    info = ads.setdefault(ad_target.name, {})
                    info.update({"enabled": True, "uploaded_at": int(time.time()), "play_count": info.get("play_count", 0)})
                    save_ad_meta(meta)
                    audit(int(user["id"]), "ad_uploaded", ad_target.name)
                    event_log("advertisement_uploaded", name=ad_target.name, user=user["username"])
                    result = {"ok": True, "ad": {"filename": ad_target.name, "enabled": True}}
                    if upload_id:
                        with DB_LOCK, db_connect() as db:
                            db.execute(
                                "INSERT OR REPLACE INTO upload_receipts(upload_id,user_id,response_json,created_at) VALUES(?,?,?,?)",
                                (upload_id, int(user["id"]), json.dumps(result), int(time.time())),
                            )
                            db.commit()
                    return self.json_response(result)

                title = fields.get("title", temp_destination.stem)
                artist = fields.get("artist", "")
                source_url_value = fields.get("source_url", "")
                rights = fields.get("rights_confirmed", "0") == "1"
                approved = rights and user["role"] in ("admin", "manager")

                # Duplicate detection: check by sha256 or existing active track
                with DB_LOCK, db_connect() as db:
                    existing_asset = db.execute("SELECT track_id FROM audio_assets WHERE sha256=?", (sha256,)).fetchone()
                    existing_track = None
                    if existing_asset and existing_asset["track_id"]:
                        existing_track = db.execute("SELECT * FROM tracks WHERE id=?", (existing_asset["track_id"],)).fetchone()
                    if not existing_track:
                        existing_track = db.execute(
                            "SELECT * FROM tracks WHERE filename=? OR (lower(title)=? AND lower(artist)=? AND artist != '')",
                            (filename, title.lower(), artist.lower())
                        ).fetchone()

                if existing_track:
                    temp_destination.unlink(missing_ok=True)
                    result = {
                        "ok": True,
                        "duplicate": True,
                        "track_id": int(existing_track["id"]),
                        "approved": bool(existing_track["approved"]),
                        "message": f"Track is already in the catalog (ID {existing_track['id']})."
                    }
                    if upload_id:
                        with DB_LOCK, db_connect() as db:
                            db.execute(
                                "INSERT OR REPLACE INTO upload_receipts(upload_id,user_id,response_json,created_at) VALUES(?,?,?,?)",
                                (upload_id, int(user["id"]), json.dumps(result), int(time.time())),
                            )
                            db.commit()
                    return self.json_response(result)

                # Move file to authoritative local storage and mirror to drive if available
                target_local = (FALLBACK_MUSIC_DIR / filename) if FALLBACK_MUSIC_DIR else (MUSIC_DIR / filename)
                target_local.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(temp_destination), str(target_local))
                os.chmod(str(target_local), 0o664)

                if FALLBACK_MUSIC_DIR is not None and primary_music_storage_available() and MUSIC_DIR != target_local.parent:
                    try:
                        shutil.copy2(str(temp_destination), str(MUSIC_DIR / filename))
                    except Exception as drive_exc:
                        event_log("drive_mirror_deferred", filename=filename, error=str(drive_exc))

                temp_destination.unlink(missing_ok=True)

                with DB_LOCK, db_connect() as db:
                    cursor = db.execute(
                        """INSERT INTO tracks(title,artist,filename,source_url,rights_confirmed,approved,enabled,added_by,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (title, artist, filename, source_url_value, int(rights), int(approved), 1, user["id"], int(time.time())),
                    )
                    track_id = cursor.lastrowid
                    db.execute(
                        """INSERT OR REPLACE INTO audio_assets(track_id,sha256,source_path,size_bytes,codec,sample_rate,channels,duration,metadata_confidence,ingested_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (track_id, sha256, str(target_local), probe_info["size_bytes"], probe_info["codec"], probe_info["sample_rate"], probe_info["channels"], probe_info["duration"], "high", int(time.time()))
                    )
                    db.execute(
                        """INSERT INTO ingest_events(source_path,sha256,state,detail,created_at) VALUES(?,?,?,?,?)""",
                        (str(target_local), sha256, "ingested", "Radio DJ Upload", int(time.time()))
                    )
                    if upload_id:
                        db.execute(
                            "INSERT OR REPLACE INTO upload_receipts(upload_id,user_id,response_json,created_at) VALUES(?,?,?,?)",
                            (upload_id, int(user["id"]), json.dumps({"ok": True, "track_id": track_id, "approved": approved}), int(time.time())),
                        )
                    db.commit()

                audit(int(user["id"]), "track_uploaded", filename)
                AUTODJ.library_changed()
                result = {"ok": True, "track_id": track_id, "approved": approved, "sha256": sha256}
                return self.json_response(result)
            if path == "/api/guest-invites":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                data = self.read_json()
                guest_name = str(data.get("guest_name", "Guest DJ")).strip()[:80] or "Guest DJ"
                minutes = max(15, min(1440, int(data.get("expires_minutes", 180))))
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                now = int(time.time())
                with DB_LOCK, db_connect() as db:
                    cursor = db.execute(
                        "INSERT INTO guest_invites(token_hash,guest_name,status,created_by,created_at,expires_at) VALUES(?,?,?,?,?,?)",
                        (token_hash, guest_name, "invited", user["id"], now, now + minutes * 60),
                    )
                    invite_id = int(cursor.lastrowid)
                    db.commit()
                audit(int(user["id"]), "guest_invite_created", f"{invite_id}:{guest_name}")
                link = f"https://ebeinc.online/liveradio/guest/#{token}"
                return self.json_response({"ok": True, "id": invite_id, "link": link, "expires_at": now + minutes * 60})
            if path in ("/api/traktor-invites", "/api/mixxx-invites"):
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                data = self.read_json()
                guest_name = str(data.get("guest_name", "Guest DJ")).strip()[:80] or "Guest DJ"
                minutes = max(15, min(1440, int(data.get("expires_minutes", 180))))
                invite_type = "mixxx" if path == "/api/mixxx-invites" else "traktor"
                password = secrets.token_urlsafe(18)
                credential_hash = hashlib.sha256(password.encode()).hexdigest()
                extension = "mp3" if invite_type == "mixxx" else "ogg"
                mount = f"/guest-{secrets.token_urlsafe(12)}.{extension}"
                now = int(time.time())
                with DB_LOCK, db_connect() as db:
                    cursor = db.execute(
                        "INSERT INTO guest_invites(token_hash,guest_name,status,created_by,created_at,expires_at,invite_type,credential_hash,source_mount) VALUES(?,?,?,?,?,?,?,?,?)",
                        (hashlib.sha256(secrets.token_bytes(32)).hexdigest(), guest_name, "invited", user["id"], now, now + minutes * 60, invite_type, credential_hash, mount),
                    )
                    invite_id = int(cursor.lastrowid)
                    db.commit()
                request_host = self.headers.get("Host", "").split(":", 1)[0].strip()
                configured_host = str(CONFIG.get("traktor_public_host", "")).strip()
                if "://" in configured_host:
                    configured_host = urllib.parse.urlparse(configured_host).hostname or ""
                host = configured_host or request_host or local_ip()
                audit(int(user["id"]), f"{invite_type}_invite_created", f"{invite_id}:{guest_name}")
                return self.json_response({
                    "ok": True, "id": invite_id, "expires_at": now + minutes * 60,
                    "host": host, "port": TRAKTOR_INGEST_PORT, "mount": mount, "password": password,
                    "format": "MP3, 128 kbps, Stereo" if invite_type == "mixxx" else "Ogg Vorbis, 44100 Hz, 128 kBit/s",
                    "login": "source",
                    "invite_type": invite_type,
                })
            if path == "/api/catalog-operations":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                data = self.read_json()
                operation_id = str(data.get("operation_id", "")).strip()
                action = str(data.get("action", "")).strip()
                raw_ids = data.get("track_ids", [])
                if not re.fullmatch(r"[A-Za-z0-9_-]{12,100}", operation_id):
                    return self.json_response({"error": "A durable operation_id is required"}, 400)
                if action != "unlink_catalog_records" or not isinstance(raw_ids, list):
                    return self.json_response({"error": "Only reviewed catalog-record unlink operations are supported"}, 400)
                track_ids = sorted({int(value) for value in raw_ids if str(value).isdigit()})
                if not track_ids or len(track_ids) > 100:
                    return self.json_response({"error": "Choose 1 to 100 reviewed track IDs"}, 400)
                now = int(time.time())
                with DB_LOCK, db_connect() as db:
                    existing = db.execute("SELECT * FROM catalog_operations WHERE operation_id=?", (operation_id,)).fetchone()
                    if existing:
                        items = [dict(row) for row in db.execute("SELECT * FROM catalog_operation_items WHERE operation_id=? ORDER BY track_id", (operation_id,))]
                        return self.json_response({"operation_id": operation_id, "status": existing["status"], "items": items, "idempotent_replay": True})
                    db.execute(
                        "INSERT INTO catalog_operations(operation_id,operation_type,status,requested_by,request_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                        (operation_id, action, "RUNNING", int(user["id"]), json.dumps({"track_ids": track_ids}), now, now),
                    )
                    db.commit()
                results = []
                current_id = int(AUTODJ.snapshot().get("current_track_id") or 0)
                for track_id in track_ids:
                    with DB_LOCK, db_connect() as db:
                        row = db.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
                        if not row:
                            result, detail = "ALREADY_REMOVED", {"physical_file_action": "NONE"}
                        elif track_id == current_id:
                            result, detail = "BLOCKED_UNSAFE", {"reason": "track is currently on air", "physical_file_action": "NONE"}
                        else:
                            record = dict(row)
                            references = int(db.execute("SELECT COUNT(*) FROM tracks WHERE filename=? AND id<>?", (record["filename"], track_id)).fetchone()[0])
                            db.execute("DELETE FROM tracks WHERE id=?", (track_id,))
                            result = "FILE_PRESERVED_SHARED_REFERENCE" if references else "CATALOG_RECORD_REMOVED"
                            detail = {"old_state": record, "physical_file_action": "NONE", "remaining_filename_references": references}
                        db.execute(
                            "INSERT OR REPLACE INTO catalog_operation_items(operation_id,track_id,result,detail_json,updated_at) VALUES(?,?,?,?,?)",
                            (operation_id, track_id, result, json.dumps(detail, default=str), int(time.time())),
                        )
                        db.commit()
                    audit(int(user["id"]), "catalog_operation_item", json.dumps({"operation_id": operation_id, "track_id": track_id, "result": result, **detail}, default=str))
                    results.append({"track_id": track_id, "result": result, "detail": detail})
                with DB_LOCK, db_connect() as db:
                    summary = {"items": results}
                    db.execute("UPDATE catalog_operations SET status='COMPLETED',result_json=?,updated_at=? WHERE operation_id=?", (json.dumps(summary, default=str), int(time.time()), operation_id))
                    db.commit()
                AUTODJ.library_changed()
                return self.json_response({"operation_id": operation_id, "status": "COMPLETED", "items": results})
            if path == "/api/catalog-quarantine":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] != "admin":
                    return self.json_response({"error": "Administrator access required"}, 403)
                data = self.read_json()
                operation_id = str(data.get("operation_id", "")).strip()
                filename = str(data.get("filename", "")).strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]{12,100}", operation_id) or not filename or Path(filename).name != filename:
                    return self.json_response({"error": "Valid operation_id and basename filename required"}, 400)
                with DB_LOCK, db_connect() as db:
                    existing = db.execute("SELECT * FROM quarantine_assets WHERE operation_id=? AND original_path=?", (operation_id, str(MUSIC_DIR / filename))).fetchone()
                    references = int(db.execute("SELECT COUNT(*) FROM tracks WHERE filename=?", (filename,)).fetchone()[0])
                if existing:
                    return self.json_response({"operation_id": operation_id, "result": "FILE_QUARANTINED", "asset": dict(existing), "idempotent_replay": True})
                if references:
                    return self.json_response({"operation_id": operation_id, "result": "BLOCKED_UNSAFE", "reason": f"{references} catalog reference(s) remain"}, 409)
                source = MUSIC_DIR / filename
                if not source.is_file():
                    return self.json_response({"operation_id": operation_id, "result": "NO_ACTION", "reason": "source does not exist"})
                digest, size = file_sha256(source), source.stat().st_size
                destination_dir = QUARANTINE_DIR / time.strftime("%Y-%m-%d", time.gmtime()) / operation_id
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination = destination_dir / filename
                if destination.exists():
                    return self.json_response({"operation_id": operation_id, "result": "BLOCKED_UNSAFE", "reason": "quarantine destination already exists"}, 409)
                shutil.move(str(source), str(destination))
                manifest = {"operation_id": operation_id, "original_path": str(source), "quarantine_path": str(destination), "sha256": digest, "size_bytes": size, "timestamp": int(time.time()), "operator": user["username"]}
                (destination_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                with DB_LOCK, db_connect() as db:
                    db.execute("INSERT INTO quarantine_assets(operation_id,track_id,original_path,quarantine_path,sha256,size_bytes,metadata_json,status,created_at) VALUES(?,NULL,?,?,?,?,?,'QUARANTINED',?)", (operation_id, str(source), str(destination), digest, size, json.dumps(manifest), int(time.time())))
                    db.commit()
                audit(int(user["id"]), "file_quarantined", json.dumps(manifest))
                return self.json_response({"operation_id": operation_id, "result": "FILE_QUARANTINED", "manifest": manifest})
            if path.startswith("/api/catalog-quarantine/") and path.endswith("/restore"):
                user = self.auth_user()
                if not user:
                    return
                if user["role"] != "admin":
                    return self.json_response({"error": "Administrator access required"}, 403)
                operation_id = path.strip("/").split("/")[2]
                with DB_LOCK, db_connect() as db:
                    asset = db.execute("SELECT * FROM quarantine_assets WHERE operation_id=? ORDER BY id DESC LIMIT 1", (operation_id,)).fetchone()
                if not asset:
                    return self.json_response({"error": "Quarantine asset not found"}, 404)
                source, destination = Path(asset["quarantine_path"]), Path(asset["original_path"])
                if asset["status"] == "RESTORED" and destination.is_file():
                    return self.json_response({"operation_id": operation_id, "result": "ALREADY_RESTORED"})
                if destination.exists() or not source.is_file() or file_sha256(source) != asset["sha256"]:
                    return self.json_response({"operation_id": operation_id, "result": "BLOCKED_UNSAFE", "reason": "destination occupied, source missing, or checksum mismatch"}, 409)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                with DB_LOCK, db_connect() as db:
                    db.execute("UPDATE quarantine_assets SET status='RESTORED',restored_at=? WHERE id=?", (int(time.time()), int(asset["id"])))
                    db.commit()
                audit(int(user["id"]), "quarantine_restored", json.dumps({"operation_id": operation_id, "path": str(destination), "sha256": asset["sha256"]}))
                return self.json_response({"operation_id": operation_id, "result": "RESTORED", "path": str(destination)})
            if path.startswith("/api/guest-invites/"):
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                parts = path.strip("/").split("/")
                if len(parts) != 4 or not parts[2].isdigit() or parts[3] not in ("approve", "revoke", "end"):
                    return self.json_response({"error": "Invalid guest action"}, 400)
                invite_id, action = int(parts[2]), parts[3]
                with DB_LOCK, db_connect() as db:
                    invite = db.execute("SELECT * FROM guest_invites WHERE id=?", (invite_id,)).fetchone()
                    if not invite:
                        return self.json_response({"error": "Guest invite not found"}, 404)
                    if action == "approve":
                        if invite["expires_at"] <= int(time.time()):
                            return self.json_response({"error": "Guest invite has expired"}, 400)
                        db.execute("UPDATE guest_invites SET status='approved' WHERE id=?", (invite_id,))
                    else:
                        db.execute("UPDATE guest_invites SET status=? ,ended_at=? WHERE id=?", ("revoked" if action == "revoke" else "ended", int(time.time()), invite_id))
                    db.commit()
                if action in ("revoke", "end"):
                    if GUEST_INGEST.snapshot().get("invite_id") == invite_id:
                        GUEST_INGEST.stop(f"guest_{action}")
                    if SECURE_TRAKTOR_GUEST.invite_id == invite_id:
                        SECURE_TRAKTOR_GUEST.stop(f"traktor_guest_{action}")
                audit(int(user["id"]), f"guest_invite_{action}", str(invite_id))
                return self.json_response({"ok": True, "status": "approved" if action == "approve" else ("revoked" if action == "revoke" else "ended")})
            if path.startswith("/api/tracks/"):
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[3] == "delete" and parts[2].isdigit():
                    return self.json_response({"error": "Legacy destructive delete is disabled. Use a durable reviewed catalog operation; physical audio is preserved."}, 409)
                if len(parts) != 3 or not parts[2].isdigit():
                    return self.json_response({"error": "Invalid track"}, 400)
                track_id = int(parts[2])
                data = self.read_json()
                title = str(data.get("title", "")).strip()[:180]
                artist = str(data.get("artist", "")).strip()[:180]
                source_url_value = str(data.get("source_url", "")).strip()[:1000]
                as_flag = lambda value: value is True or str(value).strip().lower() in ("1", "true", "yes", "on")
                rights = as_flag(data.get("rights_confirmed", False))
                approved = rights and as_flag(data.get("approved", False))
                enabled = as_flag(data.get("enabled", True))
                if not title:
                    return self.json_response({"error": "Track title is required"}, 400)
                with DB_LOCK, db_connect() as db:
                    existing = db.execute("SELECT id FROM tracks WHERE id=?", (track_id,)).fetchone()
                    if not existing:
                        return self.json_response({"error": "Track not found"}, 404)
                    db.execute(
                        "UPDATE tracks SET title=?,artist=?,source_url=?,rights_confirmed=?,approved=?,enabled=? WHERE id=?",
                        (title, artist, source_url_value, int(rights), int(approved), int(enabled), track_id),
                    )
                    db.commit()
                    updated = dict(db.execute(
                        "SELECT id,title,artist,filename,source_url,rights_confirmed,approved,enabled,created_at FROM tracks WHERE id=?",
                        (track_id,),
                    ).fetchone())
                audit(int(user["id"]), "track_updated", str(track_id))
                AUTODJ.track_metadata_changed(updated)
                return self.json_response({"ok": True, "track": updated})
            if path == "/api/ads/settings" or path.startswith("/api/ads/"):
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                if path == "/api/ads/settings":
                    data = self.read_json()
                    interval = max(60, min(3600, int(data.get("interval_seconds", 900))))
                    meta = load_ad_meta()
                    meta["interval_seconds"] = interval
                    save_ad_meta(meta)
                    write_json_config({"ad_interval_seconds": interval})
                    AUTODJ.next_ad_at = time.monotonic() + interval
                    audit(int(user["id"]), "ad_interval_updated", str(interval))
                    event_log("advertisement_interval_updated", seconds=interval, user=user["username"])
                    return self.json_response({"ok": True, "interval_seconds": interval})
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    return self.json_response({"error": "Invalid advertisement action"}, 400)
                filename = safe_filename(urllib.parse.unquote(parts[2]))
                action = parts[3]
                source = AD_DIR / filename
                if not source.exists() or source.suffix.lower() not in AUDIO_EXTENSIONS:
                    return self.json_response({"error": "Advertisement not found"}, 404)
                meta = load_ad_meta()
                ads = meta.setdefault("ads", {})
                info = ads.setdefault(filename, {})
                if action in ("enable", "disable"):
                    info["enabled"] = action == "enable"
                    save_ad_meta(meta)
                    AUTODJ.ad_pool = []
                    audit(int(user["id"]), f"ad_{action}d", filename)
                    event_log("advertisement_state_changed", name=filename, enabled=info["enabled"], user=user["username"])
                    return self.json_response({"ok": True, "filename": filename, "enabled": info["enabled"]})
                if action == "play":
                    if not info.get("enabled", True):
                        return self.json_response({"error": "Enable the advertisement before playing it"}, 400)
                    AUTODJ.request_ad(source)
                    audit(int(user["id"]), "ad_play_now", filename)
                    return self.json_response({"ok": True, "filename": filename})
                if action == "analyze":
                    measurements = measure_loudness(source)
                    info.update(measurements)
                    info["analyzed_at"] = int(time.time())
                    save_ad_meta(meta)
                    event_log("advertisement_analyzed", name=filename, **measurements)
                    return self.json_response({"ok": True, "filename": filename, **measurements})
                if action == "normalize":
                    temporary = source.with_name(f".{source.stem}.normalized-{int(time.time())}.mp3")
                    result = subprocess.run([
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-codec:a", "libmp3lame", "-b:a", "192k", str(temporary),
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=600, check=False)
                    if result.returncode != 0 or not temporary.exists() or temporary.stat().st_size < 1024:
                        temporary.unlink(missing_ok=True)
                        return self.json_response({"error": "Normalization failed", "detail": result.stderr[-500:]}, 500)
                    backup_dir = TRASH_DIR / "ads" / "pre-normalize"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup = backup_dir / f"{int(time.time())}-{filename}"
                    shutil.move(str(source), str(backup))
                    os.replace(temporary, source)
                    measurements = measure_loudness(source)
                    info.update(measurements)
                    info["normalized_at"] = int(time.time())
                    save_ad_meta(meta)
                    event_log("advertisement_normalized", name=filename, backup=backup.name, **measurements)
                    audit(int(user["id"]), "ad_normalized", filename)
                    return self.json_response({"ok": True, "filename": filename, "recoverable_backup": backup.name, **measurements})
                if action == "delete":
                    destination_dir = TRASH_DIR / "ads"
                    destination_dir.mkdir(parents=True, exist_ok=True)
                    destination = destination_dir / f"{int(time.time())}-{filename}"
                    shutil.move(str(source), str(destination))
                    ads.pop(filename, None)
                    save_ad_meta(meta)
                    AUTODJ.ad_pool = []
                    audit(int(user["id"]), "ad_moved_to_trash", filename)
                    event_log("advertisement_moved_to_trash", name=filename, user=user["username"])
                    return self.json_response({"ok": True, "recoverable": destination.name})
                return self.json_response({"error": "Invalid advertisement action"}, 400)
            if path == "/api/alerts/test":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ host access required"}, 403)
                data = self.read_json()
                alert = ALERTS.publish(
                    str(data.get("title", "TEST ALERT")),
                    str(data.get("message", "AllThings140Radio alert system online.")),
                    duration=int(data.get("duration", 7000)),
                    image_url=str(data.get("image_url", "")),
                    audio_url=str(data.get("audio_url", "")),
                    source="operator_test",
                )
                audit(int(user["id"]), "website_test_alert", alert["id"])
                return self.json_response({"ok": True, "alert": alert})
            if path == "/api/reviews":
                user = self.auth_user()
                if not user:
                    return
                data = self.read_json()
                source_url_value = str(data.get("source_url", "")).strip()
                if not source_url_value.startswith(("https://soundcloud.com/", "http://soundcloud.com/")):
                    return self.json_response({"error": "Enter a valid SoundCloud track link"}, 400)
                with DB_LOCK, db_connect() as db:
                    cursor = db.execute(
                        """INSERT INTO review_queue(title,artist,source_url,genre,bpm,artwork_url,status,notes,added_by,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (
                            str(data.get("title", "SoundCloud discovery")).strip() or "SoundCloud discovery",
                            str(data.get("artist", "")).strip(), source_url_value,
                            str(data.get("genre", "")).strip(), data.get("bpm"),
                            str(data.get("artwork_url", "")).strip(), "pending",
                            str(data.get("notes", "")).strip(), user["id"], int(time.time()),
                        ),
                    )
                    review_id = cursor.lastrowid
                    db.commit()
                audit(int(user["id"]), "review_added", source_url_value)
                return self.json_response({"ok": True, "review_id": review_id})
            if path.startswith("/api/reviews/"):
                user = self.auth_user()
                if not user:
                    return
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    return self.json_response({"error": "Invalid review action"}, 400)
                review_id = int(parts[2])
                action = parts[3]
                if action not in ("approve", "reject"):
                    return self.json_response({"error": "Invalid review action"}, 400)
                status = "approved_pending_audio" if action == "approve" else "rejected"
                with DB_LOCK, db_connect() as db:
                    db.execute("UPDATE review_queue SET status=? WHERE id=?", (status, review_id))
                    db.commit()
                audit(int(user["id"]), f"review_{action}", str(review_id))
                return self.json_response({"ok": True, "status": status})
            if path in ("/api/autodj/next", "/api/autodj/previous", "/api/autodj/restart", "/api/autodj/reshuffle", "/api/autodj/play-track"):
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "DJ or administrator access required"}, 403)
                if path.endswith("/next"):
                    AUTODJ.request_next()
                    action = "next"
                elif path.endswith("/previous"):
                    AUTODJ.request_previous()
                    action = "previous"
                elif path.endswith("/restart"):
                    AUTODJ.request_restart()
                    action = "restart"
                elif path.endswith("/reshuffle"):
                    AUTODJ.reshuffle()
                    action = "reshuffle"
                else:
                    data = self.read_json()
                    track_id = int(data.get("track_id", 0))
                    with DB_LOCK, db_connect() as db:
                        exists = db.execute(
                            "SELECT rights_confirmed FROM tracks WHERE id=? AND approved=1 AND enabled=1",
                            (track_id,),
                        ).fetchone()
                    if not exists or not rights_filter_allows(exists):
                        return self.json_response({"error": "That track is not in the approved live catalog"}, 404)
                    AUTODJ.request_track(track_id)
                    action = f"play:{track_id}"
                audit(int(user["id"]), "autodj_control", action)
                return self.json_response({"ok": True, "action": action, "autodj": AUTODJ.snapshot()})
            if path == "/api/broadcast-ended":
                user = self.auth_user()
                if not user:
                    return
                AUTODJ.resume_after_live("dj_app_ended")
                audit(int(user["id"]), "live_broadcast_ended")
                return self.json_response({"ok": True, "autodj": AUTODJ.snapshot()})
            if path == "/api/traktor-ended":
                user = self.auth_user()
                if not user:
                    return
                TRAKTOR_INGEST.stop()
                audit(int(user["id"]), "traktor_broadcast_ended")
                return self.json_response({"ok": True, "autodj": AUTODJ.snapshot()})
            if path == "/api/settings":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] != "admin":
                    return self.json_response({"error": "Administrator access required"}, 403)
                data = self.read_json()
                updated = write_json_config(data)
                if "soundcloud_client_secret" in data:
                    CONFIG["soundcloud_access_token"] = ""
                    CONFIG["soundcloud_token_expires"] = 0
                    CONFIG_PATH.write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
                audit(int(user["id"]), "settings_updated")
                return self.json_response({"ok": True, "station_name": updated["station_name"]})
            if path == "/api/support/settings":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] != "admin":
                    return self.json_response({"error": "Administrator access required"}, 403)
                SUPPORT.update_settings(self.read_json())
                audit(int(user["id"]), "support_settings_updated")
                return self.json_response({"ok": True})
            if path == "/api/support/moderate":
                user = self.auth_user()
                if not user:
                    return
                if user["role"] not in ("admin", "manager"):
                    return self.json_response({"error": "Administrator or manager access required"}, 403)
                data = self.read_json()
                SUPPORT.moderate(int(data.get("id", 0)), data.get("public_visible") is True, data.get("message_visible") is True)
                audit(int(user["id"]), "support_entry_moderated", str(int(data.get("id", 0))))
                return self.json_response({"ok": True})
            return self.json_response({"error": "Not found"}, 404)
        except SupportError as exc:
            return self.json_response({"error": str(exc)}, exc.status)
        except (ValueError, json.JSONDecodeError) as exc:
            return self.json_response({"error": str(exc)}, 400)
        except Exception as exc:
            traceback.print_exc()
            return self.json_response({"error": str(exc)}, 500)

    def listener_page(self) -> None:
        name = html.escape(str(CONFIG.get("station_name", APP_NAME)))
        desc = html.escape(str(CONFIG.get("station_description", "")))
        stream = html.escape(stream_url(self), quote=True)
        website = html.escape(str(CONFIG.get("website_url", "")), quote=True)
        website_link = f'<a class="site" href="{website}">Open the full listener site</a>' if website else ""
        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>
:root{{--bg:#07060a;--panel:#15101e;--accent:#b76bff;--text:#faf7ff;--muted:#b9aec6}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at top,#2f1450,var(--bg) 58%);font:16px system-ui;color:var(--text)}}
.card{{width:min(700px,92vw);padding:40px;border:1px solid #49325f;border-radius:28px;background:linear-gradient(160deg,#1d142bde,#0d0a12f5);box-shadow:0 30px 90px #0009}}
.badge{{display:inline-block;padding:7px 12px;border-radius:99px;background:#b466ff24;border:1px solid #b466ff66;color:#dfc5ff;font-weight:800;letter-spacing:.08em}}
h1{{font-size:clamp(36px,7vw,66px);line-height:.95;margin:22px 0 14px}}p{{color:var(--muted);line-height:1.6}}audio{{width:100%;margin:26px 0}}.site{{display:inline-flex;padding:12px 16px;border-radius:12px;background:#a94fff;color:white;text-decoration:none;font-weight:800}}.foot{{font-size:13px;color:#8f829d}}
</style></head><body><main class="card"><span class="badge">LIVE 24/7</span><h1>{name}</h1><p>{desc}</p>
<audio controls preload="none" src="{stream}"></audio>{website_link}<p class="foot">When a DJ disconnects, the approved AutoDJ rotation resumes automatically.</p></main></body></html>"""
        self.text_response(body)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 128

    def __init__(self, *args: Any, max_request_threads: int = 64, **kwargs: Any) -> None:
        # ThreadingHTTPServer is otherwise unbounded: every accepted connection
        # creates a new thread.  A slow-client/request pileup must never consume
        # the process resources used by the AutoDJ playback thread.
        self._request_slots = threading.BoundedSemaphore(max_request_threads)
        super().__init__(*args, **kwargs)

    def process_request(self, request: socket.socket, client_address: Any) -> None:
        if not self._request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._request_slots.release()
            raise

    def process_request_thread(self, request: socket.socket, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()


def shutdown_handler(signum: int, frame: Any) -> None:
    SHUTDOWN.set()
    # Exit the blocking serve_forever loop immediately. The main() finally
    # block owns orderly FFmpeg and HTTP cleanup.
    raise SystemExit(0)


def catalog_integrity_monitor() -> None:
    """Run storage checks off the playback thread; never mutate or delete assets."""
    while not SHUTDOWN.wait(30):
        started = time.monotonic()
        try:
            report = catalog_integrity_snapshot(False)
            event_log("catalog_integrity_scan", health=report["health"], duration_seconds=round(time.monotonic() - started, 2), **report["counts"])
        except Exception as exc:
            event_log("catalog_integrity_scan_failed", error=str(exc))
        if SHUTDOWN.wait(900):
            return


def main() -> None:
    ensure_dirs()
    init_db()
    SUPPORT.init_schema()
    SUBSCRIPTIONS.init_schema()
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # The private LAN API is the critical service. Bind it first so a temporary
    # public-gateway conflict can never prevent DJ logins or LAN discovery.
    httpd = ReusableThreadingHTTPServer((HOST, PORT), Handler)
    print(f"{APP_NAME} private server listening on {HOST}:{PORT}", flush=True)

    traktor_httpd = ReusableThreadingHTTPServer((HOST, TRAKTOR_INGEST_PORT), TraktorGuestSourceHandler)
    threading.Thread(target=traktor_httpd.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True, name="TraktorGuestGateway").start()
    print(f"{APP_NAME} secure Traktor ingest listening on {HOST}:{TRAKTOR_INGEST_PORT}", flush=True)

    AUTODJ.start()
    AI_PRODUCER.start()
    LiveHandoffWatchdog(daemon=True, name="LiveHandoffWatchdog").start()
    GuestIngestWatchdog(daemon=True, name="GuestIngestWatchdog").start()
    STATION_WATCHDOG.start()
    SILENCE_MONITOR.start()
    threading.Thread(target=catalog_integrity_monitor, daemon=True, name="CatalogIntegrityMonitor").start()
    DiscoveryResponder(daemon=True, name="LANDiscovery").start()
    event_log("server_started", version=VERSION)

    public_httpd = None
    try:
        public_httpd = ReusableThreadingHTTPServer(("127.0.0.1", PUBLIC_GATEWAY_PORT), PublicGatewayHandler)
        public_thread = threading.Thread(
            target=public_httpd.serve_forever,
            kwargs={"poll_interval": 0.5},
            daemon=True,
            name="PublicGateway",
        )
        public_thread.start()
        print(f"{APP_NAME} public-only gateway listening on 127.0.0.1:{PUBLIC_GATEWAY_PORT}", flush=True)
    except OSError as exc:
        # Keep the actual radio/DJ server online. The manager can repair or
        # restart the optional public relay separately.
        print(f"WARNING: public gateway unavailable on 127.0.0.1:{PUBLIC_GATEWAY_PORT}: {exc}", file=sys.stderr, flush=True)

    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        SHUTDOWN.set()
        SECURE_TRAKTOR_GUEST.stop("server_shutdown")
        traktor_httpd.shutdown()
        traktor_httpd.server_close()
        TRAKTOR_INGEST.stop()
        GUEST_INGEST.stop("server_shutdown")
        AUTODJ.stop_process()
        if public_httpd is not None:
            public_httpd.shutdown()
            public_httpd.server_close()
        httpd.server_close()


if __name__ == "__main__":
    main()
