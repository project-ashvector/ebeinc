#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import subprocess
import shutil
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.request
import webbrowser

SERVER_URL = "http://127.0.0.1:14080"
CLOUD_SERVER_URL = "http://100.124.12.41:14080"
PUBLIC_SITE = "https://ebeinc.online/radio/"
VERSION = "0.4.23"


def get_json(path: str):
    request = urllib.request.Request(SERVER_URL + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read().decode())


def get_cloud_json(path: str):
    request = urllib.request.Request(CLOUD_SERVER_URL + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=4) as response:
        return json.loads(response.read().decode())


class Manager(tk.Tk):
    def __init__(self):
        super().__init__(className="AllThings140RadioServer")
        self.title("AllThings140Radio — Server")
        self.geometry("900x680")
        self.minsize(820, 620)
        self.configure(bg="#09070d")
        self.option_add("*Font", "Sans 10")
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("TButton", background="#7d2bc4", foreground="white", borderwidth=0, padding=(14, 10), font=("Sans", 10, "bold"))
        self.style.map("TButton", background=[("active", "#9844dc")])
        self.closing = False
        self.refresh_after_id = None
        self.refresh_running = False
        self.current_status = {}
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build()
        self.refresh_after_id = self.after(300, self.refresh)

    def build(self):
        header = tk.Frame(self, bg="#15101d", padx=30, pady=22, highlightbackground="#382748", highlightthickness=1)
        header.pack(fill="x")
        tk.Label(header, text="ALLTHINGS140", bg="#15101d", fg="#f7efff", font=("Sans", 25, "bold")).pack(anchor="w")
        tk.Label(header, text=f"RADIO SERVER  •  v{VERSION}", bg="#15101d", fg="#bd73ef", font=("Sans", 10, "bold")).pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self, bg="#09070d", padx=30, pady=26)
        body.pack(fill="both", expand=True)

        self.status_card = tk.Frame(body, bg="#17111f", padx=22, pady=20, highlightbackground="#3a2949", highlightthickness=1)
        self.status_card.pack(fill="x")
        self.status_title = tk.Label(self.status_card, text="CHECKING RADIO SERVICES…", bg="#17111f", fg="#f4ebfa", font=("Sans", 15, "bold"), anchor="w")
        self.status_title.pack(fill="x")
        self.status = tk.Label(self.status_card, text="", bg="#17111f", fg="#b9acc5", justify="left", anchor="w", font=("Sans", 10))
        self.status.pack(fill="x", pady=(10, 0))

        buttons = tk.Frame(body, bg="#09070d")
        buttons.pack(fill="x", pady=18)
        ttk.Button(buttons, text="Open Public Listener Site", command=lambda: webbrowser.open(PUBLIC_SITE)).pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="Open Cloud Control", command=lambda: webbrowser.open(CLOUD_SERVER_URL)).pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="Open PC Fallback", command=lambda: webbrowser.open(SERVER_URL)).pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="Restart Radio", command=self.restart).pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="Connect Public Website", command=self.connect_public).pack(side="left", padx=(0, 10))
        ttk.Button(buttons, text="Copy Cloud DJ Address", command=self.copy_address).pack(side="left")

        public_buttons = tk.Frame(body, bg="#09070d")
        public_buttons.pack(fill="x", pady=(0, 10))
        ttk.Button(public_buttons, text="Check Public Connection", command=self.check_public).pack(side="left", padx=(0, 10))
        ttk.Button(public_buttons, text="Fix Public Audio", command=self.connect_audio).pack(side="left", padx=(0, 10))
        ttk.Button(public_buttons, text="Open Tunnel Logs", command=self.open_tunnel_logs).pack(side="left")
        tk.Label(public_buttons, text="Cloudflare carries status; Tailscale Funnel carries continuous audio.", bg="#09070d", fg="#9f8cab").pack(side="right")

        guide_header = tk.Frame(body, bg="#09070d")
        guide_header.pack(fill="x", pady=(8, 8))
        tk.Label(guide_header, text="SETUP CHECKLIST", bg="#09070d", fg="#ddbbf5", font=("Sans", 11, "bold")).pack(side="left")
        tk.Label(guide_header, text="The public website is deployed separately from this server.", bg="#09070d", fg="#8f8299").pack(side="right")

        guide = """1  KEEP THIS COMPUTER ON
The radio service and AutoDJ start automatically after a reboot.

2  CONNECT THE DJ APPS
Install the DJ .deb on both computers. Use Discover Station or copy the DJ address shown above. Accounts: ebmarah and eyewitnis. Temporary first-use password: allthings140.

3  LOAD THE ROTATION
Upload only audio you own or have permission to broadcast. Approved tracks become the real 24/7 live rotation. Keep Ebmarah's approved catalog loaded so the station plays it continuously.

4  CONTROL THE SHARED ROTATION
Open On Air in the DJ app. Previous, Restart, Next, and every Play Now button control the actual server feed for every listener. The current and next tracks are displayed clearly.

5  CONNECT THE PUBLIC WEBSITE STATUS
Press Connect Public Website above. Cloudflare securely carries the small status requests used for now-playing, next-track, mode, and listener information.

6  FIX PUBLIC AUDIO
Press Fix Public Audio once. Tailscale Funnel provides the continuous HTTPS audio connection because Cloudflare Tunnel buffers ordinary endless audio responses. The listener website still looks the same and automatically receives the working audio URL from the status API.

7  SAFE PUBLIC ROUTING
Both public connections point only to the restricted gateway on 127.0.0.1:14082. It exposes public status and the radio stream, while logins, uploads, passwords, settings, and DJ controls remain private on the LAN port.

8  GO LIVE
A DJ can start a live queue with microphone mixing. When the DJ stops or disconnects, Icecast falls back to AutoDJ automatically.
"""
        text = tk.Text(body, bg="#14101b", fg="#dfd5e7", insertbackground="white", relief="flat", wrap="word", padx=20, pady=18, highlightbackground="#342441", highlightthickness=1)
        text.insert("1.0", guide)
        text.config(state="disabled")
        text.pack(fill="both", expand=True)

    def refresh(self):
        if self.closing:
            return
        if self.refresh_running:
            return
        self.refresh_running = True
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            health = get_json("/api/health")
            public = get_json("/api/public/status")
            try:
                cloud_health = get_cloud_json("/api/health")
                cloud_public = get_cloud_json("/api/public/status")
                cloud_error = ""
            except Exception as exc:
                cloud_health = None
                cloud_public = None
                cloud_error = str(exc)
            result = (health, public, self.local_ip(), self.tunnel_state(), self.audio_funnel_state(), cloud_health, cloud_public, cloud_error)
            error = None
        except Exception as exc:
            result = None
            error = str(exc)
        if not self.closing:
            self.after(0, self._finish_refresh, result, error)

    def _finish_refresh(self, result, error):
        self.refresh_running = False
        if self.closing:
            return
        if error is None and result is not None:
            health, public, host, tunnel_state, audio_funnel_state, cloud_health, cloud_public, cloud_error = result
            self.current_status = public
            autodj = health.get("autodj", {})
            ice = health.get("icecast", {})
            cache = health.get("cache", {})
            mode = str(public.get("mode", "offline")).upper()
            cloud_ready = bool(cloud_health and cloud_health.get("icecast", {}).get("online"))
            self.status_title.config(
                text="● CLOUD PRIMARY ONLINE • THIS PC READY AS FALLBACK" if cloud_ready else "● PC FALLBACK READY • CLOUD STARTING",
                fg="#65edaa" if cloud_ready else "#e8bd67",
            )
            self.status.config(
                text=(
                    f"Cloud DJ address: {CLOUD_SERVER_URL}\n"
                    f"Cloud status: {'READY' if cloud_ready else 'STARTING / UNREACHABLE'}"
                    + (f"  •  {cloud_error}" if cloud_error else "") + "\n"
                    f"Cloud now playing: {(cloud_public or {}).get('current_artist', '')} — {(cloud_public or {}).get('current_title', '')}\n"
                    f"PC fallback: READY on http://{host}:14080\n"
                    f"Station: {health.get('name')}\n"
                    f"Broadcast mode: {mode}  •  Listeners: {public.get('listeners', 0)}\n"
                    f"DJ connection: http://{host}:14080\n"
                    f"Local stream: http://{host}:14000/live.mp3\n"
                    f"Public site: {PUBLIC_SITE}\n"
                    f"Configured public stream: {public.get('stream_url', 'not set')}\n"
                    f"Now playing: {public.get('current_artist', '')} — {public.get('current_title', '')}\n"
                    f"Next: {public.get('next_artist', '')} — {public.get('next_title', '')}\n"
                    f"Catalog files: {autodj.get('tracks', 0)}  •  AutoDJ process: {'RUNNING' if autodj.get('running') else 'RETRYING'}\n"
                    f"AutoDJ detail: {autodj.get('mode', '')}\n"
                    f"Last audio error: {autodj.get('last_error') or 'none'}\n"
                    f"Icecast: {'ONLINE' if ice.get('online') else 'OFFLINE'}\n"
                    f"Hot cache: {str(cache.get('status', 'UNKNOWN')).upper()}  •  {cache.get('minutes_ready', 0)} min ready / {cache.get('tracks_ready', 0)} tracks\n"
                    f"Public gateway: http://127.0.0.1:14082  •  Cloudflare status: {tunnel_state}\n"
                    f"Public audio: {public.get('stream_url', 'not set')}  •  Funnel: {audio_funnel_state}"
                )
            )
        else:
            self.status_title.config(text="● SERVER NOT RESPONDING", fg="#ff80a6")
            self.status.config(text=f"{error}\nUse Restart Radio below, then check the service logs if it remains offline.")
        if not self.closing:
            self.refresh_after_id = self.after(5000, self.refresh)

    @staticmethod
    def local_ip():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def restart(self):
        repair = (
            "systemctl stop allthings140radio-server.service allthings140radio-icecast.service || true; "
            "systemctl reset-failed allthings140radio-server.service allthings140radio-icecast.service || true; "
            "systemctl start allthings140radio-icecast.service; "
            "sleep 1; "
            "systemctl start allthings140radio-server.service; "
            "sleep 2; "
            "systemctl is-active --quiet allthings140radio-server.service"
        )
        proc = subprocess.run(["pkexec", "sh", "-lc", repair], capture_output=True, text=True)
        if proc.returncode:
            logs = subprocess.run(
                ["journalctl", "-u", "allthings140radio-server.service", "-n", "35", "--no-pager"],
                capture_output=True, text=True
            ).stdout[-3500:]
            messagebox.showerror(
                "Repair failed",
                (proc.stderr or "The server did not start.") + "\n\nRecent server log:\n" + (logs or "No log output was available.")
            )
        else:
            messagebox.showinfo("Radio repaired", "The Icecast and radio services were started in the correct order. DJ login should work again in a few seconds.")
            self.after(1200, self.refresh)

    @staticmethod
    def tunnel_state():
        try:
            proc = subprocess.run(["systemctl", "is-active", "allthings140radio-tunnel.service"], capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            return "CHECK TIMED OUT"
        return "CONNECTED" if proc.returncode == 0 and proc.stdout.strip() == "active" else "NOT CONNECTED"

    @staticmethod
    def audio_funnel_state():
        if not shutil.which("tailscale"):
            return "TAILSCALE NOT INSTALLED"
        try:
            proc = subprocess.run(["tailscale", "funnel", "status", "--json"], capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            return "CHECK TIMED OUT"
        if proc.returncode == 0 and "https" in proc.stdout.lower():
            return "CONNECTED"
        return "NOT CONNECTED"

    def connect_audio(self):
        script = "/usr/bin/allthings140radio-connect-audio"
        if not shutil.which("allthings140radio-connect-audio"):
            return messagebox.showerror("Audio setup tool missing", "Install the v0.4.11 Server package first.")
        command = f"{script}; printf '\\n'; read -r -p 'Press Enter to close…' _"
        terminals = []
        if shutil.which("x-terminal-emulator"):
            terminals.append(["x-terminal-emulator", "-e", "bash", "-lc", command])
        if shutil.which("gnome-terminal"):
            terminals.append(["gnome-terminal", "--", "bash", "-lc", command])
        if shutil.which("konsole"):
            terminals.append(["konsole", "-e", "bash", "-lc", command])
        for terminal in terminals:
            try:
                subprocess.Popen(terminal)
                messagebox.showinfo("Public audio setup", "A terminal has opened. Complete the Tailscale login or Funnel approval if requested. The tool will then connect and test the continuous audio feed.")
                return
            except OSError:
                continue
        messagebox.showerror("Could not open setup", f"Open Terminal and run:\n\n{script}")

    def connect_public(self):
        script = "/usr/bin/allthings140radio-connect-public"
        if not shutil.which("allthings140radio-connect-public"):
            return messagebox.showerror("Setup tool missing", "Install the v0.4.11 Server package first.")
        command = f"{script}; printf '\\n'; read -r -p 'Press Enter to close…' _"
        terminals = []
        if shutil.which("x-terminal-emulator"):
            terminals.append(["x-terminal-emulator", "-e", "bash", "-lc", command])
        if shutil.which("gnome-terminal"):
            terminals.append(["gnome-terminal", "--", "bash", "-lc", command])
        if shutil.which("konsole"):
            terminals.append(["konsole", "-e", "bash", "-lc", command])
        for terminal in terminals:
            try:
                subprocess.Popen(terminal)
                messagebox.showinfo("Public connection setup", "A setup terminal has opened. Complete the one Cloudflare browser login, then the tool will configure and test the public feed automatically.")
                return
            except OSError:
                continue
        messagebox.showerror("Could not open setup", f"Open Terminal and run:\n\n{script}")

    def check_public(self):
        try:
            status_base = str(self.current_status.get("public_host") or "https://status.ebeinc.online").rstrip("/")
            request = urllib.request.Request(status_base + "/api/public/status", headers={"Accept": "application/json", "User-Agent": "AllThings140Radio-Manager/0.4.11"})
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())
            messagebox.showinfo(
                "Public station connected",
                f"Station: {data.get('station_name', 'AllThings140Radio')}\n"
                f"Mode: {str(data.get('mode', 'offline')).upper()}\n"
                f"Now playing: {data.get('current_artist', '')} — {data.get('current_title', '')}\n\n"
                "The GitHub listener website can now reach this server."
            )
        except Exception as exc:
            messagebox.showwarning("Public connection not ready", f"The local station is safe, but the public HTTPS endpoint is not responding yet.\n\n{exc}\n\nPress Connect Public Website to run the guided setup.")

    def open_tunnel_logs(self):
        command = "journalctl -u allthings140radio-tunnel.service -n 120 --no-pager; printf '\\n'; read -r -p 'Press Enter to close…' _"
        if shutil.which("x-terminal-emulator"):
            subprocess.Popen(["x-terminal-emulator", "-e", "bash", "-lc", command])
        elif shutil.which("gnome-terminal"):
            subprocess.Popen(["gnome-terminal", "--", "bash", "-lc", command])
        else:
            messagebox.showinfo("Tunnel logs", "Run this in Terminal:\n\njournalctl -u allthings140radio-tunnel.service -n 120 --no-pager")

    def copy_address(self):
        value = CLOUD_SERVER_URL
        self.clipboard_clear()
        self.clipboard_append(value)
        messagebox.showinfo("DJ address copied", value)

    def on_close(self):
        if self.closing:
            return
        self.closing = True
        if self.refresh_after_id:
            try:
                self.after_cancel(self.refresh_after_id)
            except tk.TclError:
                pass
            self.refresh_after_id = None
        self.quit()
        self.destroy()


if __name__ == "__main__":
    Manager().mainloop()
