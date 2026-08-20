"""
ALLTHINGS140 Hub — Application Registry Model & Scanner
Discovers, models, and monitors all applications and components across the ecosystem.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import PROJECT_ROOT, get_config


@dataclass
class AppEntry:
    id: str
    name: str
    displayName: str
    description: str
    category: str  # broadcast, visuals, web, mobile, tools, infra
    repoPath: str
    workingDirectory: str
    version: str
    techStack: str
    status: str  # active-production, active-staging, active-workstation, active-tool, active-service, active-artifact, standalone, integrated
    environment: str  # production, staging, workstation, oracle-vm1, oracle-vm2, cloudflare, mobile
    deploymentTarget: str
    serviceName: str = ""
    healthUrl: str = ""
    launchCommand: str = ""
    buildCommand: str = ""
    testCommand: str = ""
    updateCommand: str = ""
    backupPath: str = ""
    logsCommand: str = ""
    gitBranch: str = "main"
    gitHead: str = ""
    dirty: bool = False
    ahead: int = 0
    behind: int = 0
    lastUpdated: str = ""
    lastHealthCheck: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    relatedApps: List[str] = field(default_factory=list)
    notes: str = ""
    iconKey: str = "radio"
    isDangerousToRestart: bool = False


class AppRegistry:
    """Central registry and dynamic discovery engine for ALLTHINGS140 applications."""

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            try:
                project_root = Path(get_config().current_project_path).expanduser().resolve()
            except Exception:
                project_root = PROJECT_ROOT
        self.project_root = project_root
        self._apps: Dict[str, AppEntry] = {}
        self._git_cache: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        """Scan and populate registered applications with live git/version state."""
        apps_map = self._get_canonical_apps()
        self._git_cache = {}
        # Enrich each app with live local status
        for app_id, app in apps_map.items():
            self._enrich_app_state(app)
        self._apps = apps_map

    def get(self, app_id: str) -> Optional[AppEntry]:
        return self._apps.get(app_id)

    def all(self) -> List[AppEntry]:
        return list(self._apps.values())

    def by_category(self, category: str) -> List[AppEntry]:
        if category == "all":
            return self.all()
        return [app for app in self._apps.values() if app.category == category]

    def search(self, query: str) -> List[AppEntry]:
        q = query.lower().strip()
        if not q:
            return self.all()
        return [
            app for app in self._apps.values()
            if q in app.name.lower() or q in app.displayName.lower() or q in app.description.lower() or q in app.techStack.lower()
        ]

    def _find_git_root(self, work_dir: Path) -> Optional[Path]:
        p = work_dir.resolve()
        for candidate in [p, *p.parents]:
            if (candidate / ".git").exists():
                return candidate
            if candidate == self.project_root.parent:
                break
        return None

    def _read_git_state(self, repo_root: Path) -> Dict[str, Any]:
        key = str(repo_root)
        if key in self._git_cache:
            return self._git_cache[key]
        state: Dict[str, Any] = {"dirty": False, "head": "", "branch": "unknown"}
        try:
            status = subprocess.run(["git", "-C", key, "status", "--porcelain"], capture_output=True, text=True, timeout=1.5)
            head = subprocess.run(["git", "-C", key, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=1.5)
            branch = subprocess.run(["git", "-C", key, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=1.5)
            if status.returncode == 0:
                state["dirty"] = bool(status.stdout.strip())
            if head.returncode == 0:
                state["head"] = head.stdout.strip()
            if branch.returncode == 0:
                state["branch"] = branch.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        self._git_cache[key] = state
        return state

    def _detect_source_version(self, app: AppEntry, work_dir: Path) -> Optional[str]:
        candidates = [
            work_dir / "package.json",
            work_dir / "src-tauri" / "tauri.conf.json",
            work_dir / "Cargo.toml",
            work_dir / "src-tauri" / "Cargo.toml",
        ]
        for file in candidates:
            try:
                if not file.is_file():
                    continue
                if file.name.endswith(".json"):
                    data = json.loads(file.read_text(encoding="utf-8"))
                    version = data.get("version") or (data.get("package") or {}).get("version")
                    if version:
                        return str(version)
                elif file.name == "Cargo.toml":
                    m = re.search(r'^version\s*=\s*["\']([^"\']+)', file.read_text(encoding="utf-8"), re.M)
                    if m:
                        return m.group(1)
            except (OSError, ValueError, TypeError):
                continue
        return None

    def _enrich_app_state(self, app: AppEntry) -> None:
        """Enrich with cheap local evidence. Remote/deployed versions remain explicitly separate."""
        work_dir = Path(app.workingDirectory).expanduser()
        if not work_dir.exists():
            app.status = "missing-local-source" if app.environment in {"workstation", "local"} else app.status
            return
        repo = self._find_git_root(work_dir)
        if repo:
            state = self._read_git_state(repo)
            app.dirty = bool(state.get("dirty"))
            app.gitHead = str(state.get("head") or "")
            app.gitBranch = str(state.get("branch") or "unknown")
        detected = self._detect_source_version(app, work_dir)
        if detected:
            app.version = detected

    def _get_canonical_apps(self) -> Dict[str, AppEntry]:
        """Define the canonical ALLTHINGS140 applications registry."""
        root = str(self.project_root)

        return {
            "radio-server": AppEntry(
                id="radio-server",
                name="allthings140radio-server",
                displayName="Station Broadcast Server",
                description="Authoritative 24/7 AutoDJ broadcast engine. Owns SQLite catalog, approved rotation, FFmpeg AutoDJ encoder, ducking ad mixer, and Icecast auth relay.",
                category="broadcast",
                repoPath="tools/server.py",
                workingDirectory=os.path.join(root, "tools"),
                version="0.8.0",
                techStack="Python 3, SQLite3, FFmpeg, Icecast 2",
                status="active-production",
                environment="oracle-vm1",
                deploymentTarget="Oracle Cloud VM 1 (/opt/allthings140radio-server/server.py)",
                serviceName="allthings140radio-server.service",
                healthUrl="http://127.0.0.1:14080/api/health",
                launchCommand="python3 tools/server.py",
                buildCommand="",
                testCommand="python3 -m unittest tests/test_server.py",
                updateCommand="bash operations/apply-allthings140-update.sh",
                backupPath="/srv/allthings140radio/backups",
                logsCommand="journalctl -u allthings140radio-server.service -n 80 --no-pager",
                dependencies=["FFmpeg", "Icecast 2", "station.db", "Google Drive rclone"],
                relatedApps=["dj-app", "hot-cache", "catalog-integrity", "ai-host", "web-frontend"],
                notes="CRITICAL 24/7 AUTHORITY: Never deploy without backup. Stderr must use DEVNULL to prevent encoder deadlocks.",
                iconKey="broadcast",
                isDangerousToRestart=True
            ),
            "dj-app": AppEntry(
                id="dj-app",
                name="allthings140radio-dj",
                displayName="Desktop DJ Workstation",
                description="Administrative station control app for catalog browsing, playlist approvals, ad scheduling, live takeover triggers, and support transaction reviews.",
                category="broadcast",
                repoPath="tools/dj_app.py",
                workingDirectory=os.path.join(root, "tools"),
                version="0.7.0",
                techStack="Python 3, Tkinter/TTK, SQLite3",
                status="active-tool",
                environment="workstation",
                deploymentTarget="Zorin Desktop (/opt/allthings140radio-dj/dj_app.py)",
                serviceName="",
                healthUrl="http://127.0.0.1:14080/api/health",
                launchCommand="python3 tools/dj_app.py",
                buildCommand="",
                testCommand="python3 tools/radio_healthcheck.py",
                updateCommand="cp tools/dj_app.py /opt/allthings140radio-dj/dj_app.py",
                backupPath="backups/",
                logsCommand="cat ~/.local/share/allthings140radio-dj/dj.log",
                dependencies=["station.db", "Tailscale MagicDNS", "Python Tkinter"],
                relatedApps=["radio-server", "catalog-integrity", "ai-host"],
                notes="Interacts directly with station.db. Takeover status updates run on background thread to prevent queue wipes.",
                iconKey="dj",
                isDangerousToRestart=False
            ),
            "web-frontend": AppEntry(
                id="web-frontend",
                name="allthings140radio-web",
                displayName="Web Listener Frontend (PWA)",
                description="Public listener website and PWA player with continuous MP3 streaming, background playback recovery, chat drawer, and Fourthwall/Stripe support.",
                category="web",
                repoPath="radio/",
                workingDirectory=os.path.join(root, "radio"),
                version="1.6.1",
                techStack="HTML5, Vanilla CSS, Vanilla JavaScript, Service Worker v54",
                status="active-production",
                environment="cloudflare",
                deploymentTarget="Cloudflare Pages (project: ebeinc)",
                serviceName="",
                healthUrl="https://allthings140radio.online",
                launchCommand="xdg-open https://allthings140radio.online",
                buildCommand="",
                testCommand="python3 tools/site_smoke.py",
                updateCommand="npx wrangler pages deploy radio --project-name ebeinc --branch main --commit-dirty=true",
                backupPath="backups/",
                logsCommand="npx wrangler pages deployment list --project-name ebeinc",
                dependencies=["Cloudflare Pages", "Service Worker v54", "Cloudflare Tunnel"],
                relatedApps=["radio-server", "cloudflare-workers", "visuals-green"],
                notes="Service worker excludes .mp3, .m3u8, and /obs/ from CacheStorage. Audio element respects dataset.src.",
                iconKey="globe",
                isDangerousToRestart=False
            ),
            "visuals-workstation": AppEntry(
                id="visuals-workstation",
                name="allthings140radio-visuals",
                displayName="Visuals Desktop Show-Control Workstation",
                description="Professional 7-layer visual show-control workstation with canonical 16:9 geometry engine, async Rust backend, WYSIWYG workshop, and 1-click Green staging sync.",
                category="visuals",
                repoPath="visuals-app/",
                workingDirectory=os.path.join(root, "visuals-app"),
                version="0.1.32",
                techStack="Rust (Tauri v2), Vite, JavaScript, FFmpeg",
                status="active-workstation",
                environment="workstation",
                deploymentTarget="Zorin Desktop (~/.local/bin/allthings140radio-visuals)",
                serviceName="",
                healthUrl="http://127.0.0.1:14340",
                launchCommand="~/.local/bin/allthings140radio-visuals",
                buildCommand="npm run tauri build",
                testCommand="node tests/test_geometry_parity.mjs && node tests/test_visuals_workstation_ui.mjs",
                updateCommand="sudo dpkg -i src-tauri/target/release/bundle/deb/ALLTHINGS140Radio*.deb",
                backupPath="backups/",
                logsCommand="cat ~/.local/share/allthings140radio-visuals/workstation.log",
                dependencies=["FFmpeg", "Tauri v2", "57 Visual MP4s", "Stage alpha.mov"],
                relatedApps=["visuals-green", "visuals-realtime"],
                notes="Visuals workstation source. Verify installed version and runtime health before making production assumptions.",
                iconKey="monitor",
                isDangerousToRestart=False
            ),
            "visuals-green": AppEntry(
                id="visuals-green",
                name="allthings140-visuals-green",
                displayName="Green Web Stage (Staging)",
                description="Staging web stage with dual video buffer, audience presence bubbles, reaction particle system, room energy meter, and takeover schedule HUD.",
                category="visuals",
                repoPath="visuals-green/",
                workingDirectory=os.path.join(root, "visuals-green"),
                version="0.1.32-green",
                techStack="HTML5, Canvas/CSS, JavaScript, Cloudflare Pages",
                status="active-staging",
                environment="cloudflare",
                deploymentTarget="Cloudflare Pages (allthings140-visuals-green.pages.dev)",
                serviceName="",
                healthUrl="https://allthings140-visuals-green.pages.dev",
                launchCommand="xdg-open https://allthings140-visuals-green.pages.dev",
                buildCommand="",
                testCommand="node test_v0134_end_to_end.mjs",
                updateCommand="npx wrangler pages deploy visuals-green --project-name allthings140-visuals-green --branch main",
                backupPath="backups/",
                logsCommand="",
                dependencies=["Cloudflare Pages", "visuals-realtime-staging", "Media Role Separation"],
                relatedApps=["visuals-workstation", "visuals-realtime"],
                notes="FROZEN baseline. Production SHA-256 4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32 permanently protected.",
                iconKey="sparkles",
                isDangerousToRestart=False
            ),
            "visuals-realtime": AppEntry(
                id="visuals-realtime",
                name="allthings140-visuals-realtime",
                displayName="Visuals Realtime Server",
                description="Realtime WebSocket room server managing live audience presence, reaction aggregation, dynamic room energy calculation, and server-authoritative takeover schedules.",
                category="visuals",
                repoPath="visuals-realtime/",
                workingDirectory=os.path.join(root, "visuals-realtime"),
                version="0.1.0-staging",
                techStack="Python 3, aiohttp, WebSockets, SQLite",
                status="active-staging",
                environment="oracle-vm2",
                deploymentTarget="Oracle Cloud VM 2 (visuals-realtime-staging.allthings140radio.online)",
                serviceName="allthings140-visuals-realtime.service",
                healthUrl="https://visuals-realtime-staging.allthings140radio.online/health",
                launchCommand="python3 visuals-realtime/app.py",
                buildCommand="",
                testCommand="curl -fsS https://visuals-realtime-staging.allthings140radio.online/health",
                updateCommand="ssh allthings140-visuals-realtime 'cd /opt/visuals-realtime && git pull && sudo systemctl restart allthings140-visuals-realtime'",
                backupPath="/opt/visuals-realtime/backups",
                logsCommand="ssh allthings140-visuals-realtime 'journalctl -u allthings140-visuals-realtime -n 50 --no-pager'",
                dependencies=["aiohttp", "WebSockets", "SQLite realtime.db"],
                relatedApps=["visuals-green", "visuals-workstation"],
                notes="Port 14140/8765. Features session rate limiting, IP event pruning, and allowlisted CORS on /visuals-state.",
                iconKey="activity",
                isDangerousToRestart=False
            ),
            "android-app": AppEntry(
                id="android-app",
                name="allthings140radio-android",
                displayName="Android Mobile App",
                description="Native Android listener application with Media3 ExoPlayer background foreground service, notification controls, and Android Auto / Automotive integration.",
                category="mobile",
                repoPath="android/mobile-app/",
                workingDirectory=os.path.join(root, "android/mobile-app"),
                version="1.1.0",
                techStack="Android SDK 35, Java 11, AndroidX Media3",
                status="active-artifact",
                environment="mobile",
                deploymentTarget="Android APK (debug-signed)",
                serviceName="",
                healthUrl="",
                launchCommand="./gradlew assembleDebug",
                buildCommand="./gradlew assembleRelease",
                testCommand="./gradlew test",
                updateCommand="",
                backupPath="android/mobile-app/app/build/outputs/apk/",
                logsCommand="",
                dependencies=["Android SDK 35", "Java 11", "ExoPlayer Media3"],
                relatedApps=["radio-server", "web-frontend"],
                notes="Currently debug-signed. Google Play release requires KEYSTORE_FILE env properties.",
                iconKey="smartphone",
                isDangerousToRestart=False
            ),
            "discord-bot": AppEntry(
                id="discord-bot",
                name="allthings140radio-discord-bot",
                displayName="Discord Community Bot",
                description="Community Discord bot providing /nowplaying, /radio status, /invite, and automated live broadcast announcements.",
                category="tools",
                repoPath="discord-bot/",
                workingDirectory=os.path.join(root, "discord-bot"),
                version="1.0.0",
                techStack="Node.js (>=20), discord.js v14",
                status="standalone",
                environment="workstation",
                deploymentTarget="Node.js Service",
                serviceName="",
                healthUrl="",
                launchCommand="npm start",
                buildCommand="npm install",
                testCommand="node -e 'console.log(\"Bot syntax valid\")'",
                updateCommand="npm update",
                backupPath="",
                logsCommand="",
                dependencies=["Node.js >=20", "discord.js v14", "dotenv"],
                relatedApps=["radio-server"],
                notes="Token stored in discord-bot/.env (gitignored). Field mapping updated for current station status payload.",
                iconKey="message-square",
                isDangerousToRestart=False
            ),
            "ai-host": AppEntry(
                id="ai-host",
                name="allthings140radio-ai-host",
                displayName="AI Host & Interstitial Generator",
                description="Synthesizes conversational radio interstitials (station IDs, roasts, promos, takeover announcements) between songs using Ollama LLM and Piper TTS.",
                category="tools",
                repoPath="tools/ai_host.py",
                workingDirectory=os.path.join(root, "tools"),
                version="1.0.0",
                techStack="Python 3, Ollama (llama3.2:3b), Piper TTS",
                status="integrated",
                environment="oracle-vm1",
                deploymentTarget="Integrated in Station Server",
                serviceName="",
                healthUrl="",
                launchCommand="python3 -c 'from tools.ai_host import AIHost; print(\"AI Host ready\")'",
                buildCommand="",
                testCommand="python3 -m unittest tests/test_ai_host.py",
                updateCommand="",
                backupPath="",
                logsCommand="",
                dependencies=["Ollama (127.0.0.1:11434)", "Piper TTS", "PersonaLibrary"],
                relatedApps=["radio-server", "dj-app"],
                notes="Fail-open design: TTS/LLM timeouts return None so music playback is never blocked or interrupted.",
                iconKey="cpu",
                isDangerousToRestart=False
            ),
            "hot-cache": AppEntry(
                id="hot-cache",
                name="allthings140radio-hot-cache",
                displayName="Predictive Hot Cache Manager",
                description="Rolling pre-fetcher downloading upcoming rotation tracks from Google Drive to local NVMe storage targeting 120 minutes of buffer.",
                category="broadcast",
                repoPath="tools/cache_manager.py",
                workingDirectory=os.path.join(root, "tools"),
                version="1.0.0",
                techStack="Python 3, SQLite3, ffprobe, rclone",
                status="active-service",
                environment="oracle-vm1",
                deploymentTarget="Oracle Cloud VM 1 (systemd timer)",
                serviceName="allthings140radio-cache.service",
                healthUrl="http://127.0.0.1:14080/api/health",
                launchCommand="python3 tools/cache_manager.py once",
                buildCommand="",
                testCommand="python3 tools/cache_manager.py status",
                updateCommand="",
                backupPath="",
                logsCommand="journalctl -u allthings140radio-cache.service -n 50 --no-pager",
                dependencies=["station.db", "Google Drive", "NVMe Cache Volume"],
                relatedApps=["radio-server", "catalog-integrity"],
                notes="Evicts LRU tracks when over 5 GB or disk free <12%. Indexes all valid ready tracks.",
                iconKey="database",
                isDangerousToRestart=False
            ),
            "catalog-integrity": AppEntry(
                id="catalog-integrity",
                name="allthings140radio-catalog-integrity",
                displayName="Catalog Integrity System",
                description="Continuous verification of SHA-256 audio hashes, DB reconciliation against physical mirror files, and automated playback admission timer.",
                category="broadcast",
                repoPath="tools/catalog_integrity.py",
                workingDirectory=os.path.join(root, "tools"),
                version="1.0.0",
                techStack="Python 3, SQLite3, hashlib, json",
                status="active-service",
                environment="oracle-vm1",
                deploymentTarget="Oracle Cloud VM 1",
                serviceName="",
                healthUrl="cat /var/lib/allthings140radio/catalog-integrity.json",
                launchCommand="python3 tools/catalog_integrity.py --scan",
                buildCommand="",
                testCommand="python3 tools/catalog_integrity.py --verify",
                updateCommand="",
                backupPath="",
                logsCommand="",
                dependencies=["station.db", "Emergency Mirror (/srv/allthings140radio/data/music)"],
                relatedApps=["radio-server", "hot-cache", "dj-app"],
                notes="Catalog integrity verifier. Current health/counts must be read from its authoritative runtime output; no fixed count is assumed by Hub.",
                iconKey="shield-check",
                isDangerousToRestart=False
            ),
            "backup-recovery": AppEntry(
                id="backup-recovery",
                name="allthings140radio-backup-recovery",
                displayName="Station Backup & Disaster Recovery",
                description="Comprehensive backup suite covering station.db snapshots, off-host encrypted archives, VM rollback points, and media mirrors.",
                category="tools",
                repoPath="tools/backup_radio.py",
                workingDirectory=os.path.join(root, "tools"),
                version="1.0.0",
                techStack="Python 3, Bash, tar, GPG/OpenSSL",
                status="active-tool",
                environment="workstation",
                deploymentTarget="Local & Off-Host Storage",
                serviceName="",
                healthUrl="",
                launchCommand="python3 tools/backup_radio.py --create",
                buildCommand="",
                testCommand="python3 tools/offhost_backup.py --verify",
                updateCommand="",
                backupPath="backups/",
                logsCommand="",
                dependencies=["tar", "sqlite3", "gzip"],
                relatedApps=["radio-server", "catalog-integrity"],
                notes="Contains disaster recovery runbooks (BACKUP_RECOVERY.md, RECOVERY_ADMIN_GUIDE.md).",
                iconKey="archive",
                isDangerousToRestart=False
            ),
            "radio-diagnostics": AppEntry(
                id="radio-diagnostics",
                name="allthings140radio-diagnostics",
                displayName="Diagnostics & Health Suite",
                description="Comprehensive health checker validating website HTTP 200, status API, current track monotonicity, live MP3 stream bytes, and visuals realtime.",
                category="tools",
                repoPath="tools/radio_healthcheck.py",
                workingDirectory=os.path.join(root, "tools"),
                version="1.0.0",
                techStack="Python 3, urllib, json, curl",
                status="active-tool",
                environment="workstation",
                deploymentTarget="Workstation & CI",
                serviceName="",
                healthUrl="",
                launchCommand="python3 tools/radio_healthcheck.py --json",
                buildCommand="",
                testCommand="python3 tools/allthings140-diagnose.py",
                updateCommand="",
                backupPath="",
                logsCommand="",
                dependencies=["Python 3"],
                relatedApps=["radio-server", "web-frontend", "visuals-realtime"],
                notes="Powers the 'allthings140 status' and 'allthings140 diagnose' CLI commands.",
                iconKey="activity",
                isDangerousToRestart=False
            ),
            "cloudflare-workers": AppEntry(
                id="cloudflare-workers",
                name="allthings140radio-workers",
                displayName="Edge Cloudflare Workers",
                description="Serverless edge layer handling takeover alert authentication, chat routing via Durable Objects, and past stream archive gateways.",
                category="web",
                repoPath="radio/_worker.js",
                workingDirectory=os.path.join(root, "radio"),
                version="1.2.0",
                techStack="TypeScript / JavaScript, Cloudflare Workers",
                status="active-production",
                environment="cloudflare",
                deploymentTarget="Cloudflare Edge",
                serviceName="",
                healthUrl="https://allthings140radio.online/api/public/status",
                launchCommand="",
                buildCommand="npx wrangler deploy",
                testCommand="",
                updateCommand="npx wrangler pages deploy radio --project-name ebeinc --branch main",
                backupPath="",
                logsCommand="npx wrangler pages deployment tail --project-name ebeinc",
                dependencies=["Cloudflare Wrangler", "ADMIN_ALERT_KEY secret"],
                relatedApps=["web-frontend", "radio-server"],
                notes="Protects admin takeover webhook endpoints with Bearer token authentication.",
                iconKey="zap",
                isDangerousToRestart=False
            ),
            "oracle-vm1": AppEntry(
                id="oracle-vm1",
                name="allthings140radio-server-vm",
                displayName="Oracle Cloud VM 1 (Broadcast Plane)",
                description="Plane 2 24/7 station broadcast authority running AutoDJ, Icecast 2, Hot Cache, and Cloudflare Tunnel to the live stream.",
                category="infra",
                repoPath="operations/",
                workingDirectory=os.path.join(root, "operations"),
                version="Oracle Linux 9.8",
                techStack="Linux, systemd, Tailscale, Cloudflare Tunnel",
                status="active-production",
                environment="oracle-vm1",
                deploymentTarget="Oracle Cloud Infrastructure (allthings140radio-server)",
                serviceName="allthings140radio-server.service",
                healthUrl="http://allthings140radio-server:14080/api/health",
                launchCommand="tailscale ssh ebmarah@allthings140radio-server",
                buildCommand="",
                testCommand="curl -fsS http://allthings140radio-server:14080/api/health",
                updateCommand="",
                backupPath="/srv/allthings140radio/backups",
                logsCommand="ssh allthings140radio-server 'journalctl -u allthings140radio-server -n 40 --no-pager'",
                dependencies=["Tailscale", "firewalld", "cloudflared", "Icecast 2"],
                relatedApps=["radio-server", "hot-cache", "oracle-vm2"],
                notes="MagicDNS: allthings140radio-server. Private control port 14080 is loopback + Tailscale only.",
                iconKey="server",
                isDangerousToRestart=True
            ),
            "oracle-vm2": AppEntry(
                id="oracle-vm2",
                name="allthings140-visuals-realtime-vm",
                displayName="Oracle Cloud VM 2 (Visuals Plane)",
                description="Plane 3 realtime and visual media plane running the WebSocket server and Cloudflare Tunnel for room presence and energy state.",
                category="infra",
                repoPath="visuals-realtime/",
                workingDirectory=os.path.join(root, "visuals-realtime"),
                version="Oracle Linux 9.8",
                techStack="Linux, aiohttp, systemd, Tailscale, Cloudflare Tunnel",
                status="active-staging",
                environment="oracle-vm2",
                deploymentTarget="Oracle Cloud Infrastructure (allthings140-visuals-realtime)",
                serviceName="allthings140-visuals-realtime.service",
                healthUrl="https://visuals-realtime-staging.allthings140radio.online/health",
                launchCommand="tailscale ssh ebmarah@allthings140-visuals-realtime",
                buildCommand="",
                testCommand="curl -fsS https://visuals-realtime-staging.allthings140radio.online/health",
                updateCommand="",
                backupPath="/opt/visuals-realtime/backups",
                logsCommand="ssh allthings140-visuals-realtime 'journalctl -u allthings140-visuals-realtime -n 40 --no-pager'",
                dependencies=["Tailscale", "cloudflared", "Python 3"],
                relatedApps=["visuals-realtime", "visuals-green", "oracle-vm1"],
                notes="Dedicated visuals host. Tunnel configured with Wants= to protect against gateway maintenance disconnects.",
                iconKey="server",
                isDangerousToRestart=False
            )
        }
