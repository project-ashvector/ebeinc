#!/usr/bin/env python3
from __future__ import annotations

import json
import base64
import calendar
import datetime as dt
import mimetypes
import queue
import os
import socket
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any
from zoneinfo import ZoneInfo

APP_NAME = "AllThings140Radio DJ"
ICON_PATH = "/usr/share/icons/hicolor/128x128/apps/allthings140radio-dj.png"
VERSION = "0.6.0"
PUBLIC_SITE = "https://ebeinc.online/radio/"
CONFIG_DIR = Path.home() / ".config" / "allthings140radio-dj"
CONFIG_FILE = CONFIG_DIR / "config.json"
CLOUD_DJ_URL = "http://100.124.12.41:14080"
DISCOVERY_PORT = 14081
AUDIO_TYPES = [("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.opus"), ("All files", "*")]
TAKEOVER_TIMES = [f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}" for hour in range(24) for minute in (0, 30)]
TAKEOVER_TIMEZONES = ["America/Los_Angeles", "America/Denver", "America/Chicago", "America/New_York", "America/Phoenix", "America/Anchorage", "Pacific/Honolulu", "Europe/London", "Europe/Paris", "Australia/Sydney", "Asia/Tokyo", "UTC"]


class APIError(RuntimeError):
    pass


class API:
    def __init__(self, base_url: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = ""

    def request(self, method: str, path: str, data: Any = None, timeout: int = 15):
        body = None
        headers = {"Accept": "application/json"}
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base_url + path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                return json.loads(raw.decode()) if raw else {}
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode()).get("error", str(exc))
            except Exception:
                detail = str(exc)
            raise APIError(detail) from exc
        except urllib.error.URLError as exc:
            raise APIError(f"Cannot connect to station: {exc.reason}") from exc

    def upload(self, path: Path, fields: dict[str, str], progress=None):
        boundary = "----AllThings140" + uuid.uuid4().hex
        chunks: list[bytes] = []
        for key, value in fields.items():
            chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
        mime = "application/octet-stream"
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode())
        ending = f"\r\n--{boundary}--\r\n".encode()
        total = sum(len(x) for x in chunks) + path.stat().st_size + len(ending)

        parsed = urllib.parse.urlparse(self.base_url)
        import http.client
        conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(parsed.hostname, parsed.port, timeout=120)
        target = (parsed.path.rstrip("/") if parsed.path else "") + "/api/upload"
        conn.putrequest("POST", target)
        conn.putheader("Authorization", f"Bearer {self.token}")
        conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        conn.putheader("Content-Length", str(total))
        conn.endheaders()
        sent = 0
        for chunk in chunks:
            conn.send(chunk); sent += len(chunk)
        with path.open("rb") as source:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                conn.send(chunk); sent += len(chunk)
                if progress:
                    progress(sent, total)
        conn.send(ending)
        response = conn.getresponse()
        raw = response.read().decode()
        conn.close()
        payload = json.loads(raw) if raw else {}
        if response.status >= 400:
            raise APIError(payload.get("error", f"Upload failed: HTTP {response.status}"))
        return payload


class DJApp(tk.Tk):
    def __init__(self):
        super().__init__(className="AllThings140RadioDJ")
        self.title(APP_NAME)
        try:
            self._app_icon = tk.PhotoImage(file=ICON_PATH)
            self.after_idle(lambda: self.iconphoto(False, self._app_icon))
        except tk.TclError:
            self._app_icon = None
        self.geometry("1120x760")
        self.minsize(980, 680)
        self.configure(bg="#0b0d14")

        self.option_add("*Font", "Sans 10")
        self.option_add("*TButton*Font", "Sans 10")
        self.option_add("*TCombobox*Listbox.font", "Sans 10")
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("TButton", background="#6d4aff", foreground="#ffffff", borderwidth=0, padding=(14, 9), font=("Sans", 10, "bold"), relief="flat")
        self.style.map("TButton", background=[("active", "#8a70ff"), ("pressed", "#5137d4"), ("disabled", "#252a3b")], foreground=[("disabled", "#777d92")])
        self.style.configure("TNotebook", background="#0b0d14", borderwidth=0, tabmargins=(0, 0, 0, 0))
        self.style.configure("TNotebook.Tab", background="#171b29", foreground="#9ca3b8", padding=(16, 11), borderwidth=0, font=("Sans", 10, "bold"))
        self.style.map("TNotebook.Tab", background=[("selected", "#30256b"), ("active", "#232743")], foreground=[("selected", "#ffffff")])
        self.style.configure("TEntry", fieldbackground="#151a27", foreground="#f4f6ff", bordercolor="#30374c", lightcolor="#30374c", darkcolor="#0f121b", padding=7)
        self.style.configure("TCombobox", fieldbackground="#151a27", foreground="#f4f6ff", bordercolor="#30374c", lightcolor="#30374c", darkcolor="#0f121b", padding=6)
        self.style.map("TCombobox", fieldbackground=[("readonly", "#151a27")], foreground=[("readonly", "#f4f6ff")])
        self.style.configure("TCheckbutton", background="#101521", foreground="#d9deed", padding=(4, 4))
        self.style.map("TCheckbutton", background=[("active", "#1a2030")], foreground=[("active", "#ffffff")])
        self.style.configure("Treeview", background="#121724", fieldbackground="#121724", foreground="#e8ecf7", borderwidth=0, rowheight=34, font=("Sans", 10))
        self.style.configure("Treeview.Heading", background="#202844", foreground="#e7eaff", relief="flat", padding=(8, 8), font=("Sans", 10, "bold"))
        self.style.map("Treeview", background=[("selected", "#40358a")], foreground=[("selected", "#ffffff")])
        self.style.configure("Vertical.TScrollbar", background="#202844", troughcolor="#0f131e", bordercolor="#0f131e", arrowcolor="#c6cbea")
        self.api = API()
        self.user = {}
        self.live_process: subprocess.Popen | None = None
        self.live_playlist: list[Path] = []
        self.temp_playlist: Path | None = None
        self.live_stop_requested = False
        self.live_runner_thread: threading.Thread | None = None
        self.live_current_index = 0
        self.library_rows: dict[str, dict[str, Any]] = {}
        self.library_refresh_running = False
        self.home_queue_rows: dict[int, dict[str, Any]] = {}
        self.guest_rows: dict[str, dict[str, Any]] = {}
        self.rotation_render_signature: tuple[Any, ...] | None = None
        self.status_after_id: str | None = None
        self.status_refresh_running = False
        self.status_queue = queue.Queue()
        self.status_drain_after_id = None
        self.ui_queue = queue.Queue()
        self.ui_drain_after_id = self.after(50, self._drain_ui_queue)
        self.closing = False
        self.config_data = self.load_config()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_connect()

    def load_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text())
            except Exception:
                pass
        return {"server_url": CLOUD_DJ_URL, "username": "ebmarah", "mic_source": "default"}

    def post_ui(self, callback):
        self.ui_queue.put(callback)

    def _drain_ui_queue(self):
        self.ui_drain_after_id = self.after(50, self._drain_ui_queue)
        for _ in range(100):
            try:
                callback = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception:
                pass

    def save_config(self):
        CONFIG_FILE.write_text(json.dumps(self.config_data, indent=2))

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    def header(self, parent, subtitle=""):
        head = tk.Frame(parent, bg="#151a29", padx=28, pady=20, highlightbackground="#2b3450", highlightthickness=1)
        head.pack(fill="x")
        tk.Label(head, text="ALLTHINGS140", bg="#151a29", fg="#f6f7ff", font=("Sans", 25, "bold")).pack(anchor="w")
        tk.Label(head, text=f"RADIO DJ  •  v{VERSION}  •  {subtitle}", bg="#151a29", fg="#9c8cff", font=("Sans", 10, "bold")).pack(anchor="w", pady=(4, 0))

    def show_connect(self):
        self.clear()
        root = tk.Frame(self, bg="#0e0915")
        root.pack(fill="both", expand=True)
        self.header(root, "Connect to the always-on station server")
        panel = tk.Frame(root, bg="#171020", padx=30, pady=28)
        panel.place(relx=.5, rely=.53, anchor="center", width=570, height=430)
        tk.Label(panel, text="DJ SIGN IN", bg="#171020", fg="#d7b9ff", font=("Sans", 12, "bold")).pack(anchor="w")
        tk.Label(panel, text="Private DJ server address", bg="#171020", fg="#e8dff0").pack(anchor="w", pady=(18, 4))
        self.server_entry = ttk.Entry(panel)
        self.server_entry.insert(0, self.config_data.get("server_url", ""))
        self.server_entry.pack(fill="x")
        tk.Label(panel, text=f"Cloud DJ address: {CLOUD_DJ_URL}. Tailscale keeps logins, uploads, and controls private. Do not use stream.ebeinc.online; that public address is listen-only.", bg="#171020", fg="#9f91ac", wraplength=500, justify="left").pack(anchor="w", pady=(6, 3))
        ttk.Button(panel, text="Discover Station on This Network", command=self.discover).pack(anchor="w", pady=8)
        tk.Label(panel, text="Username", bg="#171020", fg="#e8dff0").pack(anchor="w", pady=(8, 4))
        self.username_entry = ttk.Entry(panel)
        self.username_entry.insert(0, self.config_data.get("username", "ebmarah"))
        self.username_entry.pack(fill="x")
        tk.Label(panel, text="Password", bg="#171020", fg="#e8dff0").pack(anchor="w", pady=(12, 4))
        self.password_entry = ttk.Entry(panel, show="•")
        self.password_entry.pack(fill="x")
        self.password_entry.bind("<Return>", lambda e: self.login())
        tk.Label(panel, text="First login temporary password: allthings140", bg="#171020", fg="#9f91ac").pack(anchor="w", pady=(8, 16))
        ttk.Button(panel, text="Sign In", command=self.login).pack(fill="x", ipady=7)
        ttk.Button(panel, text="Setup Instructions", command=self.show_setup_popup).pack(fill="x", pady=(10, 0))
        self.update_idletasks()
        self.deiconify()
        self.geometry("1120x760")

    def discover(self):
        self.server_entry.delete(0, "end")
        self.server_entry.insert(0, "Searching…")
        def worker():
            found = []
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2.5)
            try:
                sock.sendto(b"ALLTHINGS140_DISCOVER", ("255.255.255.255", DISCOVERY_PORT))
                deadline = time.time() + 2.5
                while time.time() < deadline:
                    try:
                        data, _ = sock.recvfrom(4096)
                        payload = json.loads(data.decode())
                        if payload.get("url"):
                            found.append(payload)
                    except socket.timeout:
                        break
            finally:
                sock.close()
            self.post_ui(lambda: self.discovery_done(found))
        threading.Thread(target=worker, daemon=True).start()

    def discovery_done(self, found):
        self.server_entry.delete(0, "end")
        if found:
            self.server_entry.insert(0, found[0]["url"])
            messagebox.showinfo("Station found", f"Found {found[0].get('name')}\n{found[0]['url']}")
        else:
            messagebox.showwarning("Not found", "No station answered on this network. Enter the server address shown in the Server Manager, such as http://192.168.1.50:14080")

    def login(self):
        url = self.server_entry.get().strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        parsed = urllib.parse.urlparse(url)
        public_hosts = {"stream.ebeinc.online", "ebeinc.online", "www.ebeinc.online"}
        if (parsed.hostname or "").lower() in public_hosts:
            messagebox.showwarning(
                "Use the private DJ server address",
                f"stream.ebeinc.online is the public listener feed and intentionally blocks DJ logins.\n\nUse the private cloud DJ address:\n{CLOUD_DJ_URL}\n\nMake sure Tailscale is connected on this computer.",
            )
            self.discover()
            return
        self.api.base_url = url
        try:
            result = self.api.request("POST", "/api/login", {"username": self.username_entry.get().strip(), "password": self.password_entry.get()})
            self.api.token = result["token"]
            self.user = result
            self.config_data.update({"server_url": url, "username": result["username"]})
            self.save_config()
            if result.get("must_change_password"):
                self.force_password_change(self.password_entry.get())
            else:
                self.show_dashboard()
        except APIError as exc:
            detail = str(exc)
            if "404" in detail or "Not Found" in detail:
                detail += f"\n\nUse the private cloud DJ address {CLOUD_DJ_URL} and make sure Tailscale is connected."
            messagebox.showerror("Sign in failed", detail)

    def force_password_change(self, current):
        dialog = tk.Toplevel(self)
        dialog.title("Create a private password")
        dialog.geometry("460x310")
        dialog.resizable(False, False)
        dialog.configure(bg="#171020")
        dialog.transient(self); dialog.grab_set()
        tk.Label(dialog, text="REPLACE TEMPORARY PASSWORD", bg="#171020", fg="#f1e8fa", font=("Sans", 15, "bold")).pack(anchor="w", padx=24, pady=(24, 4))
        tk.Label(dialog, text="Use at least 10 characters. This is required before the dashboard opens.", bg="#171020", fg="#b9aabc", wraplength=410, justify="left").pack(anchor="w", padx=24)
        first = ttk.Entry(dialog, show="•"); second = ttk.Entry(dialog, show="•")
        tk.Label(dialog, text="New password", bg="#171020", fg="#e8dff0").pack(anchor="w", padx=24, pady=(18, 4)); first.pack(fill="x", padx=24)
        tk.Label(dialog, text="Confirm password", bg="#171020", fg="#e8dff0").pack(anchor="w", padx=24, pady=(12, 4)); second.pack(fill="x", padx=24)
        def submit():
            if first.get() != second.get():
                return messagebox.showerror("Passwords do not match", "Enter the same password twice.", parent=dialog)
            try:
                self.api.request("POST", "/api/change-password", {"current_password": current, "new_password": first.get()})
                dialog.destroy(); self.show_dashboard()
            except APIError as exc:
                messagebox.showerror("Could not change password", str(exc), parent=dialog)
        ttk.Button(dialog, text="Save New Password", command=submit).pack(fill="x", padx=24, pady=22, ipady=6)
        dialog.protocol("WM_DELETE_WINDOW", self.destroy)

    def show_dashboard(self):
        self.clear()
        root = tk.Frame(self, bg="#0e0915")
        root.pack(fill="both", expand=True)
        self.header(root, f"Signed in as {self.user.get('username')} · {self.user.get('role')}")
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=18, pady=16)
        self.tabs = {}
        for key, title in (("home","On Air"),("ops","Operations"),("schedule","Takeover Schedule"),("live","Live DJ"),("guests","Guest DJs"),("library","Catalog Library"),("ads","Station Ads"),("archive","Past Streams"),("test","Catalog Setup"),("review","Submissions"),("discover","SoundCloud Discovery"),("settings","Settings"),("setup","Setup & Help")):
            frame = tk.Frame(notebook, bg="#100b18", padx=18, pady=18)
            notebook.add(frame, text=title)
            self.tabs[key] = frame
        self.tab_builders = {
            "home": self.build_home,
            "ops": self.build_operations,
            "schedule": self.build_schedule,
            "live": self.build_live,
            "guests": self.build_guests,
            "library": self.build_library,
            "ads": self.build_ads,
            "archive": self.build_archive,
            "test": self.build_test_rotation,
            "review": self.build_review,
            "discover": self.build_discover,
            "settings": self.build_settings,
            "setup": self.build_setup,
        }
        self.built_tabs = {"home"}
        self.build_home()
        notebook.bind("<<NotebookTabChanged>>", self._build_selected_tab, add="+")
        self.refresh_status()

    def _build_selected_tab(self, event):
        notebook = event.widget
        selected = notebook.select()
        key = next((name for name, frame in self.tabs.items() if str(frame) == selected), None)
        if not key or key in self.built_tabs:
            return
        # Mark first so repeated tab events cannot initialize the same tab twice.
        self.built_tabs.add(key)
        self.tab_builders[key]()

    def build_home(self):
        f = self.tabs["home"]

        top = tk.Frame(f, bg="#100b18")
        top.pack(fill="x")
        self.onair_label = tk.Label(
            top, text="CHECKING TRANSMISSION", bg="#100b18", fg="#efe5f8",
            font=("Sans", 12, "bold"), justify="left", anchor="w"
        )
        self.onair_label.pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="Open Listener Site", command=self.open_listener).pack(side="right")
        ttk.Button(top, text="Refresh", command=self.refresh_status).pack(side="right", padx=8)

        now = tk.Frame(f, bg="#1b1127", padx=24, pady=20, highlightbackground="#6f3a9b", highlightthickness=1)
        now.pack(fill="x", pady=(16, 14))
        tk.Label(now, text="NOW TRANSMITTING", bg="#1b1127", fg="#c77dff", font=("Sans", 9, "bold")).pack(anchor="w")
        self.now_title = tk.Label(now, text="Waiting for server…", bg="#1b1127", fg="#ffffff", font=("Sans", 25, "bold"), anchor="w")
        self.now_title.pack(fill="x", pady=(5, 0))
        self.now_artist = tk.Label(now, text="AllThings140Radio", bg="#1b1127", fg="#bdaec9", font=("Sans", 13), anchor="w")
        self.now_artist.pack(fill="x", pady=(2, 12))
        self.progress = ttk.Progressbar(now, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        meta = tk.Frame(now, bg="#1b1127")
        meta.pack(fill="x", pady=(7, 0))
        self.time_label = tk.Label(meta, text="0:00 / 0:00", bg="#1b1127", fg="#8f8199")
        self.time_label.pack(side="left")
        self.next_label = tk.Label(meta, text="NEXT: —", bg="#1b1127", fg="#bdaec9")
        self.next_label.pack(side="right")

        transport = tk.Frame(f, bg="#100b18")
        transport.pack(fill="x", pady=(0, 14))
        ttk.Button(transport, text="⏮ PREVIOUS", command=lambda: self.autodj_control("previous")).pack(side="left")
        ttk.Button(transport, text="↻ RESTART SONG", command=lambda: self.autodj_control("restart")).pack(side="left", padx=8)
        ttk.Button(transport, text="NEXT ⏭", command=lambda: self.autodj_control("next")).pack(side="left")
        ttk.Button(transport, text="🔀 RESHUFFLE FULL QUEUE", command=self.reshuffle_autodj).pack(side="left", padx=8)
        self.stats_label = tk.Label(transport, text="", bg="#100b18", fg="#9f91aa", justify="right")
        self.stats_label.pack(side="right")

        health = tk.Frame(f, bg="#15101d", padx=12, pady=10, highlightbackground="#362542", highlightthickness=1)
        health.pack(fill="x", pady=(0, 12))
        self.health_labels = {}
        for key in ("SERVER", "ICECAST", "AUTODJ", "ENCODER", "DECODER", "LIVE RELAY", "SILENCE", "DISK", "ADS", "RECORDING", "STORAGE"):
            label = tk.Label(health, text=f"{key}: CHECKING", bg="#15101d", fg="#9f91aa", font=("Sans", 9, "bold"), padx=8, pady=4)
            label.pack(side="left")
            self.health_labels[key] = label

        queue_head = tk.Frame(f, bg="#100b18")
        queue_head.pack(fill="x")
        self.queue_count_label = tk.Label(queue_head, text="0 PLAYABLE APPROVED TRACKS", bg="#100b18", fg="#d8b7ff", font=("Sans", 12, "bold"))
        self.queue_count_label.pack(side="left")
        tk.Label(queue_head, text="Every listener hears this same server-controlled feed", bg="#100b18", fg="#8f8199").pack(side="right")

        queue_shell = tk.Frame(f, bg="#15101d", highlightbackground="#362542", highlightthickness=1)
        queue_shell.pack(fill="both", expand=True, pady=(8, 0))
        self.queue_tree = ttk.Treeview(
            queue_shell,
            columns=("position", "title", "artist", "state"),
            show="headings",
            selectmode="browse",
        )
        for key, title, width, anchor in (
            ("position", "#", 75, "center"),
            ("title", "Track", 500, "w"),
            ("artist", "Artist", 280, "w"),
            ("state", "Status", 100, "center"),
        ):
            self.queue_tree.heading(key, text=title)
            self.queue_tree.column(key, width=width, anchor=anchor, stretch=key in {"title", "artist"})
        scrollbar = ttk.Scrollbar(queue_shell, orient="vertical", command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=scrollbar.set)
        self.queue_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.queue_tree.tag_configure("current", background="#2a1739", foreground="#ffffff")
        self.queue_tree.bind("<Double-1>", lambda _e: self.play_selected_home())

    def build_operations(self):
        f = self.tabs["ops"]
        head = tk.Frame(f, bg="#100b18")
        head.pack(fill="x")
        tk.Label(head, text="STATION OPERATIONS", bg="#100b18", fg="#efe5f8", font=("Sans", 14, "bold")).pack(side="left")
        ttk.Button(head, text="Refresh Events", command=self.refresh_operations).pack(side="right")
        ttk.Button(head, text="Rotation Audit", command=self.refresh_rotation_audit).pack(side="right", padx=8)
        self.ops_summary = tk.Label(f, text="Loading live health…", bg="#171020", fg="#d8cbe2", justify="left", anchor="w", padx=16, pady=14)
        self.ops_summary.pack(fill="x", pady=(14, 12))
        self.rotation_audit_label = tk.Label(f, text="Rotation audit: not checked", bg="#15101d", fg="#9f91aa", justify="left", anchor="w", padx=16, pady=10)
        self.rotation_audit_label.pack(fill="x", pady=(0, 12))
        self.ops_tree = ttk.Treeview(f, columns=("time", "event", "detail"), show="headings")
        for key, title, width in (("time", "Time", 165), ("event", "Operational event", 260), ("detail", "Detail", 650)):
            self.ops_tree.heading(key, text=title)
            self.ops_tree.column(key, width=width, anchor="w")
        self.ops_tree.pack(fill="both", expand=True)
        self.refresh_operations()

    def refresh_rotation_audit(self):
        if not hasattr(self, "rotation_audit_label"):
            return
        try:
            result = self.api.request("GET", "/api/rotation-audit")
            repeats = ", ".join(f"{row['artist']} ({row['plays']})" for row in result.get("repeated_artists_last_24h", [])) or "none"
            self.rotation_audit_label.config(text=(f"Rotation audit • {result.get('approved_tracks', 0)} playable approved / "
                f"{result.get('missing_approved_tracks', 0)} missing • {result.get('plays_last_24h', 0)} plays in 24h • "
                f"{result.get('unique_tracks_last_24h', 0)} unique tracks\nRepeated artists: {repeats}"), fg="#d8cbe2")
        except Exception as exc:
            self.rotation_audit_label.config(text=f"Rotation audit unavailable: {exc}", fg="#ff9ca8")

    def refresh_operations(self):
        if not hasattr(self, "ops_tree"):
            return
        try:
            payload = self.api.request("GET", "/api/events?limit=100")
            self.ops_tree.delete(*self.ops_tree.get_children())
            for index, event in enumerate(reversed(payload.get("events", []))):
                when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(event.get("ts", 0)))) if event.get("ts") else "—"
                name = str(event.get("event", "unknown")).replace("_", " ").upper()
                detail = " • ".join(f"{key}={value}" for key, value in event.items() if key not in {"ts", "event"})
                self.ops_tree.insert("", "end", iid=f"event-{index}", values=(when, name, detail[:900]))
        except Exception as exc:
            self.ops_tree.delete(*self.ops_tree.get_children())
            self.ops_tree.insert("", "end", values=("—", "EVENT LOG UNAVAILABLE", str(exc)))

    def build_schedule(self):
        f = self.tabs["schedule"]
        tk.Label(f, text="TAKEOVER SCHEDULER", bg="#100b18", fg="#efe5f8", font=("Sans", 14, "bold")).pack(anchor="w")
        tk.Label(f, text="Add a takeover yourself or create a private form link for the artist. Submitted events publish automatically to the listener site.", bg="#100b18", fg="#a99bad", wraplength=900, justify="left").pack(anchor="w", pady=(4, 12))
        form = tk.Frame(f, bg="#171020", padx=14, pady=14); form.pack(fill="x")
        self.takeover_fields = {}
        fields = (("artist","Artist / DJ name"),("title","Show title"),("details","Details"),("instagram","Instagram URL"),("twitch","Twitch URL"),("soundcloud","SoundCloud URL"),("youtube","YouTube URL"),("x","X / Twitter URL"))
        for index,(key,label) in enumerate(fields):
            row,col=divmod(index,2); tk.Label(form,text=label,bg="#171020",fg="#cdbed6").grid(row=row,column=col*2,sticky="e",padx=(8,5),pady=4)
            entry=ttk.Entry(form,width=34); entry.grid(row=row,column=col*2+1,sticky="ew",pady=4); self.takeover_fields[key]=entry
        row=4
        tk.Label(form,text="Date",bg="#171020",fg="#cdbed6").grid(row=row,column=0,sticky="e",padx=(8,5),pady=4)
        date_box=tk.Frame(form,bg="#171020");date_box.grid(row=row,column=1,sticky="ew")
        self.takeover_date=tk.StringVar(value=(dt.date.today()+dt.timedelta(days=1)).isoformat())
        ttk.Entry(date_box,textvariable=self.takeover_date,state="readonly").pack(side="left",fill="x",expand=True)
        ttk.Button(date_box,text="CALENDAR",command=self.pick_takeover_date).pack(side="left",padx=(6,0))
        tk.Label(form,text="Timezone",bg="#171020",fg="#cdbed6").grid(row=row,column=2,sticky="e",padx=(8,5),pady=4)
        self.takeover_timezone=ttk.Combobox(form,values=TAKEOVER_TIMEZONES,state="readonly",width=31);self.takeover_timezone.set("America/Los_Angeles");self.takeover_timezone.grid(row=row,column=3,sticky="ew",pady=4)
        row=5
        tk.Label(form,text="Start time",bg="#171020",fg="#cdbed6").grid(row=row,column=0,sticky="e",padx=(8,5),pady=4)
        self.takeover_start=ttk.Combobox(form,values=TAKEOVER_TIMES,state="readonly",width=31);self.takeover_start.set("2:00 PM");self.takeover_start.grid(row=row,column=1,sticky="ew",pady=4)
        tk.Label(form,text="End time",bg="#171020",fg="#cdbed6").grid(row=row,column=2,sticky="e",padx=(8,5),pady=4)
        self.takeover_end=ttk.Combobox(form,values=TAKEOVER_TIMES,state="readonly",width=31);self.takeover_end.set("3:00 PM");self.takeover_end.grid(row=row,column=3,sticky="ew",pady=4)
        row=6
        tk.Label(form,text="Artist logo (optional)",bg="#171020",fg="#cdbed6").grid(row=row,column=0,sticky="e",padx=(8,5),pady=4)
        self.takeover_logo_path=tk.StringVar()
        logo_box=tk.Frame(form,bg="#171020");logo_box.grid(row=row,column=1,columnspan=3,sticky="ew")
        ttk.Entry(logo_box,textvariable=self.takeover_logo_path,state="readonly").pack(side="left",fill="x",expand=True)
        ttk.Button(logo_box,text="CHOOSE IMAGE",command=self.choose_takeover_logo).pack(side="left",padx=(6,0))
        form.columnconfigure(1,weight=1); form.columnconfigure(3,weight=1)
        buttons=tk.Frame(f,bg="#100b18");buttons.pack(fill="x",pady=10)
        ttk.Button(buttons,text="PUBLISH TAKEOVER",command=self.publish_takeover).pack(side="left")
        ttk.Button(buttons,text="CREATE ARTIST FORM LINK",command=self.create_takeover_form).pack(side="left",padx=8)
        ttk.Button(buttons,text="REFRESH",command=self.refresh_takeovers).pack(side="left")
        ttk.Button(buttons,text="APPROVE SELECTED",command=lambda:self.set_takeover_status("published")).pack(side="left",padx=(8,0))
        ttk.Button(buttons,text="REJECT SELECTED",command=lambda:self.set_takeover_status("rejected")).pack(side="left",padx=(8,0))
        self.takeover_feedback=tk.Label(buttons,text="",bg="#100b18",fg="#78e9ba");self.takeover_feedback.pack(side="left",padx=12)
        self.takeover_tree=ttk.Treeview(f,columns=("status","artist","title","start","end","socials"),show="headings",height=12)
        for key,title,width in (("status","Status",95),("artist","Artist",170),("title","Show",210),("start","Starts",150),("end","Ends",150),("socials","Socials",180)):
            self.takeover_tree.heading(key,text=title);self.takeover_tree.column(key,width=width,anchor="w")
        self.takeover_tree.pack(fill="both",expand=True,pady=(4,8))
        ttk.Button(f,text="DELETE SELECTED",command=self.delete_takeover).pack(anchor="e")
        self.refresh_takeovers()

    def _takeover_payload(self):
        values={key:entry.get().strip() for key,entry in self.takeover_fields.items()}
        try:
            zone=ZoneInfo(self.takeover_timezone.get())
            date=dt.date.fromisoformat(self.takeover_date.get())
            start_time=dt.datetime.strptime(self.takeover_start.get(),"%I:%M %p").time()
            end_time=dt.datetime.strptime(self.takeover_end.get(),"%I:%M %p").time()
            start_dt=dt.datetime.combine(date,start_time,zone)
            end_dt=dt.datetime.combine(date,end_time,zone)
            if end_dt<=start_dt:end_dt+=dt.timedelta(days=1)
            starts,ends=int(start_dt.timestamp()),int(end_dt.timestamp())
        except ValueError as exc:
            raise APIError("Choose a date, start time, end time, and timezone") from exc
        socials=[{"platform":key.title() if key!="x" else "X","url":values[key]} for key in ("instagram","twitch","soundcloud","youtube","x") if values[key]]
        payload={"artist":values["artist"],"title":values["title"],"details":values["details"],"starts_at":starts,"ends_at":ends,"timezone":self.takeover_timezone.get(),"socials":socials}
        if self.takeover_logo_path.get():
            path=Path(self.takeover_logo_path.get());mime=mimetypes.guess_type(path.name)[0] or ""
            if mime not in {"image/png","image/jpeg","image/webp"} or path.stat().st_size>2*1024*1024:raise APIError("Logo must be a PNG, JPEG, or WebP smaller than 2 MB")
            payload["logo_data"]=f"data:{mime};base64,"+base64.b64encode(path.read_bytes()).decode()
        return payload

    def choose_takeover_logo(self):
        path=filedialog.askopenfilename(parent=self,title="Choose artist logo",filetypes=[("Images","*.png *.jpg *.jpeg *.webp")])
        if path:self.takeover_logo_path.set(path)

    def pick_takeover_date(self):
        try:selected=dt.date.fromisoformat(self.takeover_date.get())
        except ValueError:selected=dt.date.today()
        popup=tk.Toplevel(self);popup.title("Choose takeover date");popup.transient(self);popup.grab_set();popup.configure(bg="#100b18")
        current=[selected.year,selected.month]
        header=tk.Label(popup,bg="#100b18",fg="#fff",font=("Sans",12,"bold"));header.grid(row=0,column=1,columnspan=5,pady=8)
        body=tk.Frame(popup,bg="#100b18");body.grid(row=1,column=0,columnspan=7,padx=8,pady=(0,8))
        def draw():
            for child in body.winfo_children():child.destroy()
            header.config(text=f"{calendar.month_name[current[1]]} {current[0]}")
            for col,name in enumerate(("M","T","W","T","F","S","S")):tk.Label(body,text=name,bg="#100b18",fg="#c58bea",width=4).grid(row=0,column=col)
            for r,week in enumerate(calendar.monthcalendar(*current),1):
                for c,day in enumerate(week):
                    if day:ttk.Button(body,text=str(day),width=3,command=lambda d=day:self._set_takeover_date(popup,current[0],current[1],d)).grid(row=r,column=c,padx=2,pady=2)
        def shift(delta):
            month=current[1]+delta;current[:]=[current[0]+(month-1)//12,(month-1)%12+1];draw()
        ttk.Button(popup,text="‹",command=lambda:shift(-1)).grid(row=0,column=0,padx=8)
        ttk.Button(popup,text="›",command=lambda:shift(1)).grid(row=0,column=6,padx=8);draw()

    def _set_takeover_date(self,popup,year,month,day):
        self.takeover_date.set(dt.date(year,month,day).isoformat());popup.destroy()

    def publish_takeover(self):
        try:
            self.api.request("POST","/api/takeovers",self._takeover_payload())
            self.takeover_feedback.config(text="Takeover published to the listener site.")
            self.refresh_takeovers()
        except APIError as exc: messagebox.showerror("Could not schedule takeover",str(exc),parent=self)

    def create_takeover_form(self):
        label=self.takeover_fields["artist"].get().strip() or "Guest DJ"
        try:
            result=self.api.request("POST","/api/takeover-invites",{"label":label,"expires_days":14})
            self.copy_text(result["link"])
            self.takeover_feedback.config(text="Private artist form link copied to clipboard.")
            messagebox.showinfo("Artist form link copied",f"Send this private link to {label}:\n\n{result['link']}\n\nIt expires in 14 days and can be submitted once.",parent=self)
        except APIError as exc: messagebox.showerror("Could not create artist form",str(exc),parent=self)

    def refresh_takeovers(self):
        if not hasattr(self,"takeover_tree"): return
        try:
            rows=self.api.request("GET","/api/takeovers").get("takeovers",[]);self.takeover_tree.delete(*self.takeover_tree.get_children())
            for row in rows:
                socials=", ".join(link.get("platform","") for link in row.get("socials",[]))
                self.takeover_tree.insert("","end",iid=f"takeover-{row['id']}",values=(str(row.get("status","published")).upper(),row["artist"],row.get("title","") or "—",time.strftime("%Y-%m-%d %H:%M",time.localtime(row["starts_at"])),time.strftime("%Y-%m-%d %H:%M",time.localtime(row["ends_at"])),socials or "—"))
        except Exception as exc: self.takeover_feedback.config(text=f"Schedule unavailable: {exc}",fg="#ff7fa9")

    def delete_takeover(self):
        selected=self.takeover_tree.selection()
        if not selected:return messagebox.showinfo("Select a takeover","Click a takeover in the list first.",parent=self)
        takeover_id=int(selected[0].split("-",1)[1])
        if messagebox.askyesno("Delete takeover?","Remove this takeover from the public schedule?",parent=self):
            try:self.api.request("POST","/api/takeovers/delete",{"id":takeover_id});self.takeover_feedback.config(text="Takeover deleted from the app and public site.",fg="#78e9ba");self.refresh_takeovers()
            except APIError as exc:messagebox.showerror("Could not delete takeover",str(exc),parent=self)

    def set_takeover_status(self,status):
        selected=self.takeover_tree.selection()
        if not selected:return messagebox.showinfo("Select a takeover","Click a takeover request in the list first.",parent=self)
        takeover_id=int(selected[0].split("-",1)[1]);verb="approve and publish" if status=="published" else "reject"
        if not messagebox.askyesno(f"{verb.title()} takeover?",f"Are you sure you want to {verb} this takeover?",parent=self):return
        try:
            result=self.api.request("POST","/api/takeovers/status",{"id":takeover_id,"status":status})
            if status=="published" and result.get("takeover"):
                request=urllib.request.Request("https://allthings140radio.online/api/public/takeover-alert",data=json.dumps({"id":takeover_id}).encode(),method="POST",headers={"Content-Type":"application/json"})
                try:urllib.request.urlopen(request,timeout=20).read()
                except Exception:pass
            self.takeover_feedback.config(text="Takeover published and subscriber alert started." if status=="published" else "Takeover request rejected.",fg="#78e9ba");self.refresh_takeovers()
        except APIError as exc:messagebox.showerror("Could not update takeover",str(exc),parent=self)
        self.bind_all("<Button-5>", self._scroll_rotation_with_mouse, add="+")
        self.render_rotation([])

    def _scroll_rotation_with_mouse(self, event):
        """Scroll the rotation whenever the pointer is anywhere over its panel."""
        if not hasattr(self, "queue_canvas"):
            return None
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return None
        current = widget
        while current is not None and current is not self.queue_canvas:
            try:
                current = current.master
            except (AttributeError, tk.TclError):
                return None
        if current is not self.queue_canvas:
            return None
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = int(getattr(event, "delta", 0) or 0)
            if not delta:
                return None
            units = -max(-6, min(6, int(delta / 120) or (1 if delta > 0 else -1)))
        self.queue_canvas.yview_scroll(units, "units")
        return "break"

    @staticmethod
    def format_time(seconds):
        try:
            value = max(0, int(float(seconds or 0)))
        except (TypeError, ValueError):
            value = 0
        return f"{value // 60}:{value % 60:02d}"

    def render_rotation(self, rows):
        if not hasattr(self, "queue_tree"):
            return
        # The On Air queue is the complete server rotation, not a truncated preview.
        display_rows = list(rows)
        if rows and not any(row.get("is_current") for row in display_rows):
            current = next((row for row in rows if row.get("is_current")), None)
            if current:
                display_rows = [current] + display_rows[:-1]
        signature = tuple(
            (
                int(row.get("id") or 0),
                str(row.get("title") or ""),
                str(row.get("artist") or ""),
                bool(row.get("is_current")),
            )
            for row in display_rows
        ) + (("total", len(rows)),)
        if signature == self.rotation_render_signature:
            return
        self.rotation_render_signature = signature
        selected = self.queue_tree.selection()
        selected_id = selected[0] if selected else None
        self.queue_tree.delete(*self.queue_tree.get_children())
        self.home_queue_rows = {}
        if not rows:
            return
        for index, row in enumerate(display_rows, 1):
            track_id = int(row["id"])
            self.home_queue_rows[track_id] = row
            current = bool(row.get("is_current"))
            iid = str(track_id)
            self.queue_tree.insert(
                "", "end", iid=iid,
                values=("ON AIR" if current else index, row.get("title") or "Untitled", row.get("artist") or "Unknown artist", "RESTART" if current else "PLAY NOW"),
                tags=("current",) if current else (),
            )
        if selected_id and self.queue_tree.exists(selected_id):
            self.queue_tree.selection_set(selected_id)

    def play_selected_home(self):
        if not hasattr(self, "queue_tree"):
            return
        selected = self.queue_tree.selection()
        if not selected:
            return messagebox.showinfo("Select a track", "Select a queue track first, then double-click it to play.", parent=self)
        row = self.home_queue_rows.get(int(selected[0]))
        if row:
            self.autodj_play_track(row["id"], row.get("title", "track"), restart=bool(row.get("is_current")))

    def autodj_control(self, action):
        labels = {"next": "Skipping to the next catalog song…", "previous": "Returning to the previous catalog song…", "restart": "Restarting the current song…"}
        try:
            self.api.request("POST", f"/api/autodj/{action}", {})
            self.onair_label.config(text=labels.get(action, "Updating rotation…"), fg="#d7b1ff")
            self.after(700, self.refresh_status)
        except APIError as exc:
            messagebox.showerror("Radio control failed", str(exc))

    def reshuffle_autodj(self):
        if not messagebox.askyesno("Reshuffle full queue?", "Create a fresh random order for all approved tracks?\n\nThe current song will hand off to the new rotation for every listener.", parent=self):
            return
        try:
            self.api.request("POST", "/api/autodj/reshuffle", {})
            self.onair_label.config(text="Reshuffling all approved tracks…", fg="#d7b1ff")
            self.after(700, self.refresh_status)
        except APIError as exc:
            messagebox.showerror("Reshuffle failed", str(exc), parent=self)

    def autodj_play_track(self, track_id, title, restart=False):
        if restart:
            return self.autodj_control("restart")
        if not messagebox.askyesno("Play this song now?", f"Immediately switch the shared 24/7 feed to:\n\n{title}\n\nAll connected listeners will hear the change."):
            return
        try:
            self.api.request("POST", "/api/autodj/play-track", {"track_id": int(track_id)})
            self.onair_label.config(text=f"Switching transmission to {title}…", fg="#d7b1ff")
            self.after(700, self.refresh_status)
        except APIError as exc:
            messagebox.showerror("Could not play track", str(exc))

    def build_live(self):
        f = self.tabs["live"]
        top = tk.Frame(f, bg="#100b18"); top.pack(fill="x")
        tk.Label(top, text="LIVE QUEUE", bg="#100b18", fg="#d8b7ff", font=("Sans", 12, "bold")).pack(side="left")
        ttk.Button(top, text="Add Audio", command=self.add_live_tracks).pack(side="right")
        ttk.Button(top, text="Start From Selected", command=self.start_from_selected).pack(side="right", padx=6)
        ttk.Button(top, text="Clear", command=self.clear_live_tracks).pack(side="right", padx=6)
        ttk.Button(top, text="Remove", command=self.remove_live_track).pack(side="right", padx=6)
        ttk.Button(top, text="Move Down", command=lambda: self.move_live_track(1)).pack(side="right", padx=6)
        ttk.Button(top, text="Move Up", command=lambda: self.move_live_track(-1)).pack(side="right", padx=6)
        self.live_list = tk.Listbox(f, bg="#181121", fg="#ede4f4", selectbackground="#6e3aa8", relief="flat")
        self.live_list.pack(fill="both", expand=True, pady=12)
        self.live_list.bind("<Double-1>", lambda _e: self.start_from_selected())
        self.live_track_label = tk.Label(f, text="Current live track: —", bg="#100b18", fg="#b9abca")
        self.live_track_label.pack(anchor="w", pady=(0, 10))
        controls = tk.Frame(f, bg="#100b18"); controls.pack(fill="x")
        self.mix_mic = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Mix microphone with music", variable=self.mix_mic).pack(side="left")
        tk.Label(controls, text="Mic source", bg="#100b18", fg="#c8b9d2").pack(side="left", padx=(18,4))
        self.mic_source = ttk.Combobox(controls, width=30, state="readonly")
        self.mic_source.pack(side="left")
        ttk.Button(controls, text="Refresh", command=self.refresh_mic_sources).pack(side="left", padx=(5, 0))
        self.refresh_mic_sources()
        buttons = tk.Frame(f, bg="#100b18"); buttons.pack(fill="x", pady=(14,0))
        self.go_live_btn = ttk.Button(buttons, text="GO LIVE", command=self.toggle_live)
        self.go_live_btn.pack(side="left", ipadx=28, ipady=8)
        ttk.Button(buttons, text="CONNECT TRAKTOR", command=self.show_traktor_setup).pack(side="left", padx=10)
        self.mute_btn = ttk.Button(buttons, text="Mute Mic", command=self.toggle_mic_mute, state="disabled")
        self.mute_btn.pack(side="left", padx=10)
        self.live_state = tk.Label(buttons, text="Offline", bg="#100b18", fg="#a99ab3", justify="left", anchor="w")
        self.live_state.pack(side="left", padx=12)
        tk.Label(f, text="Live DJ now streams one queue track at a time so the app can automatically continue to the next song instead of dropping after the first file. Double-click a queue item or use Start From Selected to begin from any song.", bg="#100b18", fg="#998ba4", wraplength=860, justify="left").pack(anchor="w", pady=(16,0))

    def show_traktor_setup(self):
        try:
            cfg = self.api.request("GET", "/api/traktor-config")
        except APIError as exc:
            return messagebox.showerror("Could not prepare Traktor", str(exc), parent=self)
        dialog = tk.Toplevel(self)
        dialog.title("Connect Traktor to AllThings140Radio")
        dialog.configure(bg="#100b18")
        dialog.resizable(False, False)
        panel = tk.Frame(dialog, bg="#100b18", padx=26, pady=22)
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text="TRAKTOR BROADCAST SETUP", bg="#100b18", fg="#e3c5ff", font=("Sans", 15, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        tk.Label(panel, text="In Traktor Preferences → Broadcasting, select Default proxy and enter:", bg="#100b18", fg="#b9abca").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))
        fields = (("Address", cfg["host"]), ("Port", str(cfg["port"])), ("Mount path", cfg["mount"]), ("Password", cfg["password"]), ("Format", cfg["format"]))
        for row, (label, value) in enumerate(fields, 2):
            tk.Label(panel, text=label, bg="#100b18", fg="#d8cde0").grid(row=row, column=0, sticky="e", padx=(0, 10), pady=4)
            entry = ttk.Entry(panel, width=43, show="•" if label == "Password" else "")
            entry.insert(0, value); entry.configure(state="readonly")
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            ttk.Button(panel, text="COPY", command=lambda text=value: self.copy_text(text)).grid(row=row, column=2, padx=(8, 0), pady=4)
        tk.Label(panel, text="Leave Stream URL blank. Stream name, description, and genre are optional.\nPress Broadcast in Traktor; AutoDJ hands over only after Traktor connects and returns automatically if it drops.", bg="#100b18", fg="#a99ab3", justify="left", wraplength=560).grid(row=7, column=0, columnspan=3, sticky="w", pady=(14, 12))
        ttk.Button(panel, text="END TRAKTOR SESSION", command=lambda: self.end_traktor_session(dialog)).grid(row=8, column=0, columnspan=2, sticky="w")
        ttk.Button(panel, text="CLOSE", command=dialog.destroy).grid(row=8, column=2, sticky="e")
        dialog.transient(self); dialog.grab_set()

    def copy_text(self, text):
        self.clipboard_clear(); self.clipboard_append(str(text)); self.update_idletasks()

    def end_traktor_session(self, dialog=None):
        try:
            self.api.request("POST", "/api/traktor-ended", {})
            self.live_state.config(text="Traktor session ended — AutoDJ resumed", fg="#a99ab3")
            if dialog:
                dialog.destroy()
        except APIError as exc:
            messagebox.showerror("Could not end Traktor session", str(exc), parent=dialog or self)

    def refresh_mic_sources(self):
        saved = self.config_data.get("mic_source", "default") or "default"
        values = []
        try:
            result = subprocess.run(["pactl", "list", "short", "sources"], capture_output=True, text=True, timeout=3, check=False)
            for line in result.stdout.splitlines():
                fields = line.split()
                if len(fields) >= 2 and not fields[1].endswith(".monitor"):
                    values.append(fields[1])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        if saved not in values:
            values.insert(0, saved)
        if not values:
            values = ["default"]
        self.mic_source["values"] = values
        self.mic_source.set(saved if saved in values else values[0])

    def add_live_tracks(self):
        files = filedialog.askopenfilenames(title="Add tracks to live queue", filetypes=AUDIO_TYPES)
        for filename in files:
            path = Path(filename)
            self.live_playlist.append(path); self.live_list.insert("end", path.name)


    def start_from_selected(self):
        selected = self.live_list.curselection()
        if selected:
            self.live_current_index = int(selected[0])
            self.live_track_label.config(text=f"Current live track: {self.live_playlist[self.live_current_index].name}")
            if not (self.live_process and self.live_process.poll() is None):
                self.toggle_live(start_index=self.live_current_index)
        elif self.live_playlist:
            self.live_current_index = 0
            self.live_track_label.config(text=f"Current live track: {self.live_playlist[0].name}")
            if not (self.live_process and self.live_process.poll() is None):
                self.toggle_live(start_index=0)
        else:
            messagebox.showinfo("No queue", "Add at least one track to the live queue first.")

    def remove_live_track(self):
        if self.live_process and self.live_process.poll() is None:
            return messagebox.showwarning("Currently live", "End the current broadcast before changing the active queue.")
        selected = list(self.live_list.curselection())
        if not selected:
            return
        for index in reversed(selected):
            del self.live_playlist[index]
            self.live_list.delete(index)

    def move_live_track(self, direction):
        if self.live_process and self.live_process.poll() is None:
            return messagebox.showwarning("Currently live", "End the current broadcast before reordering the active queue.")
        selected = self.live_list.curselection()
        if len(selected) != 1:
            return messagebox.showinfo("Select one track", "Select one queue item to move.")
        index = selected[0]
        target = index + direction
        if target < 0 or target >= len(self.live_playlist):
            return
        self.live_playlist[index], self.live_playlist[target] = self.live_playlist[target], self.live_playlist[index]
        label = self.live_list.get(index)
        self.live_list.delete(index)
        self.live_list.insert(target, label)
        self.live_list.selection_set(target)
        self.live_list.see(target)

    def clear_live_tracks(self):
        if self.live_process and self.live_process.poll() is None:
            return messagebox.showwarning("Currently live", "End the broadcast before clearing the queue.")
        self.live_playlist.clear(); self.live_list.delete(0, "end")

    def ffmpeg_live_command(self, cfg, track: Path | None = None):
        password = urllib.parse.quote(cfg["source_password"], safe="")
        target = f"icecast://source:{password}@{cfg['host']}:{cfg['port']}{cfg['mount']}"
        out = ["-ar","44100","-ac","2","-codec:a","libmp3lame","-b:a",f"{cfg.get('bitrate',128)}k","-content_type","audio/mpeg","-ice_name",f"AllThings140Radio Live — {self.user.get('username','DJ')}","-ice_description","Live DJ takeover","-f","mp3",target]
        mic = self.mic_source.get().strip() or "default"
        base = ["ffmpeg","-hide_banner","-loglevel","warning","-nostdin","-re"]
        if track is not None:
            cmd = base + ["-i", str(track)]
            if self.mix_mic.get():
                cmd += ["-thread_queue_size","1024","-f","pulse","-i",mic,"-filter_complex","[0:a:0]aresample=44100,volume=0.92[m];[1:a]aresample=44100,volume=1.0[voice];[m][voice]amix=inputs=2:duration=first:dropout_transition=2[out]","-map","[out]"]
            else:
                cmd += ["-map","0:a:0"]
            return cmd + out
        if not self.mix_mic.get():
            raise APIError("Add at least one track or enable microphone-only broadcasting.")
        return base + ["-f","pulse","-i",mic] + out

    def _select_live_row(self, index: int):
        if not hasattr(self, "live_list"):
            return
        self.live_list.selection_clear(0, "end")
        if 0 <= index < self.live_list.size():
            self.live_list.selection_set(index)
            self.live_list.see(index)
            name = self.live_list.get(index)
            self.live_track_label.config(text=f"Current live track: {name}")

    def _run_live_queue(self, cfg, start_index: int = 0):
        final_text = "Broadcast ended"
        try:
            if self.live_playlist:
                index = max(0, min(start_index, len(self.live_playlist) - 1))
                while not self.live_stop_requested and index < len(self.live_playlist):
                    track = self.live_playlist[index]
                    self.live_current_index = index
                    self.post_ui(lambda i=index: self._select_live_row(i))
                    self.post_ui(lambda name=track.name: self.live_state.config(text=f"● LIVE — streaming {name}", fg="#8ff0b6"))
                    proc = subprocess.Popen(self.ffmpeg_live_command(cfg, track), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                    self.live_process = proc
                    code = proc.wait()
                    err = proc.stderr.read()[-1200:] if proc.stderr else ""
                    self.live_process = None
                    if self.live_stop_requested:
                        final_text = "Broadcast ended"
                        break
                    if code == 0:
                        index += 1
                        if index < len(self.live_playlist):
                            self.post_ui(lambda next_name=self.live_playlist[index].name: self.live_state.config(text=f"Track finished. Loading {next_name}…", fg="#ffcb6b"))
                            continue
                        final_text = "Queue finished"
                        break
                    index += 1
                    if index < len(self.live_playlist):
                        self.post_ui(lambda next_name=self.live_playlist[index].name: self.live_state.config(text=f"Track ended unexpectedly. Switching to {next_name}…", fg="#ffcb6b"))
                        continue
                    final_text = f"Broadcast stopped\n{err}" if err else "Broadcast stopped"
                    break
            else:
                proc = subprocess.Popen(self.ffmpeg_live_command(cfg, None), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                self.live_process = proc
                code = proc.wait()
                err = proc.stderr.read()[-1200:] if proc.stderr else ""
                self.live_process = None
                final_text = "Broadcast ended" if self.live_stop_requested else ("Broadcast stopped\n" + err if code else "Broadcast ended")
        except Exception as exc:
            final_text = f"Could not stay live\n{exc}"
        self.post_ui(lambda t=final_text: self.live_finished(t))

    def toggle_live(self, start_index: int | None = None):
        if self.live_process and self.live_process.poll() is None:
            self.live_stop_requested = True
            self.live_process.terminate()
            try: self.live_process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.live_process.kill()
            return
        try:
            cfg = self.api.request("GET", "/api/broadcast-config")
            self.config_data["mic_source"] = self.mic_source.get().strip() or "default"; self.save_config()
            self.live_stop_requested = False
            if start_index is None:
                selected = self.live_list.curselection() if hasattr(self, "live_list") else ()
                start_index = int(selected[0]) if selected else 0
            self.go_live_btn.config(text="END BROADCAST")
            self.mute_btn.config(state="normal")
            self.live_state.config(text="Connecting live source…", fg="#ffcb6b")
            self.live_runner_thread = threading.Thread(target=self._run_live_queue, args=(cfg, start_index), daemon=True)
            self.live_runner_thread.start()
        except (APIError, FileNotFoundError) as exc:
            messagebox.showerror("Could not go live", str(exc))

    def watch_live(self):
        pass

    def live_finished(self, text):
        self.live_process = None
        self.live_stop_requested = False
        try:
            self.api.request("POST", "/api/broadcast-ended", {})
        except Exception:
            pass
        self.go_live_btn.config(text="GO LIVE")
        self.mute_btn.config(state="disabled", text="Mute Mic")
        self.live_state.config(text=text, fg="#a99ab3")
        if not self.live_playlist:
            self.live_track_label.config(text="Current live track: —")

    def toggle_mic_mute(self):

        source = self.mic_source.get().strip() or "default"
        if source == "default":
            source = "@DEFAULT_SOURCE@"
        currently_muting = self.mute_btn.cget("text") == "Mute Mic"
        value = "1" if currently_muting else "0"
        proc = subprocess.run(["pactl","set-source-mute",source,value], capture_output=True, text=True)
        if proc.returncode:
            messagebox.showerror("Microphone control failed", proc.stderr or "Check the microphone source name.")
        else:
            self.mute_btn.config(text="Unmute Mic" if currently_muting else "Mute Mic")

    def build_guests(self):
        f = self.tabs["guests"]
        tk.Label(f, text="PRIVATE GUEST STUDIO", bg="#100b18", fg="#e3c5ff", font=("Sans", 17, "bold")).pack(anchor="w")
        tk.Label(
            f, text="Create a private expiring link for a guest DJ. They select their Traktor/controller loopback input, test levels, and wait for your approval before taking over the station. AutoDJ returns automatically if their connection drops.",
            bg="#100b18", fg="#aa9bb5", wraplength=1000, justify="left"
        ).pack(anchor="w", pady=(5, 16))
        tools = tk.Frame(f, bg="#100b18")
        tools.pack(fill="x")
        ttk.Button(tools, text="CREATE GUEST INVITE", command=self.create_guest_invite).pack(side="left")
        ttk.Button(tools, text="CREATE TRAKTOR INVITE", command=self.create_traktor_invite).pack(side="left", padx=8)
        ttk.Button(tools, text="CREATE MIXXX INVITE", command=self.create_mixxx_invite).pack(side="left")
        ttk.Button(tools, text="CREATE REKORDBOX INVITE", command=self.create_rekordbox_invite).pack(side="left", padx=8)
        ttk.Button(tools, text="APPROVE SELECTED", command=lambda: self.guest_action("approve")).pack(side="left", padx=8)
        ttk.Button(tools, text="END LIVE GUEST", command=lambda: self.guest_action("end")).pack(side="left")
        ttk.Button(tools, text="REVOKE LINK", command=lambda: self.guest_action("revoke")).pack(side="left", padx=8)
        ttk.Button(tools, text="Refresh", command=self.refresh_guests).pack(side="right")
        self.guest_tree = ttk.Treeview(f, columns=("guest", "status", "expires", "connected"), show="headings", height=13)
        for key, title, width in (("guest", "Guest DJ", 280), ("status", "Status", 150), ("expires", "Expires", 190), ("connected", "Connected", 190)):
            self.guest_tree.heading(key, text=title)
            self.guest_tree.column(key, width=width)
        self.guest_tree.pack(fill="both", expand=True, pady=14)
        self.guest_status = tk.Label(f, text="No guest session active.", bg="#100b18", fg="#9e90a8", anchor="w")
        self.guest_status.pack(fill="x")
        self.refresh_guests()

    def create_guest_invite(self):
        guest_name = simpledialog.askstring("Guest DJ invite", "Guest DJ name", initialvalue="Guest DJ", parent=self)
        if guest_name is None:
            return
        minutes = simpledialog.askinteger("Invite expiration", "How many minutes should this link remain valid?", initialvalue=180, minvalue=15, maxvalue=1440, parent=self)
        if minutes is None:
            return
        try:
            result = self.api.request("POST", "/api/guest-invites", {"guest_name": guest_name, "expires_minutes": minutes})
            link = result["link"]
            self.clipboard_clear()
            self.clipboard_append(link)
            self.update()
            self.refresh_guests()
            messagebox.showinfo("Guest link copied", f"Private link for {guest_name}:\n\n{link}\n\nIt has been copied to your clipboard. The guest cannot go live until you approve them in this tab.", parent=self)
        except Exception as exc:
            messagebox.showerror("Could not create invite", str(exc), parent=self)

    def create_traktor_invite(self):
        guest_name = simpledialog.askstring("Traktor guest invite", "Guest DJ name", initialvalue="Guest DJ", parent=self)
        if guest_name is None:
            return
        minutes = simpledialog.askinteger("Invite expiration", "How many minutes should these credentials remain valid?", initialvalue=180, minvalue=15, maxvalue=1440, parent=self)
        if minutes is None:
            return
        try:
            result = self.api.request("POST", "/api/traktor-invites", {"guest_name": guest_name, "expires_minutes": minutes})
            invite = (
                f"AllThings140Radio private Traktor invite for {guest_name}\n\n"
                "Open Traktor Preferences → Broadcasting and use:\n"
                "Proxy: Default\n"
                f"Address: {result['host']}\n"
                f"Port: {result['port']}\n"
                f"Mount path: {result['mount']}\n"
                f"Password: {result['password']}\n"
                f"Format: {result['format']}\n\n"
                "Leave Stream URL blank. Wait for the host to approve you, then press Broadcast in Traktor.\n"
                f"This invite expires in {minutes} minutes and can be revoked at any time."
            )
            self.clipboard_clear(); self.clipboard_append(invite); self.update()
            self.refresh_guests()
            messagebox.showinfo("Traktor invite copied", f"Secure Traktor settings for {guest_name} were copied to your clipboard.\n\nSend the copied invite privately, then select this guest and click APPROVE SELECTED. The password is shown only this once.", parent=self)
        except Exception as exc:
            messagebox.showerror("Could not create Traktor invite", str(exc), parent=self)

    def create_mixxx_invite(self):
        guest_name = simpledialog.askstring("Mixxx guest invite", "Guest DJ name", initialvalue="Guest DJ", parent=self)
        if guest_name is None:
            return
        minutes = simpledialog.askinteger("Invite expiration", "How many minutes should these credentials remain valid?", initialvalue=180, minvalue=15, maxvalue=1440, parent=self)
        if minutes is None:
            return
        try:
            result = self.api.request("POST", "/api/mixxx-invites", {"guest_name": guest_name, "expires_minutes": minutes})
            invite = (
                f"AllThings140Radio private Mixxx invite for {guest_name}\n\n"
                "Open Mixxx Preferences → Live Broadcasting, create/select a connection, and enter:\n"
                "Type: Icecast 2\n"
                f"Host: {result['host']}\n"
                f"Port: {result['port']}\n"
                f"Mount: {result['mount']}\n"
                f"Login: {result['login']}\n"
                f"Password: {result['password']}\n"
                "Encoding: 128 kbps, MP3, Stereo\n"
                "Automatic reconnect: Enabled (5 seconds)\n\n"
                "Wait for the host to approve you, click Apply/OK, then turn ON AIR in Mixxx.\n"
                f"This invite expires in {minutes} minutes and can be revoked at any time."
            )
            self.clipboard_clear(); self.clipboard_append(invite); self.update()
            self.refresh_guests()
            messagebox.showinfo("Mixxx invite copied", f"Secure Mixxx settings for {guest_name} were copied to your clipboard.\n\nSend the copied invite privately, then select this guest and click APPROVE SELECTED. The password is shown only this once.", parent=self)
        except Exception as exc:
            messagebox.showerror("Could not create Mixxx invite", str(exc), parent=self)

    def create_rekordbox_invite(self):
        guest_name = simpledialog.askstring("rekordbox guest invite", "Guest DJ name", initialvalue="Guest DJ", parent=self)
        if guest_name is None:
            return
        minutes = simpledialog.askinteger("Invite expiration", "How many minutes should this link remain valid?", initialvalue=180, minvalue=15, maxvalue=1440, parent=self)
        if minutes is None:
            return
        try:
            result = self.api.request("POST", "/api/guest-invites", {"guest_name": guest_name, "expires_minutes": minutes})
            invite = (
                f"AllThings140Radio private rekordbox invite for {guest_name}\n\n"
                f"Guest Studio: {result['link']}\n\n"
                "1. In rekordbox Performance mode, open Preferences → Audio.\n"
                "2. Select the DJ controller/audio device and enable PC MASTER OUT or its loopback/broadcast output.\n"
                "3. Open the private Guest Studio link in Chrome, Edge, or Brave.\n"
                "4. Choose the controller loopback/broadcast input and confirm the level meter moves.\n"
                "5. Request access and wait for host approval, then press START BROADCAST.\n\n"
                f"This invite expires in {minutes} minutes and can be revoked at any time."
            )
            self.clipboard_clear(); self.clipboard_append(invite); self.update()
            self.refresh_guests()
            messagebox.showinfo("rekordbox invite copied", f"The private rekordbox Guest Studio invite for {guest_name} was copied to your clipboard.\n\nSend it privately, then approve the guest when their audio meter is working.", parent=self)
        except Exception as exc:
            messagebox.showerror("Could not create rekordbox invite", str(exc), parent=self)

    def selected_guest(self):
        selected = self.guest_tree.selection()
        if not selected:
            messagebox.showinfo("Select a guest", "Select a guest invite first.", parent=self)
            return None
        return self.guest_rows.get(selected[0])

    def guest_action(self, action):
        row = self.selected_guest()
        if not row:
            return
        labels = {"approve": "Approve this guest to begin streaming?", "end": "End this guest broadcast and return to AutoDJ?", "revoke": "Revoke this private link?"}
        if not messagebox.askyesno("Guest DJ", f"{labels[action]}\n\n{row.get('guest_name', 'Guest DJ')}", parent=self):
            return
        try:
            self.api.request("POST", f"/api/guest-invites/{row['id']}/{action}", {})
            self.refresh_guests()
            self.refresh_status()
        except Exception as exc:
            messagebox.showerror("Guest action failed", str(exc), parent=self)

    def refresh_guests(self):
        if not hasattr(self, "guest_tree"):
            return
        try:
            result = self.api.request("GET", "/api/guest-invites", timeout=4)
            self.guest_rows = {}
            self.guest_tree.delete(*self.guest_tree.get_children())
            for row in result.get("invites", []):
                iid = str(row["id"])
                self.guest_rows[iid] = row
                expires = time.strftime("%b %d, %I:%M %p", time.localtime(row["expires_at"]))
                connected = time.strftime("%b %d, %I:%M %p", time.localtime(row["connected_at"])) if row.get("connected_at") else "—"
                self.guest_tree.insert("", "end", iid=iid, values=(row.get("guest_name", "Guest DJ"), str(row.get("status", "")).upper(), expires, connected))
            ingest = result.get("ingest", {})
            self.guest_status.config(text="● GUEST LIVE — AutoDJ safety return armed" if ingest.get("running") else "Guest studio ready. Create a private link or approve a waiting guest.", fg="#76f0c2" if ingest.get("running") else "#9e90a8")
        except Exception as exc:
            self.guest_status.config(text=f"Guest status unavailable: {exc}", fg="#ff9ca8")

    def build_library(self):
        f = self.tabs["library"]
        tools = tk.Frame(f, bg="#100b18")
        tools.pack(fill="x")
        ttk.Button(tools, text="Upload One Track", command=self.upload_track).pack(side="left")
        ttk.Button(tools, text="Upload Ebmarah Masters Folder", command=self.bulk_upload_owned_masters).pack(side="left", padx=8)
        ttk.Button(tools, text="EDIT SELECTED", command=self.edit_selected_library).pack(side="left", padx=8)
        ttk.Button(tools, text="PLAY SELECTED NOW", command=self.play_selected_library).pack(side="left", padx=8)
        ttk.Button(tools, text="Refresh", command=self.refresh_library).pack(side="right")
        ttk.Button(tools, text="ERASE SELECTED", command=self.delete_selected_library).pack(side="right", padx=8)
        ttk.Button(tools, text="ERASE CANCELLED / NOT APPROVED", command=self.prune_unapproved_library).pack(side="right", padx=8)
        ttk.Button(tools, text="Detect Duplicates", command=self.detect_library_duplicates).pack(side="right")
        self.library_tree = ttk.Treeview(f, columns=("track", "approved", "rights", "enabled", "onair"), show="headings")
        for key, title, width in (("track", "Artist / Title", 500), ("approved", "Approved", 90), ("rights", "Rights", 90), ("enabled", "Enabled", 90), ("onair", "On Air", 80)):
            self.library_tree.heading(key, text=title)
            self.library_tree.column(key, width=width)
        self.library_tree.pack(fill="both", expand=True, pady=12)
        self.library_tree.tag_configure("duplicate", background="#3a173f", foreground="#fff0ff")
        self.library_tree.bind("<Double-1>", lambda _e: self.edit_selected_library())
        self.upload_status = tk.Label(
            f, text="Approved, rights-cleared files become the actual synchronized 24/7 server feed.",
            bg="#100b18", fg="#a99ab3"
        )
        self.upload_status.pack(anchor="w")
        self.refresh_library()

    def upload_track(self):
        filename = filedialog.askopenfilename(title="Choose rights-cleared audio", filetypes=AUDIO_TYPES)
        if not filename:
            return
        title = simpledialog.askstring("Track title", "Title", initialvalue=Path(filename).stem, parent=self)
        if title is None:
            return
        artist = simpledialog.askstring("Artist", "Artist name", initialvalue="Ebmarah", parent=self) or ""
        source = simpledialog.askstring("Source link", "SoundCloud or artist page (optional)", initialvalue="https://soundcloud.com/ebmarah", parent=self) or ""
        rights = messagebox.askyesno(
            "Broadcast permission",
            "Do you confirm that you own this recording or have permission from the relevant rights holders to broadcast it?\n\nSelecting No uploads it unapproved and it will not enter the live rotation."
        )
        self.upload_status.config(text="Uploading…")
        def worker():
            try:
                self.api.upload(
                    Path(filename),
                    {"title": title, "artist": artist, "source_url": source, "rights_confirmed": "1" if rights else "0"},
                    lambda sent, total: self.post_ui(lambda: self.upload_status.config(text=f"Uploading… {sent * 100 // max(total, 1)}%")),
                )
                self.post_ui(lambda: (self.upload_status.config(text="Upload complete. The server rotation is refreshing."), self.refresh_library(), self.refresh_status()))
            except Exception as exc:
                self.post_ui(lambda: messagebox.showerror("Upload failed", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def build_ads(self):
        f = self.tabs["ads"]
        top = tk.Frame(f, bg="#100b18"); top.pack(fill="x")
        ttk.Button(top, text="UPLOAD AD", command=self.upload_ad).pack(side="left")
        ttk.Button(top, text="ENABLE / DISABLE", command=self.toggle_ad).pack(side="left", padx=8)
        ttk.Button(top, text="PLAY AD NOW", command=self.play_ad_now).pack(side="left")
        ttk.Button(top, text="PREVIEW", command=self.preview_ad).pack(side="left", padx=8)
        ttk.Button(top, text="ANALYZE", command=lambda: self.ad_action("analyze")).pack(side="left")
        ttk.Button(top, text="NORMALIZE COPY", command=self.normalize_ad).pack(side="left", padx=8)
        ttk.Button(top, text="MOVE TO TRASH", command=self.delete_ad).pack(side="left", padx=8)
        ttk.Button(top, text="Refresh", command=self.refresh_ads).pack(side="right")
        settings = tk.Frame(f, bg="#100b18"); settings.pack(fill="x", pady=(14, 8))
        tk.Label(settings, text="Automatic ad interval (seconds)", bg="#100b18", fg="#cdbed7").pack(side="left")
        self.ad_interval = tk.StringVar(value="420")
        ttk.Entry(settings, textvariable=self.ad_interval, width=8).pack(side="left", padx=8)
        ttk.Button(settings, text="SAVE INTERVAL", command=self.save_ad_interval).pack(side="left")
        self.ads_tree = ttk.Treeview(f, columns=("name", "enabled", "duration", "loudness", "peak", "last", "plays"), show="headings")
        for key, title, width in (("name", "Advertisement", 330), ("enabled", "Enabled", 80), ("duration", "Duration", 80), ("loudness", "Mean dB", 85), ("peak", "Peak dB", 80), ("last", "Last Played", 150), ("plays", "Plays", 65)):
            self.ads_tree.heading(key, text=title); self.ads_tree.column(key, width=width)
        self.ads_tree.pack(fill="both", expand=True, pady=8)
        self.ad_history = tk.Text(f, height=7, bg="#15101d", fg="#bdaec9", relief="flat", padx=10, pady=8)
        self.ad_history.pack(fill="x", pady=(0, 8))
        self.ads_status = tk.Label(f, text="Managed ads are copied to the server; originals are never modified.", bg="#100b18", fg="#a99ab3")
        self.ads_status.pack(anchor="w")
        self.refresh_ads()

    def refresh_ads(self):
        if not hasattr(self, "ads_tree"):
            return
        try:
            result = self.api.request("GET", "/api/ads")
            self.ad_interval.set(str(result.get("interval_seconds", 420)))
            self.ads_tree.delete(*self.ads_tree.get_children())
            for ad in result.get("ads", []):
                last = time.strftime("%b %d %I:%M %p", time.localtime(ad["last_played"])) if ad.get("last_played") else "—"
                mean = f"{float(ad['mean_volume_db']):.1f}" if ad.get("mean_volume_db") is not None else "ANALYZE"
                peak = f"{float(ad['peak_db']):.1f}" if ad.get("peak_db") is not None else "—"
                self.ads_tree.insert("", "end", iid=ad["filename"], values=(ad["name"], "YES" if ad.get("enabled", True) else "NO", f"{float(ad.get('duration', 0)):.1f}s", mean, peak, last, ad.get("play_count", 0)))
            self.ad_history.config(state="normal"); self.ad_history.delete("1.0", "end")
            for row in result.get("history", [])[:25]:
                when = time.strftime("%b %d %I:%M:%S %p", time.localtime(int(row.get("ts", 0))))
                mode = "AUTO" if row.get("automatic", True) else "MANUAL"
                self.ad_history.insert("end", f"{when}  {mode:6}  {row.get('event', '')}  {row.get('name', '')}\n")
            self.ad_history.config(state="disabled")
        except Exception as exc:
            self.ads_status.config(text=f"Ads unavailable: {exc}", fg="#ff9ca8")

    def selected_ad(self):
        selected = self.ads_tree.selection()
        return selected[0] if selected else None

    def ad_action(self, action):
        filename = self.selected_ad()
        if not filename:
            return messagebox.showinfo("Select an ad", "Select an advertisement first.")
        try:
            self.api.request("POST", f"/api/ads/{urllib.parse.quote(filename)}/{action}")
            self.ads_status.config(text=f"Advertisement {action}: {filename}", fg="#7ce5ad")
            self.refresh_ads()
        except Exception as exc:
            messagebox.showerror("Advertisement action failed", str(exc))

    def toggle_ad(self):
        filename = self.selected_ad()
        if not filename: return messagebox.showinfo("Select an ad", "Select an advertisement first.")
        try:
            result = self.api.request("GET", "/api/ads")
            current = next((ad for ad in result.get("ads", []) if ad["filename"] == filename), {})
            self.ad_action("disable" if current.get("enabled", True) else "enable")
        except Exception as exc:
            messagebox.showerror("Could not inspect ad", str(exc))

    def play_ad_now(self):
        if messagebox.askyesno("Play advertisement now", "This will insert the selected ad into the live station. Continue?", parent=self): self.ad_action("play")

    def delete_ad(self):
        if messagebox.askyesno("Move ad to trash", "The ad will be recoverable from the server trash. Continue?", parent=self): self.ad_action("delete")

    def preview_ad(self):
        filename = self.selected_ad()
        if not filename:
            return messagebox.showinfo("Select an ad", "Select an advertisement first.")
        source = Path("/opt/allthings140radio-server/ads") / Path(filename).name
        if not source.is_file():
            return messagebox.showerror("Preview unavailable", "The managed server copy is not available locally.")
        try:
            subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", str(source)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.ads_status.config(text=f"Previewing locally: {filename}", fg="#7ce5ad")
        except Exception as exc:
            messagebox.showerror("Preview failed", str(exc))

    def normalize_ad(self):
        filename = self.selected_ad()
        if not filename:
            return messagebox.showinfo("Select an ad", "Select an advertisement first.")
        if messagebox.askyesno("Normalize managed copy?", f"Create a broadcast-normalized managed copy of:\n\n{filename}\n\nThe original source file is never changed and the current server copy is moved to recoverable trash.", parent=self):
            self.ad_action("normalize")

    def upload_ad(self):
        filename = filedialog.askopenfilename(title="Choose station advertisement", filetypes=AUDIO_TYPES)
        if not filename: return
        self.ads_status.config(text="Uploading advertisement…")
        def worker():
            try:
                self.api.upload(Path(filename), {"kind": "ad"})
                self.post_ui(lambda: (self.ads_status.config(text="Advertisement installed.", fg="#7ce5ad"), self.refresh_ads()))
            except Exception as exc:
                self.post_ui(lambda: messagebox.showerror("Ad upload failed", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def save_ad_interval(self):
        try:
            result = self.api.request("POST", "/api/ads/settings", {"interval_seconds": int(self.ad_interval.get())})
            self.ad_interval.set(str(result.get("interval_seconds", self.ad_interval.get())))
            self.ads_status.config(text="Advertisement interval saved.", fg="#7ce5ad")
        except Exception as exc:
            messagebox.showerror("Could not save interval", str(exc))

    def build_archive(self):
        f = self.tabs["archive"]
        top = tk.Frame(f, bg="#100b18"); top.pack(fill="x")
        tk.Label(top, text="TAKEOVER RECORDINGS", bg="#100b18", fg="#efe5f8", font=("Sans", 12, "bold")).pack(side="left")
        ttk.Button(top, text="TEST WEBSITE ALERT", command=self.test_website_alert).pack(side="right")
        ttk.Button(top, text="Refresh", command=self.refresh_archive).pack(side="right", padx=8)
        self.archive_tree = ttk.Treeview(f, columns=("title", "host", "started", "duration", "status"), show="headings")
        for key, title, width in (("title", "Show", 360), ("host", "DJ / Host", 180), ("started", "Started", 180), ("duration", "Duration", 100), ("status", "Status", 120)):
            self.archive_tree.heading(key, text=title); self.archive_tree.column(key, width=width)
        self.archive_tree.pack(fill="both", expand=True, pady=14)
        self.archive_status = tk.Label(f, text="Takeovers record automatically after a legitimate live handoff.", bg="#100b18", fg="#a99ab3")
        self.archive_status.pack(anchor="w")
        self.refresh_archive()

    def refresh_archive(self):
        if not hasattr(self, "archive_tree"): return
        try:
            result = self.api.request("GET", "/api/archive")
            self.archive_tree.delete(*self.archive_tree.get_children())
            for row in result.get("archives", []):
                started = time.strftime("%b %d, %Y %I:%M %p", time.localtime(int(row.get("started_at", 0))))
                self.archive_tree.insert("", "end", iid=row["archive_id"], values=(row.get("title", "Live takeover"), row.get("host", "Guest DJ"), started, self.format_time(row.get("duration", 0)), str(row.get("status", "")).upper()))
            self.archive_status.config(text=f"{result.get('total', 0)} published takeover recording(s).", fg="#7ce5ad")
        except Exception as exc:
            self.archive_status.config(text=f"Archive unavailable: {exc}", fg="#ff9ca8")

    def test_website_alert(self):
        try:
            self.api.request("POST", "/api/alerts/test", {"title": "TEST ALERT", "message": "AllThings140Radio alert system online.", "duration": 7000})
            self.archive_status.config(text="Test alert queued for the public website.", fg="#7ce5ad")
        except Exception as exc:
            messagebox.showerror("Test alert failed", str(exc))

    def refresh_library(self):
        if not hasattr(self, "library_tree"):
            return
        if self.library_refresh_running:
            return
        self.library_refresh_running = True
        threading.Thread(target=self._refresh_library_worker, daemon=True).start()

    def _refresh_library_worker(self):
        try:
            rows = self.api.request("GET", "/api/tracks")
            current_id = None
            try:
                current_id = self.api.request("GET", "/api/autodj/queue").get("state", {}).get("current_track_id")
            except Exception:
                pass
            self.post_ui(lambda: self._apply_library(rows, current_id, None))
        except Exception as exc:
            self.post_ui(lambda: self._apply_library([], None, str(exc)))

    def _apply_library(self, rows, current_id, error):
        self.library_refresh_running = False
        if error:
            self.upload_status.config(text=f"Could not refresh library: {error}")
            return
        self.library_rows = {}
        self.library_tree.delete(*self.library_tree.get_children())
        for row in rows:
            iid = str(row["id"])
            self.library_rows[iid] = row
            on_air = "●" if current_id is not None and int(current_id) == int(row["id"]) else ""
            self.library_tree.insert(
                "", "end", iid=iid,
                values=(f"{row['artist']} — {row['title']}", "Yes" if row["approved"] else "No", "Yes" if row["rights_confirmed"] else "No", "Yes" if row["enabled"] else "No", on_air)
            )

    def play_selected_library(self):
        selected = self.library_tree.selection()
        if not selected:
            return messagebox.showinfo("Select a track", "Select a catalog song first.")
        row = self.library_rows.get(selected[0])
        if not row:
            return
        self.autodj_play_track(row["id"], row.get("title", "track"))

    def edit_selected_library(self):
        selected = self.library_tree.selection()
        if not selected:
            return messagebox.showinfo("Select a track", "Select a catalog song to edit.")
        row = self.library_rows.get(selected[0])
        if not row:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Edit Track Metadata")
        dialog.geometry("560x430")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg="#100b18", padx=24, pady=20)
        dialog.columnconfigure(0, weight=1)
        title_var = tk.StringVar(value=row.get("title", ""))
        artist_var = tk.StringVar(value=row.get("artist", ""))
        source_var = tk.StringVar(value=row.get("source_url", ""))
        rights_var = tk.BooleanVar(value=bool(row.get("rights_confirmed")))
        approved_var = tk.BooleanVar(value=bool(row.get("approved")))
        enabled_var = tk.BooleanVar(value=bool(row.get("enabled")))
        fields = (("TRACK TITLE", title_var), ("ARTIST", artist_var), ("SOURCE / ARTIST LINK", source_var))
        for index, (label, variable) in enumerate(fields):
            tk.Label(dialog, text=label, bg="#100b18", fg="#d9b8ef", font=("Sans", 9, "bold")).grid(row=index * 2, column=0, sticky="w", pady=(0 if index == 0 else 12, 5))
            tk.Entry(dialog, textvariable=variable, bg="#08040d", fg="white", insertbackground="white", relief="flat", highlightthickness=1, highlightbackground="#633080").grid(row=index * 2 + 1, column=0, sticky="ew", ipady=8)
        checks = tk.Frame(dialog, bg="#100b18")
        checks.grid(row=6, column=0, sticky="w", pady=18)
        for text, variable in (("Rights confirmed", rights_var), ("Approved for rotation", approved_var), ("Enabled", enabled_var)):
            tk.Checkbutton(checks, text=text, variable=variable, bg="#100b18", fg="#e8ddf0", selectcolor="#281a33", activebackground="#100b18", activeforeground="white").pack(anchor="w", pady=3)
        feedback = tk.Label(dialog, text=f"Audio file: {row.get('filename', '')}", bg="#100b18", fg="#897a93", anchor="w")
        feedback.grid(row=7, column=0, sticky="ew")
        buttons = tk.Frame(dialog, bg="#100b18")
        buttons.grid(row=8, column=0, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)
        def save():
            title = title_var.get().strip()
            if not title:
                return messagebox.showerror("Missing title", "Enter a track title.", parent=dialog)
            if approved_var.get() and not rights_var.get():
                return messagebox.showerror("Rights required", "Confirm broadcast rights before approving this track.", parent=dialog)
            try:
                self.api.request("POST", f"/api/tracks/{row['id']}", {
                    "title": title, "artist": artist_var.get().strip(), "source_url": source_var.get().strip(),
                    "rights_confirmed": rights_var.get(), "approved": approved_var.get(), "enabled": enabled_var.get(),
                })
                dialog.destroy()
                self.upload_status.config(text="Track metadata saved. The station catalog is updated.")
                self.refresh_library()
                self.refresh_status()
            except Exception as exc:
                messagebox.showerror("Could not save track", str(exc), parent=dialog)
        ttk.Button(buttons, text="SAVE CHANGES", command=save).pack(side="left")
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.bind("<Return>", lambda _event: save())
        dialog.after(50, lambda: dialog.focus_force())

    def detect_library_duplicates(self):
        self.upload_status.config(text="Scanning audio files for duplicates…")
        def worker():
            try:
                result = self.api.request("GET", "/api/tracks/duplicates", timeout=180)
                self.post_ui(lambda: self.show_duplicate_results(result))
            except Exception as exc:
                self.post_ui(lambda: (self.upload_status.config(text="Duplicate scan failed."), messagebox.showerror("Duplicate scan failed", str(exc))))
        threading.Thread(target=worker, daemon=True).start()

    def show_duplicate_results(self, result):
        groups = result.get("groups", [])
        duplicate_ids = {str(track["id"]) for group in groups for track in group.get("tracks", [])}
        for iid in self.library_tree.get_children():
            self.library_tree.item(iid, tags=("duplicate",) if iid in duplicate_ids else ())
        if not groups:
            self.upload_status.config(text="Duplicate scan complete: no duplicates found.")
            return messagebox.showinfo("Duplicate scan", "No duplicate tracks were found.")
        self.upload_status.config(text=f"Duplicate scan found {len(groups)} group(s). Removing extra copies…")
        self.remove_duplicate_copies(groups, None, confirm=False)
        return
        dialog = tk.Toplevel(self)
        dialog.title("Duplicate Tracks")
        dialog.geometry("760x520")
        dialog.transient(self)
        dialog.configure(bg="#100b18", padx=18, pady=16)
        tk.Label(dialog, text="POSSIBLE DUPLICATES", bg="#100b18", fg="#e7c7ff", font=("Sans", 16, "bold")).pack(anchor="w")
        tk.Label(dialog, text="Exact matches compare the complete audio file. Metadata matches compare normalized artist and title.", bg="#100b18", fg="#9f91aa").pack(anchor="w", pady=(4, 12))
        text = tk.Text(dialog, bg="#08040d", fg="#eee4f5", insertbackground="white", relief="flat", padx=14, pady=12, wrap="word")
        text.pack(fill="both", expand=True)
        for index, group in enumerate(groups, 1):
            text.insert("end", f"{index}. {group['reason']}\n")
            for track in group.get("tracks", []):
                text.insert("end", f"   ID {track['id']}  •  {track.get('artist', '')} — {track.get('title', '')}\n   {track.get('filename', '')}\n")
            text.insert("end", "\n")
        text.configure(state="disabled")
        actions = tk.Frame(dialog, bg="#100b18")
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="REMOVE DUPLICATE COPIES", command=lambda: self.remove_duplicate_copies(groups, dialog)).pack(side="left")
        ttk.Button(actions, text="CLOSE", command=dialog.destroy).pack(side="right")

    def remove_duplicate_copies(self, groups, dialog=None, confirm=True):
        removable = []
        seen = set()
        for group in groups:
            tracks = group.get("tracks", [])
            for track in tracks[1:]:
                track_id = int(track["id"])
                if track_id not in seen:
                    seen.add(track_id)
                    removable.append(track)
        if not removable:
            return
        if confirm and not messagebox.askyesno(
            "Remove duplicate copies",
            f"Move {len(removable)} duplicate catalog entr{'y' if len(removable) == 1 else 'ies'} to server trash?\n\nThe first entry in each duplicate group will be kept. Files remain recoverable.",
            parent=dialog,
        ):
            return
        if dialog is not None:
            dialog.destroy()
        self.upload_status.config(text=f"Removing {len(removable)} duplicate copies…")
        def worker():
            removed = 0
            failed = []
            for track in removable:
                try:
                    self.api.request("POST", f"/api/tracks/{int(track['id'])}/delete", {}, timeout=20)
                    removed += 1
                except Exception as exc:
                    failed.append(f"ID {track.get('id')}: {exc}")
            message = f"Removed {removed} duplicate cop{'y' if removed == 1 else 'ies'}; kept one entry per group."
            if failed:
                message += " Failed: " + "; ".join(failed[:3])
            self.post_ui(lambda: (self.upload_status.config(text=message), self.refresh_library(), self.refresh_status(), messagebox.showinfo("Duplicate cleanup complete", message)))
        threading.Thread(target=worker, daemon=True).start()

    def delete_selected_library(self):
        selected = self.library_tree.selection()
        if not selected:
            return messagebox.showinfo("Select a track", "Select a catalog song to delete.")
        row = self.library_rows.get(selected[0])
        if not row:
            return
        label = " — ".join(part for part in (row.get("artist", ""), row.get("title", "")) if part)
        confirmed = messagebox.askyesno(
            "Move track to trash?",
            f"Remove this track from the station catalog?\n\n{label}\n\nThe audio file will be moved to the server trash folder, not permanently erased.",
            parent=self,
        )
        if not confirmed:
            return
        try:
            result = self.api.request("POST", f"/api/tracks/{row['id']}/delete", {})
            self.upload_status.config(text=f"Track removed safely. Recovery file: {result.get('recoverable', 'server trash')}")
            self.refresh_library()
            self.refresh_status()
        except Exception as exc:
            messagebox.showerror("Could not delete track", str(exc), parent=self)

    def prune_unapproved_library(self):
        """Safely remove cancelled, disabled, rights-unconfirmed, or missing tracks."""
        try:
            preview = self.api.request("GET", "/api/tracks/prune-preview")
        except Exception as exc:
            return messagebox.showerror("Could not scan catalog", str(exc), parent=self)
        candidates = preview.get("candidates", [])
        removable = [row for row in candidates if not row.get("is_current")]
        if not removable:
            return messagebox.showinfo("Catalog is clean", "Every catalog entry is approved, enabled, rights-cleared, and has an audio file.", parent=self)
        sample = "\n".join(
            f"• {row.get('artist', '')} — {row.get('title', '')} ({row.get('reason', 'not eligible')})"
            for row in removable[:8]
        )
        more = f"\n…plus {len(removable) - 8} more" if len(removable) > 8 else ""
        if not messagebox.askyesno(
            "Erase cancelled tracks?",
            f"Erase {len(removable)} cancelled or non-playable catalog entries?\n\n{sample}{more}\n\nAudio files are moved to the server trash folder for recovery. The currently playing track is never erased while on air.",
            parent=self,
        ):
            return
        try:
            result = self.api.request("POST", "/api/tracks/prune", {})
            skipped = len(result.get("skipped_current", []))
            suffix = f" {skipped} current track skipped until it leaves the air." if skipped else ""
            self.upload_status.config(text=f"Erased {result.get('removed', 0)} cancelled/non-playable entries.{suffix}")
            self.refresh_library()
            self.refresh_status()
        except Exception as exc:
            messagebox.showerror("Could not erase catalog entries", str(exc), parent=self)

    def build_test_rotation(self):
        f = self.tabs["test"]
        tk.Label(f, text="EBMARAH CATALOG — 24/7 SERVER FEED", bg="#100b18", fg="#e3c5ff", font=("Sans", 15, "bold")).pack(anchor="w")
        tk.Label(
            f,
            text="This is the real synchronized station rotation. Select the folder containing your owned Ebmarah master files; the server uploads, approves, and loops them continuously whenever no DJ takeover is active.",
            bg="#100b18", fg="#b6a8bf", wraplength=880, justify="left"
        ).pack(anchor="w", pady=(6, 18))
        try:
            settings = self.api.request("GET", "/api/settings")
        except Exception:
            settings = {}
        form = tk.Frame(f, bg="#100b18")
        form.pack(fill="x")
        tk.Label(form, text="Catalog reference link (metadata only)", bg="#100b18", fg="#d9ccdf").grid(row=0, column=0, sticky="w")
        self.test_sc_url = ttk.Entry(form)
        self.test_sc_url.insert(0, settings.get("soundcloud_test_url", "https://soundcloud.com/ebmarah"))
        self.test_sc_url.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        tk.Label(form, text="Catalog display name", bg="#100b18", fg="#d9ccdf").grid(row=2, column=0, sticky="w")
        self.test_sc_title = ttk.Entry(form)
        self.test_sc_title.insert(0, settings.get("soundcloud_test_title", "Ebmarah Catalog"))
        self.test_sc_title.grid(row=3, column=0, sticky="ew", pady=(4, 12))
        self.test_sc_enabled = tk.BooleanVar(value=False)
        form.columnconfigure(0, weight=1)
        buttons = tk.Frame(f, bg="#100b18")
        buttons.pack(fill="x", pady=18)
        ttk.Button(buttons, text="UPLOAD OWNED EBMARAH MASTERS FOLDER", command=self.bulk_upload_owned_masters).pack(side="left", ipady=7)
        ttk.Button(buttons, text="Open Catalog Link", command=self.open_soundcloud_test).pack(side="left", padx=8)
        ttk.Button(buttons, text="Open Listener Website", command=lambda: webbrowser.open(PUBLIC_SITE)).pack(side="right")
        self.test_sc_status = tk.Label(f, text="", bg="#100b18", fg="#9f91aa", wraplength=880, justify="left")
        self.test_sc_status.pack(anchor="w", pady=(0, 18))
        note = (
            "The SoundCloud link is only saved as an artist/catalog reference. The radio does not scrape or relay SoundCloud. "
            "The uploaded master files are what the server streams as one shared 24/7 feed, so Skip, Previous, Restart, and Play Now affect every listener at once."
        )
        tk.Label(f, text=note, bg="#171020", fg="#c9bbd2", padx=18, pady=16, wraplength=850, justify="left", highlightbackground="#3a2949", highlightthickness=1).pack(fill="x")

    def save_soundcloud_test(self):
        url = self.test_sc_url.get().strip()
        if not url.startswith(("https://soundcloud.com/", "http://soundcloud.com/", "https://on.soundcloud.com/", "http://on.soundcloud.com/")):
            return messagebox.showerror("Invalid SoundCloud link", "Paste a soundcloud.com profile, playlist, or track URL.")
        data = {
            "soundcloud_test_url": url,
            "soundcloud_test_title": self.test_sc_title.get().strip() or "SoundCloud Test Rotation",
            "soundcloud_test_enabled": False,
        }
        try:
            self.api.request("POST", "/api/settings", data)
            self.test_sc_status.config(text="Catalog reference saved. The live feed still uses your uploaded master files.", fg="#7ce5ad")
            messagebox.showinfo("Catalog reference saved", "The reference link was updated. The synchronized radio feed uses uploaded master files.")
        except APIError as exc:
            messagebox.showerror("Could not save", str(exc))

    def open_soundcloud_test(self):
        url = self.test_sc_url.get().strip() if hasattr(self, "test_sc_url") else "https://soundcloud.com/ebmarah"
        if url:
            webbrowser.open(url)

    def bulk_upload_owned_masters(self):
        folder = filedialog.askdirectory(title="Choose folder containing your owned master files")
        if not folder:
            return
        extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
        files = sorted(path for path in Path(folder).rglob("*") if path.is_file() and path.suffix.lower() in extensions)
        if not files:
            return messagebox.showwarning("No audio found", "That folder does not contain a supported audio file.")
        artist = simpledialog.askstring("Artist name", "Artist for these files", initialvalue="Ebmarah", parent=self)
        if artist is None:
            return
        source = self.test_sc_url.get().strip() if hasattr(self, "test_sc_url") else "https://soundcloud.com/ebmarah"
        if not messagebox.askyesno(
            "Confirm owned masters",
            f"Upload {len(files)} audio file(s) as {artist or 'Unknown artist'}?\n\nConfirm that you own these recordings or have permission from every relevant rights holder to broadcast them."
        ):
            return
        if hasattr(self, "test_sc_status"):
            self.test_sc_status.config(text=f"Preparing to upload {len(files)} file(s)…", fg="#d8b7ff")
        if hasattr(self, "upload_status"):
            self.upload_status.config(text=f"Bulk upload starting: {len(files)} file(s)…")

        def worker():
            completed = 0
            failed = []
            for index, audio_path in enumerate(files, 1):
                try:
                    def progress(sent, total, i=index, name=audio_path.name):
                        percent = sent * 100 // max(total, 1)
                        text = f"Uploading {i}/{len(files)}: {name} — {percent}%"
                        self.post_ui(lambda t=text: self._set_bulk_status(t, "#d8b7ff"))
                    self.api.upload(audio_path, {
                        "title": audio_path.stem,
                        "artist": artist or "",
                        "source_url": source,
                        "rights_confirmed": "1",
                    }, progress)
                    completed += 1
                except Exception as exc:
                    failed.append(f"{audio_path.name}: {exc}")
            def done():
                self.refresh_library()
                message = f"Uploaded {completed} of {len(files)} file(s). AutoDJ is refreshing."
                if failed:
                    message += "\n\nFailed:\n" + "\n".join(failed[:8])
                self._set_bulk_status(message, "#7ce5ad" if not failed else "#ff91b7")
                messagebox.showinfo("Bulk upload finished", message)
            self.post_ui(done)
        threading.Thread(target=worker, daemon=True).start()

    def _set_bulk_status(self, text, color):
        if hasattr(self, "test_sc_status"):
            self.test_sc_status.config(text=text, fg=color)
        if hasattr(self, "upload_status"):
            self.upload_status.config(text=text, fg=color)

    def build_review(self):
        f = self.tabs["review"]
        buttons = tk.Frame(f, bg="#100b18"); buttons.pack(fill="x")
        ttk.Button(buttons, text="Add Submission", command=self.add_review_link).pack(side="left")
        ttk.Button(buttons, text="Listen", command=self.listen_review).pack(side="left", padx=8)
        ttk.Button(buttons, text="Approve — Request Audio", command=lambda:self.review_action("approve")).pack(side="left")
        ttk.Button(buttons, text="Reject", command=lambda:self.review_action("reject")).pack(side="left", padx=8)
        ttk.Button(buttons, text="Refresh", command=self.refresh_reviews).pack(side="right")
        self.review_tree = ttk.Treeview(f, columns=("title","genre","status","url"), show="headings")
        for key,title,width in (("title","Artist / Track",330),("genre","Genre / BPM",150),("status","Status",160),("url","SoundCloud",360)):
            self.review_tree.heading(key,text=title); self.review_tree.column(key,width=width)
        self.review_tree.pack(fill="both", expand=True, pady=12)
        tk.Label(f, text="Public paid submissions appear here for review. Approve only after verifying payment and rights; then request or upload an authorized audio file before adding it to the live catalog.", bg="#100b18", fg="#a99ab3", wraplength=850, justify="left").pack(anchor="w")
        self.review_rows = {}; self.refresh_reviews()

    def add_review_link(self):
        url = simpledialog.askstring("SoundCloud link", "Paste the public track link", parent=self)
        if not url: return
        title = simpledialog.askstring("Track", "Track title", parent=self) or "SoundCloud discovery"
        artist = simpledialog.askstring("Artist", "Artist name", parent=self) or ""
        try:
            self.api.request("POST", "/api/reviews", {"source_url":url,"title":title,"artist":artist})
            self.refresh_reviews()
        except APIError as exc: messagebox.showerror("Could not add track", str(exc))

    def refresh_reviews(self):
        if not hasattr(self,"review_tree"): return
        try:
            rows = self.api.request("GET", "/api/reviews")
            self.review_tree.delete(*self.review_tree.get_children()); self.review_rows={}
            for row in rows:
                iid = str(row["id"]); self.review_rows[iid]=row
                genre = row.get("genre","") + (f" / {row['bpm']} BPM" if row.get("bpm") else "")
                self.review_tree.insert("", "end", iid=iid, values=(f"{row.get('artist','')} — {row['title']}",genre,row["status"],row["source_url"]))
        except Exception: pass

    def selected_review(self):
        sel = self.review_tree.selection()
        return self.review_rows.get(sel[0]) if sel else None

    def listen_review(self):
        row=self.selected_review()
        if row: webbrowser.open(row["source_url"])
        else: messagebox.showinfo("Select a track", "Select a review row first.")

    def review_action(self, action):
        row=self.selected_review()
        if not row: return messagebox.showinfo("Select a track", "Select a review row first.")
        try:
            self.api.request("POST",f"/api/reviews/{row['id']}/{action}",{})
            self.refresh_reviews()
        except APIError as exc: messagebox.showerror("Could not update review",str(exc))

    def build_discover(self):
        f=self.tabs["discover"]
        form=tk.Frame(f,bg="#100b18"); form.pack(fill="x")
        tk.Label(form,text="Search",bg="#100b18",fg="#d9ccdf").grid(row=0,column=0,sticky="w")
        tk.Label(form,text="Genre tags",bg="#100b18",fg="#d9ccdf").grid(row=0,column=1,sticky="w",padx=8)
        tk.Label(form,text="BPM from",bg="#100b18",fg="#d9ccdf").grid(row=0,column=2,sticky="w")
        tk.Label(form,text="BPM to",bg="#100b18",fg="#d9ccdf").grid(row=0,column=3,sticky="w",padx=8)
        self.sc_query=ttk.Entry(form); self.sc_query.grid(row=1,column=0,sticky="ew")
        self.sc_genres=ttk.Entry(form); self.sc_genres.insert(0,"dubstep,140"); self.sc_genres.grid(row=1,column=1,sticky="ew",padx=8)
        self.sc_from=ttk.Entry(form,width=8); self.sc_from.insert(0,"130"); self.sc_from.grid(row=1,column=2)
        self.sc_to=ttk.Entry(form,width=8); self.sc_to.insert(0,"150"); self.sc_to.grid(row=1,column=3,padx=8)
        ttk.Button(form,text="Search SoundCloud",command=self.search_soundcloud).grid(row=1,column=4,padx=8)
        form.columnconfigure(0,weight=1);form.columnconfigure(1,weight=1)
        self.sc_tree=ttk.Treeview(f,columns=("track","genre","url"),show="headings")
        for key,title,width in (("track","Artist / Track",380),("genre","Genre / BPM",170),("url","SoundCloud",400)):
            self.sc_tree.heading(key,text=title);self.sc_tree.column(key,width=width)
        self.sc_tree.pack(fill="both",expand=True,pady=12)
        actions=tk.Frame(f,bg="#100b18");actions.pack(fill="x")
        ttk.Button(actions,text="Listen",command=self.listen_sc).pack(side="left")
        ttk.Button(actions,text="Add Selected to Review",command=self.add_sc_review).pack(side="left",padx=8)
        tk.Label(actions,text="Uses SoundCloud's official API credentials configured by ebmarah.",bg="#100b18",fg="#9f91aa").pack(side="right")
        self.sc_rows={}

    def search_soundcloud(self):
        params=urllib.parse.urlencode({"q":self.sc_query.get(),"genres":self.sc_genres.get(),"bpm_from":self.sc_from.get(),"bpm_to":self.sc_to.get()})
        try:
            rows=self.api.request("GET","/api/soundcloud/search?"+params,timeout=30)
            self.sc_tree.delete(*self.sc_tree.get_children());self.sc_rows={}
            for i,row in enumerate(rows):
                iid=str(i);self.sc_rows[iid]=row
                genre=row.get("genre","")+(f" / {row['bpm']} BPM" if row.get("bpm") else "")
                self.sc_tree.insert("","end",iid=iid,values=(f"{row.get('artist','')} — {row['title']}",genre,row.get("source_url","")))
        except APIError as exc: messagebox.showerror("Search unavailable",str(exc))

    def selected_sc(self):
        sel=self.sc_tree.selection();return self.sc_rows.get(sel[0]) if sel else None
    def listen_sc(self):
        row=self.selected_sc(); webbrowser.open(row["source_url"]) if row else messagebox.showinfo("Select a track","Select a result first.")
    def add_sc_review(self):
        row=self.selected_sc()
        if not row:return messagebox.showinfo("Select a track","Select a result first.")
        try:self.api.request("POST","/api/reviews",row);messagebox.showinfo("Added","Track added to the review queue.");self.refresh_reviews()
        except APIError as exc:messagebox.showerror("Could not add",str(exc))

    def build_settings(self):
        f=self.tabs["settings"]
        if self.user.get("role")!="admin":
            tk.Label(f,text="Only the ebmarah administrator account can change server branding and API credentials.",bg="#100b18",fg="#c3b4cc").pack(anchor="w");return
        ai_frame=tk.Frame(f,bg="#171020",highlightbackground="#633080",highlightthickness=1,padx=14,pady=14);ai_frame.pack(fill="x",pady=(0,14))
        tk.Label(ai_frame,text="AI RADIO HOST (FAIL-OPEN)",bg="#171020",fg="#d7b9ff",font=("Sans",11,"bold")).pack(anchor="w")
        tk.Label(ai_frame,text="Optional local Ollama/TTS personalities. AI errors always skip the announcement and leave music playing.",bg="#171020",fg="#a99bad",wraplength=800,justify="left").pack(anchor="w",pady=(4,10))
        self.ai_status_label=tk.Label(ai_frame,text="Checking AI host…",bg="#171020",fg="#9f91aa",anchor="w",justify="left");self.ai_status_label.pack(fill="x")
        ai_buttons=tk.Frame(ai_frame,bg="#171020");ai_buttons.pack(anchor="w",pady=(10,0))
        ttk.Button(ai_buttons,text="REFRESH AI STATUS",command=self.refresh_ai_status).pack(side="left")
        ttk.Button(ai_buttons,text="ENABLE AI TEST",command=lambda:self.set_ai_enabled(True)).pack(side="left",padx=8)
        ttk.Button(ai_buttons,text="TEST ANNOUNCEMENT",command=self.test_ai_announcement).pack(side="left",padx=8)
        ttk.Button(ai_buttons,text="DISABLE AI NOW",command=lambda:self.set_ai_enabled(False)).pack(side="left")
        self.refresh_ai_status()
        try:settings=self.api.request("GET","/api/settings")
        except Exception:settings={}
        labels=(("station_name","Station name"),("station_description","Description"),("website_url","Public listener website"),("public_host","Public API base URL"),("public_stream_url","Public HTTPS stream URL"),("soundcloud_client_id","SoundCloud Client ID"),("soundcloud_client_secret","SoundCloud Client Secret"))
        self.setting_entries={}
        for key,label in labels:
            tk.Label(f,text=label,bg="#100b18",fg="#d9ccdf").pack(anchor="w",pady=(10,4))
            entry=ttk.Entry(f,show="•" if key.endswith("secret") else "")
            if key in settings:entry.insert(0,str(settings.get(key,"")))
            entry.pack(fill="x");self.setting_entries[key]=entry
        self.unlicensed_test_var=tk.BooleanVar(value=bool(settings.get("allow_unlicensed_test_mode", False)))
        tk.Checkbutton(
            f, text="TEST MODE: include tracks without confirmed broadcast rights",
            variable=self.unlicensed_test_var, bg="#100b18", fg="#ffcf73", selectcolor="#281a33",
            activebackground="#100b18", activeforeground="#ffe0a6"
        ).pack(anchor="w", pady=(16, 4))
        tk.Label(
            f, text="Warning: this is for private testing only. Turning it on allows rights-unconfirmed files into the shared stream; public broadcasting may require permission or licenses even when it is non-commercial.",
            bg="#100b18", fg="#c7a66e", wraplength=800, justify="left"
        ).pack(anchor="w", pady=(0, 10))
        tk.Label(f,text="The listener site is deployed at https://ebeinc.online/radio/. Set the public API and stream fields after the HTTPS tunnel or reverse proxy is connected. SoundCloud credentials are only used for discovery and review; the real radio feed uses uploaded catalog masters. Leave the SoundCloud secret blank unless replacing it.",bg="#100b18",fg="#9d8fa7",wraplength=800,justify="left").pack(anchor="w",pady=14)
        ttk.Button(f,text="Save Server Settings",command=self.save_settings).pack(anchor="w",ipadx=18,ipady=6)

    def save_settings(self):
        data={k:e.get().strip() for k,e in self.setting_entries.items()}
        data["allow_unlicensed_test_mode"]=bool(self.unlicensed_test_var.get())
        if not data.get("soundcloud_client_secret"):data.pop("soundcloud_client_secret",None)
        try:self.api.request("POST","/api/settings",data);messagebox.showinfo("Saved","Server settings updated.")
        except APIError as exc:messagebox.showerror("Could not save",str(exc))

    def refresh_ai_status(self):
        if not hasattr(self,"ai_status_label"): return
        try:
            data=self.api.request("GET","/api/ai/status")
            providers=", ".join(f"{key}:{'ready' if value else 'missing'}" for key,value in data.get("providers",{}).items())
            self.ai_status_label.config(text=f"Enabled: {data.get('enabled',False)}  •  Humor: {data.get('humorLevel','—')}  •  Voices: {len(data.get('voices',[]))}  •  Personas: {len(data.get('personas',[]))}\nProviders: {providers or 'none detected'}",fg="#78e9ba" if data.get("ready") else "#c7a66e")
        except Exception as exc:self.ai_status_label.config(text=f"AI host unavailable: {exc}",fg="#ff9ca8")

    def test_ai_announcement(self):
        try:
            data=self.api.request("POST","/api/ai/test",{"announcementType":"STATION_ID","context":{"stationUrl":"https://allthings140radio.online"}})
            messagebox.showinfo("AI announcement test",str(data.get("text","No announcement returned.")),parent=self)
        except APIError as exc:messagebox.showerror("AI test failed",str(exc),parent=self)

    def set_ai_enabled(self,enabled):
        try:
            self.api.request("POST","/api/ai/disable",{"enabled":bool(enabled)});self.refresh_ai_status();messagebox.showinfo("AI host",("Enabled" if enabled else "Disabled immediately; music is unaffected."),parent=self)
        except APIError as exc:messagebox.showerror("Could not change AI host",str(exc),parent=self)

    def build_setup(self):
        f=self.tabs["setup"]
        text=tk.Text(f,bg="#171020",fg="#e8ddf0",insertbackground="white",relief="flat",wrap="word",padx=18,pady=18)
        guide="""ALLTHINGS140RADIO — DJ SETUP

CONNECT
1. Install this .deb on a Zorin OS computer.
2. Be on the same network as the always-on radio server.
3. Press Discover Station. If discovery is blocked, type the server address shown in Server Manager.
4. Sign in as ebmarah or eyewitnis. First-use password: allthings140.
5. Create a private password when prompted.

24/7 AUTODJ
Upload audio from Library and confirm broadcast permission. Admin/manager uploads with permission are approved automatically. The server refreshes its rotation without requiring a reboot.

GO LIVE
1. Add local audio files to Live Queue in the order you want.
2. Enable microphone mixing for announcements.
3. Press GO LIVE. AutoDJ becomes the fallback automatically.
4. Use Mute Mic between announcements.
5. Press END BROADCAST when finished. AutoDJ returns.

MICROPHONE
The default source is usually named “default.” To list sources, run:
  pactl list short sources
Paste the correct source name into Live DJ if needed.

EBMARAH 24/7 CATALOG
Open Catalog Setup and choose Upload Owned Ebmarah Masters Folder. The server streams those approved files continuously as one synchronized feed. On Air controls let either DJ skip, go back, restart, or play any catalog song immediately for every listener.

SOUNDCLOUD REVIEW
SoundCloud Discovery requires official API credentials on the server. Search by terms, genres and BPM, listen using SoundCloud, then add promising tracks to Review Queue. Approval means “contact/request authorized audio,” not permission to download or rebroadcast the SoundCloud stream.

PUBLIC LISTENERS
The GitHub Pages listener site is https://ebeinc.online/radio/. It expects a public HTTPS server base such as https://stream.ebeinc.online. Expose only the public status endpoint and the live audio mount; keep account controls private behind your LAN or Tailscale.

TROUBLESHOOTING
• Cannot connect: confirm the server is on and port 14080 is reachable.
• Stream offline: restart radio services from Server Manager.
• Mic fails: confirm pactl lists the source and no other app has exclusive control.
• Live music too quiet: adjust system microphone gain and music files before broadcast.
• No AutoDJ audio: upload at least one rights-confirmed, approved track.
"""
        text.insert("1.0",guide);text.config(state="disabled");text.pack(fill="both",expand=True)

    def refresh_status(self):
        if self.closing:
            return
        if not hasattr(self, "onair_label"):
            return
        if self.status_after_id:
            try:
                self.after_cancel(self.status_after_id)
            except Exception:
                pass
            self.status_after_id = None
        if self.status_refresh_running:
            return
        self.status_refresh_running = True
        threading.Thread(target=self._refresh_status_worker, daemon=True).start()
        self.status_drain_after_id = self.after(50, self._drain_status_queue)

    def _refresh_status_worker(self):
        try:
            s = self.api.request("GET", "/api/status", timeout=3)
            error = None
        except Exception as exc:
            s = None
            error = str(exc)
        self.status_queue.put((s, error))

    def _drain_status_queue(self):
        self.status_drain_after_id = None
        try:
            status, error = self.status_queue.get_nowait()
        except queue.Empty:
            if not self.closing:
                self.status_drain_after_id = self.after(100, self._drain_status_queue)
            return
        self._finish_status_refresh(status, error)

    def _finish_status_refresh(self, status, error):
        self.status_refresh_running = False
        if self.closing:
            return
        if error is None and status is not None:
            self._apply_status(status)
        else:
            self.onair_label.config(text=f"STATION UNAVAILABLE   •   {error}", fg="#ff9ca8")
        self.status_after_id = self.after(4000, self.refresh_status)

    def _apply_status(self, s):
        try:
            ice = s.get("icecast", {})
            live = bool(ice.get("live_source", False))
            autodj = s.get("autodj", {})
            rotation = s.get("rotation", [])
            self.current_listener = s.get("website_url") or s.get("listener_page", self.api.base_url)
            if live:
                state = "LIVE DJ TAKEOVER ON AIR"
                color = "#ff8cab"
            elif ice.get("online") and autodj.get("current_track_id"):
                state = "24/7 EBMARAH CATALOG ON AIR"
                color = "#76f0c2"
            elif ice.get("online"):
                state = "SERVER ON AIR — WAITING FOR CATALOG"
                color = "#ffcb6b"
            else:
                state = "RADIO SERVER OFFLINE"
                color = "#ff9ca8"
            self.onair_label.config(text=f"● {state}   •   {s.get('station_name', 'AllThings140Radio')}", fg=color)
            self.now_title.config(text=autodj.get("current_title") or ("Live DJ transmission" if live else "No catalog song loaded"))
            self.now_artist.config(text=autodj.get("current_artist") or (self.user.get("username", "DJ") if live else "AllThings140Radio"))
            position = float(autodj.get("position_seconds") or 0)
            duration = float(autodj.get("duration_seconds") or 0)
            progress = float(autodj.get("progress") or 0) * 100
            self.progress["value"] = progress
            self.time_label.config(text=f"{self.format_time(position)} / {self.format_time(duration)}")
            next_text = " — ".join(part for part in (autodj.get("next_artist", ""), autodj.get("next_title", "")) if part) or "—"
            self.next_label.config(text=f"NEXT: {next_text}")
            playable = len(rotation)
            catalog_total = int(s.get("catalog_tracks", s.get("approved_tracks", playable)) or 0)
            self.stats_label.config(text=f"{ice.get('listeners', 0)} listeners   •   {playable} rotation tracks / {catalog_total} catalog entries")
            if hasattr(self, "queue_count_label"):
                missing = int(s.get("missing_approved_tracks", 0) or 0)
                suffix = f" • {missing} missing audio" if missing else ""
                self.queue_count_label.config(text=f"{playable} PLAYABLE APPROVED TRACKS{suffix}")
            self.render_rotation(rotation)
            if hasattr(self, "health_labels"):
                silence = s.get("silence", {})
                disk = s.get("disk", {})
                recording = s.get("recording", {})
                storage = s.get("storage", {})
                ads = s.get("ads", {})
                watchdog = s.get("watchdog", {})
                if hasattr(self, "ops_summary"):
                    free_gb = float(disk.get("free_bytes", 0) or 0) / (1024 ** 3)
                    self.ops_summary.config(text=(
                        f"LISTENERS  {ice.get('listeners', 0)}     AUDIO  {'LIVE' if ice.get('online') else 'OFFLINE'}     "
                        f"AUTODJ  {'RUNNING' if autodj.get('running') else 'STOPPED'}     SILENCE  {str(silence.get('state', 'unknown')).upper()}\n"
                        f"WATCHDOG  {str(watchdog.get('state', 'unknown')).upper()}     RECOVERIES  {watchdog.get('recovery_count', 0)}     "
                        f"DISK FREE  {free_gb:.1f} GB ({disk.get('free_percent', 0)}%)     STORAGE  {str(storage.get('provider', 'local')).upper()}"
                    ))
                states = {
                    "SERVER": ("HEALTHY", True),
                    "ICECAST": ("HEALTHY" if ice.get("online") else "ERROR", bool(ice.get("online"))),
                    "AUTODJ": ("LIVE" if live else ("HEALTHY" if autodj.get("running") else "ERROR"), live or bool(autodj.get("running"))),
                    "ENCODER": ("HEALTHY" if autodj.get("pid") else "ERROR", bool(autodj.get("pid"))),
                    "DECODER": ("LIVE" if live else ("HEALTHY" if autodj.get("current_track_id") else "WARNING"), live or bool(autodj.get("current_track_id"))),
                    "LIVE RELAY": ("LIVE" if live else "READY", True),
                    "SILENCE": (str(silence.get("state", "UNKNOWN")).upper(), silence.get("state") not in ("warning", "error")),
                    "DISK": (str(disk.get("state", "UNKNOWN")).upper(), disk.get("state") == "healthy"),
                    "ADS": ("PLAYING" if ads.get("playing") else "READY", True),
                    "RECORDING": ("RECORDING" if recording.get("recording") else "READY", True),
                    "STORAGE": (str(storage.get("provider", "LOCAL")).upper(), True),
                }
                for key, (value, healthy) in states.items():
                    self.health_labels[key].config(text=f"{key}: {value}", fg="#76f0c2" if healthy else "#ffcb6b")
        except Exception as exc:
            self.onair_label.config(text=f"STATION UNAVAILABLE   •   {exc}", fg="#ff9ca8")

    def open_listener(self):webbrowser.open(getattr(self,"current_listener",PUBLIC_SITE))

    def show_setup_popup(self):
        messagebox.showinfo("Setup", "Install the Server .deb on the always-on computer and open Server Manager.\n\nInstall this DJ .deb on both DJ computers. Use Discover Station, then log in as ebmarah or eyewitnis with allthings140. You will be forced to create a new password.")

    def on_close(self):
        if self.closing:
            return
        self.closing = True
        if self.status_after_id:
            try:
                self.after_cancel(self.status_after_id)
            except Exception:
                pass
        if self.live_process and self.live_process.poll() is None:
            if not messagebox.askyesno("End live broadcast?","Closing the app will end the live broadcast and return listeners to AutoDJ."):
                self.closing = False
                return
            self.live_process.terminate()
            try:
                self.live_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.live_process.kill()
        self.quit()
        self.destroy()


if __name__ == "__main__":
    DJApp().mainloop()
