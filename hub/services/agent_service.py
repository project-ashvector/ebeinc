"""
ALLTHINGS140 Hub — AI & Coding Agent Control Center
Provides multi-provider abstraction for Antigravity, Codex, OpenCode, and Ollama,
smart prompt context generation, and workspace launch orchestration.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hub.config import PROJECT_ROOT, CONFIG_DIR, get_config
from hub.registry.app_registry import AppEntry


@dataclass
class CodingSession:
    id: str
    provider_id: str
    app_id: str
    task_title: str
    working_directory: str
    started_at: float
    prompt_used: str = ""
    status: str = "active"  # active, completed, closed


@dataclass
class AgentProviderInfo:
    id: str
    name: str
    executable: str
    is_available: bool
    version_string: str
    auth_status: str  # configured, missing, not_required, unknown
    description: str
    default_model: str = ""


class AgentService:
    """Manages AI coding agent integrations and terminal launches."""

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            try:
                project_root = Path(get_config().current_project_path).expanduser().resolve()
            except Exception:
                project_root = PROJECT_ROOT
        self.project_root = project_root
        self._sessions: List[CodingSession] = []

    def get_providers(self) -> List[AgentProviderInfo]:
        """Detect and return all registered AI agent providers with live availability."""
        cfg = get_config()
        providers = []

        for p_id, p_data in cfg.ai_providers.items():
            exe_path = p_data.get("executable", "")
            is_avail = bool(exe_path and os.path.exists(exe_path) and os.access(exe_path, os.X_OK))
            if not is_avail and exe_path:
                # Try finding in PATH
                found = shutil.which(os.path.basename(exe_path))
                if found:
                    exe_path = found
                    is_avail = True

            version_str = ""
            auth_status = "unknown"

            if is_avail:
                version_str = "Installed (not probed at startup)"
                auth_status = self._detect_auth(p_id)

            desc = ""
            if p_id == "antigravity":
                desc = "Google Deepmind Antigravity CLI (agy) pair-programming agent"
            elif p_id == "codex":
                desc = "OpenAI Codex interactive coding agent"
            elif p_id == "opencode":
                desc = "OpenCode autonomous terminal coding agent"
            elif p_id == "ollama":
                desc = "Local Ollama LLM service running offline"

            providers.append(AgentProviderInfo(
                id=p_id,
                name=p_data.get("name", p_id.title()),
                executable=exe_path,
                is_available=is_avail,
                version_string=version_str,
                auth_status=auth_status,
                description=desc,
                default_model=p_data.get("default_model", "")
            ))

        return providers

    def _detect_version(self, exe: str, provider_id: str) -> str:
        try:
            flag = "--version" if provider_id != "ollama" else "--version"
            res = subprocess.run([exe, flag], capture_output=True, text=True, timeout=3)
            out = (res.stdout or res.stderr or "").strip()
            first_line = out.split("\n")[0] if out else ""
            return first_line[:40]
        except Exception:
            return "Installed"

    def _detect_auth(self, provider_id: str) -> str:
        home = Path.home()
        if provider_id == "antigravity":
            return "Configured" if (home / ".gemini").exists() else "Not detected"
        if provider_id == "codex":
            candidates = [home / ".codex", home / ".config" / "codex"]
            return "Configured" if any(p.exists() for p in candidates) or bool(os.environ.get("OPENAI_API_KEY")) else "Not detected"
        if provider_id == "opencode":
            return "Configured" if (home / ".opencode").exists() else "Unknown / provider-managed"
        if provider_id == "ollama":
            return "Local (No Key Required)"
        return "Unknown"

    def generate_smart_prompt(self, app: AppEntry, task_title: str, task_instructions: str = "") -> str:
        """Generate a structured, safe context prompt header for the target application."""
        lines = [
            f"You are working on the ALLTHINGS140 Radio ecosystem.",
            f"TARGET APPLICATION: {app.displayName} ({app.name})",
            f"WORKING DIRECTORY: {app.workingDirectory}",
            f"CURRENT VERSION: {app.version}",
            f"GIT BRANCH: {app.gitBranch} (commit: {app.gitHead or 'latest'})",
            f"ENVIRONMENT: {app.environment.upper()} ({app.deploymentTarget})",
            f"TECH STACK: {app.techStack}",
            "",
            "## SAFETY REQUIREMENTS & DO NOT BREAK RULES",
            f"• Application Notes: {app.notes}",
            "• Zero Downtime: Never restart or deploy without verifying local health and backups.",
            "• Mobile Visuals (visuals-phone.mp4) must remain untouched.",
            "• Never expose or commit secrets, tokens, or private keys.",
            "",
            f"## TASK: {task_title}",
        ]
        if task_instructions:
            lines.extend([
                "",
                task_instructions
            ])
        else:
            lines.extend([
                "",
                "Please inspect the current codebase, verify health, implement the required changes safely, and document all changes in an engineering handoff."
            ])
        return "\n".join(lines)

    def launch_agent_session(
        self,
        provider_id: str,
        app: AppEntry,
        task_title: str,
        prompt_text: Optional[str] = None,
        model: Optional[str] = None
    ) -> CodingSession:
        """Launch the specified AI coding agent inside a dedicated terminal in the app's directory."""
        providers = {p.id: p for p in self.get_providers()}
        provider = providers.get(provider_id)
        if not provider or not provider.is_available:
            raise RuntimeError(f"AI Provider '{provider_id}' is not installed or available.")

        work_dir = Path(app.workingDirectory)
        if not work_dir.exists():
            work_dir = self.project_root

        if not prompt_text:
            prompt_text = self.generate_smart_prompt(app, task_title)

        session_id = f"session-{int(time.time())}-{app.id}"
        session = CodingSession(
            id=session_id,
            provider_id=provider_id,
            app_id=app.id,
            task_title=task_title,
            working_directory=str(work_dir),
            started_at=time.time(),
            prompt_used=prompt_text,
            status="active"
        )
        self._sessions.append(session)

        # Store task context outside the repository so launching an agent cannot
        # create uncommitted files in the target project.
        context_dir = CONFIG_DIR / "agent-contexts"
        context_dir.mkdir(parents=True, exist_ok=True)
        context_file = context_dir / f"{session_id}.md"
        context_file.write_text(prompt_text, encoding="utf-8")

        self._open_in_terminal(provider.executable, str(work_dir), prompt_text, session_id, app.displayName, provider_id, context_file)
        return session

    def _open_in_terminal(self, exe: str, work_dir: str, prompt: str, session_id: str, app_name: str, provider_id: str, context_file: Path) -> None:
        """Launch the agent in gnome-terminal or x-terminal-emulator."""
        title = f"ALLTHINGS140 Hub — Agent ({app_name})"
        
        # Provider prompt syntax changes over time. Launch the verified executable
        # interactively and make the exact Hub-generated context path explicit
        # instead of falsely claiming it was injected into the agent.
        import shlex
        header = f"=== ALLTHINGS140 HUB AGENT WORKSPACE: {app_name} ==="
        shell_cmd = (
            f"cd {shlex.quote(work_dir)} && "
            f"printf '%s\n' {shlex.quote(header)} "
            f"{shlex.quote('Task context: ' + str(context_file))} "
            f"{shlex.quote('Read that context file before changing this project.')} && "
            f"{shlex.quote(exe)}; exec bash"
        )

        # Check for gnome-terminal
        if shutil.which("gnome-terminal"):
            subprocess.Popen([
                "gnome-terminal",
                f"--title={title}",
                f"--working-directory={work_dir}",
                "--",
                "bash", "-c", shell_cmd
            ])
        elif shutil.which("x-terminal-emulator"):
            subprocess.Popen([
                "x-terminal-emulator",
                "-e", f"bash -c \"{shell_cmd}\""
            ], cwd=work_dir)
        elif shutil.which("xterm"):
            subprocess.Popen([
                "xterm",
                "-title", title,
                "-e", f"bash -c \"{shell_cmd}\""
            ], cwd=work_dir)
        else:
            # Background subprocess fallback
            subprocess.Popen([exe], cwd=work_dir)
