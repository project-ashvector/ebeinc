"""
ALLTHINGS140 Hub — Command Line Interface
Fast headless CLI for querying registry, health status, prompts, handoffs, and launching agents.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hub.registry.app_registry import AppRegistry
from hub.registry.project_registry import ProjectRegistry
from hub.services.agent_service import AgentService
from hub.services.health_service import HealthService
from hub.services.handoff_service import HandoffService
from hub.services.prompt_service import PromptService
from hub.services.update_service import UpdateService


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="allthings140-hub",
        description="ALLTHINGS140 Hub — Operations Center CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # status
    subparsers.add_parser("status", help="Check overall station health and telemetry")

    # apps
    p_apps = subparsers.add_parser("apps", help="List all registered applications and services")
    p_apps.add_argument("--json", action="store_true", help="Emit raw JSON")

    # health
    p_health = subparsers.add_parser("health", help="Run full health check across all endpoints")
    p_health.add_argument("--json", action="store_true", help="Emit raw JSON")

    # prompts
    subparsers.add_parser("prompts", help="List reusable prompt templates")

    # handoffs
    p_handoffs = subparsers.add_parser("handoffs", help="List engineering handoffs")
    p_handoffs.add_argument("--export", metavar="HANDOFF_ID", help="Export handoff for ChatGPT")

    # smart-prompt
    p_smart = subparsers.add_parser("smart-prompt", help="Generate smart context prompt for an app")
    p_smart.add_argument("--app", required=True, help="Target application ID")
    p_smart.add_argument("--task", default="Investigate and implement task", help="Task title")

    # updates
    subparsers.add_parser("updates", help="Check version matrix and available updates")

    args = parser.parse_args()

    if not args.command or args.command == "status":
        hs = HealthService()
        snap = hs.run_check()
        print("==================================================")
        print(" ALLTHINGS140 OPERATIONAL STATUS")
        print("==================================================")
        print(f"Overall Status:    {snap.overall_status.upper()}")
        print(f"Broadcast Mode:    {snap.mode.upper()}" + (" (LIVE)" if snap.live else ""))
        print(f"Current Track:     {snap.current_artist} - {snap.current_title}")
        print(f"Public Stream:     {snap.stream_status.upper()} (stream.ebeinc.online)")
        print(f"Active Listeners:  {snap.listeners}")
        print(f"Catalog State:     {snap.catalog_health.upper()}" + (f" ({snap.approved_tracks} approved tracks reported)" if snap.approved_tracks else ""))
        print(f"Hot Cache:         {snap.cache_status.upper()}" + (f" ({snap.cache_tracks_ready} tracks ready reported)" if snap.cache_tracks_ready else ""))
        print(f"Visuals Realtime:  {'ONLINE' if snap.realtime_online else ('UNREACHABLE/UNKNOWN' if not snap.vm2_reachable else 'OFFLINE')}")
        return 0

    elif args.command == "apps":
        reg = AppRegistry()
        apps = reg.all()
        if getattr(args, "json", False):
            import dataclasses
            print(json.dumps([dataclasses.asdict(a) for a in apps], indent=2))
        else:
            print(f"{'ID':<22} {'NAME':<32} {'VERSION':<10} {'STATUS':<16} {'ENVIRONMENT'}")
            print("-" * 95)
            for a in apps:
                print(f"{a.id:<22} {a.displayName[:30]:<32} {a.version:<10} {a.status:<16} {a.environment}")
        return 0

    elif args.command == "health":
        hs = HealthService()
        snap = hs.run_check()
        if getattr(args, "json", False):
            import dataclasses
            print(json.dumps(dataclasses.asdict(snap), indent=2))
        else:
            print(f"Station Health: {snap.overall_status.upper()} | Stream: {snap.stream_status.upper()}")
            for c in snap.checks:
                status_str = "PASS" if c.is_healthy else "FAIL"
                print(f"[{status_str}] {c.name:<30} {c.response_time_ms:>6.1f}ms  {c.detail}")
        return 0

    elif args.command == "prompts":
        ps = PromptService()
        for p in ps.all():
            tags_str = " ".join(f"#{t}" for t in p.tags)
            print(f"• [{p.id}] {p.title} ({tags_str})\n  {p.description}\n")
        return 0

    elif args.command == "handoffs":
        hos = HandoffService()
        if args.export:
            print(hos.export_for_chatgpt(args.export))
        else:
            for h in hos.all():
                print(f"[{h.formattedDate}] {h.taskTitle} ({h.appName} by {h.agentName})")
                print(f"  Next: {h.recommendedNextTask}\n")
        return 0

    elif args.command == "smart-prompt":
        reg = AppRegistry()
        agent_s = AgentService()
        app = reg.get(args.app)
        if not app:
            print(f"Error: Application '{args.app}' not found.", file=sys.stderr)
            return 1
        prompt = agent_s.generate_smart_prompt(app, args.task)
        print(prompt)
        return 0

    elif args.command == "updates":
        reg = AppRegistry()
        us = UpdateService()
        matrix = us.get_version_matrix(reg.all())
        print(f"{'APPLICATION':<32} {'LOCAL':<10} {'DEPLOYED':<10} {'STATE':<14} {'DETAILS'}")
        print("-" * 90)
        for m in matrix:
            print(f"{m.appName[:30]:<32} {m.localVersion:<10} {m.deployedVersion:<10} {m.updateType:<14} {m.details}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
