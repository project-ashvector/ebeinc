"""ALLTHINGS140 Hub — truthful health and diagnostics service.

No endpoint is considered healthy merely because an HTTP request returned 200.
The service never invents catalog/cache/server state. Callers should execute
``run_check`` off the GUI thread.
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import HEALTH_HISTORY_FILE, PROJECT_ROOT, get_config
from hub.util.atomic_io import atomic_write_json


@dataclass
class EndpointCheckResult:
    name: str
    target: str
    is_healthy: bool
    status_code: Optional[int]
    response_time_ms: float
    detail: str
    error: str = ""


@dataclass
class StationHealthSnapshot:
    timestamp: float
    overall_status: str = "unknown"
    station_name: str = "AllThings140Radio"
    authority_status_verified: bool = False
    online: bool = False
    mode: str = "unknown"
    live: bool = False
    live_host: str = ""
    current_title: str = ""
    current_artist: str = ""
    listeners: int = 0
    approved_tracks: int = 0
    catalog_health: str = "unknown"
    cache_status: str = "unknown"
    cache_tracks_ready: int = 0
    cache_minutes_ready: float = 0.0
    stream_status: str = "unknown"
    website_status: str = "unknown"
    website_latency_ms: float = 0.0
    vm1_reachable: bool = False
    vm2_reachable: bool = False
    realtime_online: bool = False
    checks: List[EndpointCheckResult] = field(default_factory=list)
    recent_alerts: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return self.overall_status


class HealthService:
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            try:
                project_root = Path(get_config().current_project_path).expanduser().resolve()
            except Exception:
                project_root = PROJECT_ROOT
        self.project_root = project_root
        self._last_snapshot: Optional[StationHealthSnapshot] = None
        self._history: List[Dict[str, Any]] = []
        self._load_history()

    # Kept for API compatibility; MainWindow owns Qt-safe fanout.
    def subscribe(self, callback) -> None:
        return None

    def get_last_snapshot(self) -> StationHealthSnapshot:
        return self._last_snapshot or StationHealthSnapshot(timestamp=time.time())

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def run_check(self) -> StationHealthSnapshot:
        now = time.time()
        checks: List[EndpointCheckResult] = []

        status_data: Dict[str, Any] = {}
        status_check = self._check_http_json(
            "https://status.ebeinc.online/api/public/status", "Status API", timeout=3.0
        )
        checks.append(status_check)
        if status_check.status_code == 200:
            try:
                parsed = json.loads(status_check.detail)
                if isinstance(parsed, dict):
                    status_data = parsed
                    # Respect semantic status from payload if present.
                    if "online" in parsed:
                        status_check.is_healthy = bool(parsed.get("online"))
            except (ValueError, TypeError) as exc:
                status_check.is_healthy = False
                status_check.error = f"Invalid JSON: {exc}"

        stream_check = self._check_stream_audio(
            "https://stream.ebeinc.online/live.mp3", "Live Audio Stream", timeout=3.5
        )
        checks.append(stream_check)

        website_check = self._check_http(
            "https://allthings140radio.online", "Website (Cloudflare Pages)", timeout=3.0
        )
        checks.append(website_check)

        realtime_check = self._check_http_json(
            "https://visuals-realtime-staging.allthings140radio.online/health",
            "Visuals Realtime Server", timeout=3.0
        )
        checks.append(realtime_check)
        if realtime_check.status_code == 200:
            try:
                rdata = json.loads(realtime_check.detail)
                if isinstance(rdata, dict):
                    semantic = rdata.get("online", rdata.get("ok", rdata.get("healthy", True)))
                    realtime_check.is_healthy = bool(semantic)
            except (ValueError, TypeError):
                realtime_check.is_healthy = False

        green_check = self._check_http(
            "https://allthings140-visuals-green.pages.dev", "Green Web Stage", timeout=3.0
        )
        checks.append(green_check)

        # VM1 private API: localhost is not proof of VM reachability. Prefer Tailscale host.
        private_check = self._check_http_json(
            "http://allthings140radio-server:14080/api/health",
            "Private Server API (Tailscale)", timeout=2.0
        )
        checks.append(private_check)

        vm1_ping = self._check_tailscale_ping("allthings140radio-server", "VM1 Tailscale Reachability")
        vm2_ping = self._check_tailscale_ping("allthings140-visuals-realtime", "VM2 Tailscale Reachability")
        checks.extend([vm1_ping, vm2_ping])

        is_online = bool(status_data.get("online", False))
        mode = str(status_data.get("mode") or "unknown")
        is_live = bool(status_data.get("live", False))
        live_host = str(status_data.get("live_host") or "")
        current_title = str(status_data.get("current_title") or "")
        current_artist = str(status_data.get("current_artist") or "")
        listeners = self._safe_int(status_data.get("listeners"), 0)
        approved_tracks = self._safe_int(status_data.get("approved_tracks"), 0)

        raw_catalog = str(status_data.get("catalog_health") or "unknown").lower()
        catalog_health = raw_catalog if raw_catalog in {"healthy", "warning", "critical", "unknown"} else "unknown"

        cache_info = status_data.get("cache") if isinstance(status_data.get("cache"), dict) else {}
        raw_cache = str(cache_info.get("status") or "unknown").lower()
        cache_status = raw_cache if raw_cache in {"healthy", "warning", "critical", "unknown"} else "unknown"
        cache_tracks_ready = self._safe_int(cache_info.get("tracks_ready"), 0)
        cache_minutes_ready = self._safe_float(cache_info.get("minutes_ready"), 0.0)

        stream_online = stream_check.is_healthy
        realtime_online = realtime_check.is_healthy

        # Only call the overall station healthy when the two core broadcast proofs agree.
        core_known = status_check.status_code is not None or stream_check.status_code is not None
        if not core_known:
            overall = "unknown"
        elif not stream_online and not is_online:
            overall = "critical"
        elif not stream_online or not is_online:
            overall = "warning"
        elif not website_check.is_healthy or not realtime_online:
            overall = "warning"
        else:
            overall = "healthy"

        alerts: List[str] = []
        for check in checks:
            if not check.is_healthy:
                alerts.append(f"{check.name}: {check.error or check.detail}")

        snapshot = StationHealthSnapshot(
            timestamp=now,
            overall_status=overall,
            authority_status_verified=bool(status_data) and status_check.status_code == 200 and not status_check.error,
            online=is_online,
            mode=mode,
            live=is_live,
            live_host=live_host,
            current_title=current_title,
            current_artist=current_artist,
            listeners=listeners,
            approved_tracks=approved_tracks,
            catalog_health=catalog_health,
            cache_status=cache_status,
            cache_tracks_ready=cache_tracks_ready,
            cache_minutes_ready=cache_minutes_ready,
            stream_status="online" if stream_online else ("offline" if stream_check.status_code is not None or stream_check.error else "unknown"),
            website_status="online" if website_check.is_healthy else ("offline" if website_check.error else "unknown"),
            website_latency_ms=website_check.response_time_ms,
            vm1_reachable=vm1_ping.is_healthy,
            vm2_reachable=vm2_ping.is_healthy,
            realtime_online=realtime_online,
            checks=checks,
            recent_alerts=alerts[:8],
        )
        self._last_snapshot = snapshot
        self._record_history(snapshot)
        return snapshot

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _check_http(self, url: str, name: str, timeout: float = 3.0) -> EndpointCheckResult:
        start = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ALLTHINGS140-Hub/1.2.1"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = (time.time() - start) * 1000.0
                return EndpointCheckResult(name, url, resp.status in (200, 204), resp.status, round(elapsed, 1), f"HTTP {resp.status}")
        except Exception as exc:
            return EndpointCheckResult(name, url, False, getattr(exc, "code", None), round((time.time()-start)*1000.0, 1), "Connection failed", str(exc))

    def _check_http_json(self, url: str, name: str, timeout: float = 3.0) -> EndpointCheckResult:
        start = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ALLTHINGS140-Hub/1.2.1", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(262144).decode("utf-8", errors="replace")
                elapsed = (time.time() - start) * 1000.0
                healthy = resp.status == 200
                try:
                    json.loads(body)
                except ValueError:
                    healthy = False
                return EndpointCheckResult(name, url, healthy, resp.status, round(elapsed, 1), body[:4096])
        except Exception as exc:
            return EndpointCheckResult(name, url, False, getattr(exc, "code", None), round((time.time()-start)*1000.0, 1), "{}", str(exc))

    def _check_stream_audio(self, url: str, name: str, timeout: float = 3.5) -> EndpointCheckResult:
        start = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ALLTHINGS140-Hub/1.2.1", "Range": "bytes=0-4095"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                chunk = resp.read(4096)
                elapsed = (time.time() - start) * 1000.0
                ok = resp.status in (200, 206) and len(chunk) >= 256
                return EndpointCheckResult(name, url, ok, resp.status, round(elapsed, 1), f"Received {len(chunk)} stream bytes")
        except Exception as exc:
            return EndpointCheckResult(name, url, False, getattr(exc, "code", None), round((time.time()-start)*1000.0, 1), "Stream unreachable", str(exc))

    def _check_tailscale_ping(self, host: str, name: str) -> EndpointCheckResult:
        start = time.time()
        try:
            res = subprocess.run(["tailscale", "ping", "--c=1", "--timeout=2s", host], capture_output=True, text=True, timeout=3.0)
            elapsed = (time.time()-start)*1000.0
            detail = (res.stdout or res.stderr or "").strip()[:300]
            return EndpointCheckResult(name, host, res.returncode == 0, None, round(elapsed, 1), detail or f"exit {res.returncode}")
        except FileNotFoundError:
            return EndpointCheckResult(name, host, False, None, round((time.time()-start)*1000.0, 1), "Tailscale CLI not installed", "tailscale executable not found")
        except Exception as exc:
            return EndpointCheckResult(name, host, False, None, round((time.time()-start)*1000.0, 1), "Tailscale ping failed", str(exc))

    def _load_history(self) -> None:
        if HEALTH_HISTORY_FILE.exists():
            try:
                data = json.loads(HEALTH_HISTORY_FILE.read_text(encoding="utf-8"))
                self._history = data if isinstance(data, list) else []
            except Exception:
                self._history = []

    def _record_history(self, snapshot: StationHealthSnapshot) -> None:
        self._history.append({
            "timestamp": snapshot.timestamp,
            "overall": snapshot.overall_status,
            "online": snapshot.online,
            "track": f"{snapshot.current_artist} - {snapshot.current_title}" if snapshot.current_title else "None",
            "listeners": snapshot.listeners,
            "stream": snapshot.stream_status,
        })
        self._history = self._history[-200:]
        try:
            atomic_write_json(HEALTH_HISTORY_FILE, self._history)
        except OSError:
            # History failure must never change station health or crash the Hub.
            pass
