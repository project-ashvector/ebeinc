#!/usr/bin/env python3
"""Non-critical production extensions for AllThings140Radio.

Archive recording, waveform processing, alert queuing, and notification hooks
live here so failures cannot take down the AutoDJ audio loop.
"""
from __future__ import annotations

import array
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import urllib.request
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Callable


def _safe_slug(value: str, fallback: str = "guest-dj") -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value).strip()).strip("-.")
    return (value[:72] or fallback).lower()


class LocalArchiveStorage:
    """Durable local provider; remote providers can implement the same methods."""

    name = "local"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.audio = root / "audio"
        self.waveforms = root / "waveforms"
        self.trash = root / "trash"
        for path in (self.root, self.audio, self.waveforms, self.trash):
            path.mkdir(parents=True, exist_ok=True)

    def audio_path(self, archive_id: str, host: str) -> Path:
        return self.audio / f"{archive_id}-{_safe_slug(host)}.mp3"

    def waveform_path(self, archive_id: str) -> Path:
        return self.waveforms / f"{archive_id}.json"


class ArchiveManager:
    """Records only intentional live handoffs and indexes finalized replays."""

    def __init__(
        self,
        db_path: Path,
        data_root: Path,
        stream_url: Callable[[], str],
        event_log: Callable[..., None],
        storage_provider: str = "local",
    ) -> None:
        self.db_path = db_path
        self.storage = LocalArchiveStorage(data_root / "archives")
        self.remote_endpoint = os.environ.get("ALLTHINGS140_ARCHIVE_REMOTE_ENDPOINT", "https://archives.ebeinc.online").rstrip("/")
        token_path = Path(os.environ.get("ALLTHINGS140_ARCHIVE_TOKEN_FILE", "/etc/allthings140radio/archive-upload-token"))
        try:
            self.remote_token = token_path.read_text(encoding="utf-8").strip()
        except OSError:
            self.remote_token = ""
        self.storage_provider = "r2" if storage_provider == "r2" and self.remote_endpoint and self.remote_token else "local"
        self.stream_url = stream_url
        self.event_log = event_log
        self.lock = threading.RLock()
        self.process: subprocess.Popen[bytes] | None = None
        self.active_id = ""
        self.active_path: Path | None = None
        self.active_started = 0
        self._init_db()
        self._recover_interrupted()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _init_db(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS archives (
                    archive_id TEXT PRIMARY KEY,
                    host TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    started_at INTEGER NOT NULL,
                    ended_at INTEGER NOT NULL DEFAULT 0,
                    duration REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL,
                    audio_filename TEXT NOT NULL DEFAULT '',
                    waveform_filename TEXT NOT NULL DEFAULT '',
                    replay_url TEXT NOT NULL DEFAULT '',
                    waveform_url TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    public INTEGER NOT NULL DEFAULT 1,
                    recording_error TEXT NOT NULL DEFAULT '',
                    waveform_error TEXT NOT NULL DEFAULT '',
                    storage_provider TEXT NOT NULL DEFAULT 'local',
                    remote_status TEXT NOT NULL DEFAULT 'local',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS archives_public_started ON archives(public,status,started_at DESC)")
            db.commit()

    def _recover_interrupted(self) -> None:
        now = int(time.time())
        with self._connect() as db:
            db.execute(
                "UPDATE archives SET status='interrupted',ended_at=CASE WHEN ended_at=0 THEN ? ELSE ended_at END,updated_at=? WHERE status='recording'",
                (now, now),
            )
            db.commit()

    def start(self, host: str = "Guest DJ", title: str = "Live takeover", source: str = "live") -> str:
        with self.lock:
            if self.process and self.process.poll() is None:
                return self.active_id
            host = str(host).strip()[:100] or "Guest DJ"
            title = str(title).strip()[:180] or f"{host} Live Takeover"
            source = str(source).strip()[:80] or "live"
            archive_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
            final_path = self.storage.audio_path(archive_id, host)
            partial_path = final_path.with_suffix(".partial.mp3")
            started = int(time.time())
            with self._connect() as db:
                db.execute(
                    """INSERT INTO archives(archive_id,host,title,started_at,source,audio_filename,status,public,storage_provider,created_at,updated_at)
                       VALUES(?,?,?,?,?,?, 'recording',1,?,?,?)""",
                    (archive_id, host, title, started, source, final_path.name, self.storage_provider, started, started),
                )
                db.commit()
            try:
                process = subprocess.Popen([
                    "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
                    "-i", self.stream_url(), "-vn", "-codec:a", "libmp3lame", "-b:a", "192k",
                    "-f", "mp3", str(partial_path),
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as exc:
                with self._connect() as db:
                    db.execute("UPDATE archives SET status='recording_failed',recording_error=?,updated_at=? WHERE archive_id=?", (str(exc)[:1000], int(time.time()), archive_id))
                    db.commit()
                self.event_log("takeover_recording_failed", archive_id=archive_id, error=str(exc))
                return archive_id
            self.process = process
            self.active_id = archive_id
            self.active_path = partial_path
            self.active_started = started
            self.event_log("takeover_recording_started", archive_id=archive_id, host=host, source=source)
            return archive_id

    def stop(self, reason: str = "live_ended") -> None:
        with self.lock:
            process, archive_id, partial_path, started = self.process, self.active_id, self.active_path, self.active_started
            self.process = None
            self.active_id = ""
            self.active_path = None
            self.active_started = 0
        if not archive_id:
            return
        error = ""
        if process and process.poll() is None:
            process.send_signal(getattr(__import__('signal'), 'SIGINT'))
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    error = "FFmpeg did not finalize before timeout"
        ended = int(time.time())
        final_path = partial_path.with_name(partial_path.name.replace(".partial.mp3", ".mp3")) if partial_path else None
        if partial_path and partial_path.exists() and partial_path.stat().st_size > 4096 and final_path:
            os.replace(partial_path, final_path)
            status = "processing"
        else:
            status = "recording_failed"
            error = error or "Recording output was empty or unavailable"
        with self._connect() as db:
            db.execute(
                "UPDATE archives SET ended_at=?,duration=?,status=?,recording_error=?,updated_at=? WHERE archive_id=?",
                (ended, max(0, ended - started), status, error[:1000], ended, archive_id),
            )
            db.commit()
        self.event_log("takeover_recording_ended", archive_id=archive_id, reason=reason, status=status)
        if status == "processing" and final_path:
            threading.Thread(target=self._postprocess, args=(archive_id, final_path), daemon=True, name=f"Archive-{archive_id}").start()

    def _postprocess(self, archive_id: str, audio_path: Path) -> None:
        waveform_path = self.storage.waveform_path(archive_id)
        error = ""
        try:
            proc = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(audio_path),
                "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, check=True)
            samples = array.array("h")
            samples.frombytes(proc.stdout)
            buckets = 720
            width = max(1, len(samples) // buckets)
            peaks = []
            for offset in range(0, len(samples), width):
                block = samples[offset:offset + width]
                peaks.append(round(max((abs(value) for value in block), default=0) / 32768, 4))
                if len(peaks) >= buckets:
                    break
            temporary = waveform_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps({"version": 1, "peaks": peaks}), encoding="utf-8")
            os.replace(temporary, waveform_path)
            status = "published"
        except Exception as exc:
            error = str(exc)[:1000]
            status = "waveform_failed"
        replay_url = f"/api/public/archive/{archive_id}/audio"
        waveform_url = f"/api/public/archive/{archive_id}/waveform" if waveform_path.exists() else ""
        remote_status = "local"
        if self.storage_provider == "r2":
            try:
                replay_url = self._upload_remote(f"audio/{audio_path.name}", audio_path, "audio/mpeg")
                if waveform_path.exists():
                    waveform_url = self._upload_remote(f"waveforms/{waveform_path.name}", waveform_path, "application/json")
                remote_status = "uploaded"
            except Exception as exc:
                remote_status = f"failed: {str(exc)[:180]}"
                self.event_log("archive_remote_upload_failed", archive_id=archive_id, error=str(exc))
        with self._connect() as db:
            db.execute(
                """UPDATE archives SET waveform_filename=?,replay_url=?,waveform_url=?,status=?,waveform_error=?,storage_provider=?,remote_status=?,updated_at=? WHERE archive_id=?""",
                (waveform_path.name if waveform_path.exists() else "", replay_url, waveform_url, status, error, self.storage_provider, remote_status, int(time.time()), archive_id),
            )
            db.commit()
        self.event_log("archive_processed", archive_id=archive_id, status=status, error=error, remote_status=remote_status)

    def _upload_remote(self, key: str, path: Path, content_type: str) -> str:
        url = f"{self.remote_endpoint}/objects/{key}"
        request = urllib.request.Request(url, data=path.read_bytes(), method="PUT", headers={
            "Authorization": f"Bearer {self.remote_token}",
            "Content-Type": content_type,
            "Content-Length": str(path.stat().st_size),
        })
        with urllib.request.urlopen(request, timeout=1800) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"remote archive upload returned HTTP {response.status}")
        return url

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            running = bool(self.process and self.process.poll() is None)
            return {"recording": running, "archive_id": self.active_id, "started_at": self.active_started, "storage": self.storage_provider}

    def list_public(self, limit: int = 20, offset: int = 0, host: str = "", search: str = "") -> dict[str, Any]:
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
        clauses = ["public=1", "status IN ('published','waveform_failed')"]
        values: list[Any] = []
        if host:
            clauses.append("host LIKE ?")
            values.append(f"%{host[:100]}%")
        if search:
            clauses.append("(title LIKE ? OR host LIKE ? OR description LIKE ?)")
            term = f"%{search[:100]}%"
            values.extend((term, term, term))
        where = " AND ".join(clauses)
        with self._connect() as db:
            total = int(db.execute(f"SELECT COUNT(*) FROM archives WHERE {where}", values).fetchone()[0])
            rows = db.execute(
                f"""SELECT archive_id,host,title,description,started_at,ended_at,duration,source,replay_url,waveform_url,status
                    FROM archives WHERE {where} ORDER BY started_at DESC LIMIT ? OFFSET ?""",
                (*values, limit, offset),
            ).fetchall()
        return {"archives": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def list_all(self, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(500, int(limit)))
        with self._connect() as db:
            total = int(db.execute("SELECT COUNT(*) FROM archives").fetchone()[0])
            rows = db.execute(
                """SELECT archive_id,host,title,description,started_at,ended_at,duration,source,replay_url,waveform_url,status,public,recording_error,waveform_error,storage_provider,remote_status
                   FROM archives ORDER BY started_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return {"archives": [dict(row) for row in rows], "total": total, "limit": limit}

    def public_item(self, archive_id: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"[a-zA-Z0-9-]{8,80}", archive_id):
            return None
        with self._connect() as db:
            row = db.execute(
                """SELECT archive_id,host,title,description,started_at,ended_at,duration,source,replay_url,waveform_url,status
                   FROM archives WHERE archive_id=? AND public=1 AND status IN ('published','waveform_failed')""",
                (archive_id,),
            ).fetchone()
        return dict(row) if row else None

    def public_file(self, archive_id: str, kind: str) -> tuple[Path, str] | None:
        item = self.public_item(archive_id)
        if not item:
            return None
        with self._connect() as db:
            row = db.execute("SELECT audio_filename,waveform_filename FROM archives WHERE archive_id=?", (archive_id,)).fetchone()
        if not row:
            return None
        if kind == "audio":
            path, mime = self.storage.audio / str(row["audio_filename"]), "audio/mpeg"
        elif kind == "waveform":
            path, mime = self.storage.waveforms / str(row["waveform_filename"]), "application/json; charset=utf-8"
        else:
            return None
        try:
            path.resolve().relative_to(self.storage.root.resolve())
        except ValueError:
            return None
        return (path, mime) if path.is_file() else None


class AlertBus:
    """Small in-memory public alert queue; third-party bridges remain external."""

    def __init__(self, event_log: Callable[..., None]) -> None:
        self.event_log = event_log
        self.lock = threading.RLock()
        self.items: deque[dict[str, Any]] = deque(maxlen=50)

    def publish(self, title: str, message: str, *, duration: int = 7000, image_url: str = "", audio_url: str = "", source: str = "internal") -> dict[str, Any]:
        item = {
            "id": f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}",
            "title": str(title).strip()[:100] or "ALLTHINGS140 RADIO",
            "message": str(message).strip()[:280],
            "duration": max(2000, min(20000, int(duration))),
            "image_url": str(image_url).strip()[:500] if str(image_url).startswith(("https://", "/")) else "",
            "audio_url": str(audio_url).strip()[:500] if str(audio_url).startswith(("https://", "/")) else "",
            "source": str(source).strip()[:40] or "internal",
            "created_at": int(time.time()),
        }
        with self.lock:
            self.items.append(item)
        self.event_log("website_alert_queued", alert_id=item["id"], source=item["source"])
        return item

    def since(self, created_after: int = 0) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(item) for item in self.items if int(item["created_at"]) >= int(created_after)]


class FailureNotifier:
    """Optional cooldown/deduplicated Discord-compatible webhook notifier."""

    def __init__(self, event_log: Callable[..., None], webhook_url: str = "", cooldown: int = 900) -> None:
        self.event_log = event_log
        self.webhook_url = webhook_url.strip()
        self.cooldown = max(60, int(cooldown))
        self.lock = threading.RLock()
        self.last_sent: dict[str, float] = {}

    def notify(self, key: str, title: str, detail: str) -> bool:
        now = time.time()
        with self.lock:
            if now - self.last_sent.get(key, 0) < self.cooldown:
                return False
            self.last_sent[key] = now
        if not self.webhook_url.startswith("https://"):
            self.event_log("failure_notification_skipped", key=key, reason="webhook_not_configured")
            return False
        payload = json.dumps({"content": f"**{str(title)[:160]}**\n{str(detail)[:1500]}"}).encode()
        def worker() -> None:
            try:
                request = urllib.request.Request(self.webhook_url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "AllThings140Radio/1.0"}, method="POST")
                with urllib.request.urlopen(request, timeout=8) as response:
                    response.read(1024)
                self.event_log("failure_notification_sent", key=key)
            except Exception as exc:
                self.event_log("failure_notification_failed", key=key, error=str(exc))
        threading.Thread(target=worker, daemon=True, name="FailureNotifier").start()
        return True
