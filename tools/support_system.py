"""Stripe-backed listener support for AllThings140Radio.

This module is deliberately independent of the playback engine. Listener and
payment requests can never mutate the station timeline.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable


class SupportError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class SupportService:
    MIN_CENTS = 100
    MAX_CENTS = 100_000
    NAME_LIMIT = 40
    MESSAGE_LIMIT = 180
    WEBHOOK_TOLERANCE = 300

    def __init__(self, db_path: str, db_lock: threading.RLock, event_log: Callable[..., None]) -> None:
        self.db_path = db_path
        self.db_lock = db_lock
        self.event_log = event_log

    @property
    def stripe_key(self) -> str:
        return os.environ.get("STRIPE_SECRET_KEY", "").strip()

    @property
    def webhook_secret(self) -> str:
        return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()

    @property
    def site_url(self) -> str:
        value = os.environ.get("SITE_URL", "https://allthings140radio.online").strip().rstrip("/")
        return value if value.startswith("https://") else "https://allthings140radio.online"

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def init_schema(self) -> None:
        with self.db_lock, self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS support_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    support_id TEXT NOT NULL UNIQUE,
                    provider TEXT NOT NULL DEFAULT 'stripe',
                    provider_session_id TEXT UNIQUE,
                    provider_payment_id TEXT,
                    amount_cents INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'usd',
                    display_name TEXT NOT NULL DEFAULT 'Anonymous',
                    supporter_message TEXT NOT NULL DEFAULT '',
                    public_display INTEGER NOT NULL DEFAULT 0,
                    public_visible INTEGER NOT NULL DEFAULT 1,
                    message_visible INTEGER NOT NULL DEFAULT 1,
                    payment_status TEXT NOT NULL DEFAULT 'pending',
                    refunded_cents INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    completed_at INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS support_paid_time
                    ON support_transactions(payment_status, completed_at);
                CREATE INDEX IF NOT EXISTS support_payment_reference
                    ON support_transactions(provider_payment_id);
                CREATE TABLE IF NOT EXISTS support_webhook_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    processed_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS support_settings (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    goal_title TEXT NOT NULL DEFAULT 'KEEP 140 ONLINE',
                    goal_description TEXT NOT NULL DEFAULT 'Help power the station and keep underground bass music broadcasting 24/7.',
                    goal_target_cents INTEGER NOT NULL DEFAULT 15000,
                    goal_start INTEGER NOT NULL DEFAULT 0,
                    goal_reset_mode TEXT NOT NULL DEFAULT 'never',
                    goal_enabled INTEGER NOT NULL DEFAULT 1,
                    public_feed_enabled INTEGER NOT NULL DEFAULT 1,
                    live_notifications_enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at INTEGER NOT NULL
                );
            """)
            db.execute("INSERT OR IGNORE INTO support_settings(id,updated_at) VALUES(1,?)", (int(time.time()),))
            db.commit()

    @staticmethod
    def clean_text(value: Any, limit: int) -> str:
        text = str(value or "")
        text = re.sub(r"<[^>]*>", "", text)
        text = "".join(char for char in text if char in "\n\t" or ord(char) >= 32)
        return re.sub(r"\s+", " ", text).strip()[:limit]

    def validate_tip(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            amount = int(data.get("amount_cents"))
        except (TypeError, ValueError):
            raise SupportError("Choose a valid support amount.")
        if not self.MIN_CENTS <= amount <= self.MAX_CENTS:
            raise SupportError("Support must be between $1 and $1,000.")
        public = data.get("public_display") is True
        name = self.clean_text(data.get("display_name"), self.NAME_LIMIT) if public else "Anonymous"
        message = self.clean_text(data.get("message"), self.MESSAGE_LIMIT) if public else ""
        return {"amount_cents": amount, "public_display": public, "display_name": name or "Anonymous", "message": message}

    def stripe_request(self, method: str, path: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.stripe_key:
            raise SupportError("Stripe test checkout is not configured yet.", 503)
        encoded = urllib.parse.urlencode(fields or {}).encode()
        request = urllib.request.Request(
            "https://api.stripe.com" + path,
            data=encoded if method != "GET" else None,
            method=method,
            headers={"Authorization": f"Bearer {self.stripe_key}", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "AllThings140Radio-Support/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode()).get("error", {}).get("message", "Stripe rejected the request")
            except Exception:
                detail = "Stripe rejected the request"
            self.event_log("support_stripe_error", status=exc.code)
            raise SupportError(str(detail)[:200], 502) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            self.event_log("support_stripe_unavailable")
            raise SupportError("Secure checkout is temporarily unavailable.", 503) from exc

    def create_checkout(self, data: dict[str, Any]) -> dict[str, Any]:
        tip = self.validate_tip(data)
        now = int(time.time())
        support_id = "sup_" + uuid.uuid4().hex
        with self.db_lock, self.connect() as db:
            db.execute("""INSERT INTO support_transactions
                (support_id,amount_cents,currency,display_name,supporter_message,public_display,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)""", (support_id, tip["amount_cents"], "usd", tip["display_name"], tip["message"], int(tip["public_display"]), now, now))
            db.commit()
        fields = {
            "mode": "payment", "client_reference_id": support_id,
            "metadata[support_id]": support_id,
            "payment_intent_data[metadata][support_id]": support_id,
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][product_data][name]": "Support ALLTHINGS140 Radio",
            "line_items[0][price_data][product_data][description]": "One-time tip to help keep the station broadcasting 24/7",
            "line_items[0][price_data][unit_amount]": tip["amount_cents"],
            "line_items[0][quantity]": 1,
            "success_url": self.site_url + "/?support=success&session_id={CHECKOUT_SESSION_ID}#support",
            "cancel_url": self.site_url + "/?support=cancelled#support",
        }
        try:
            session = self.stripe_request("POST", "/v1/checkout/sessions", fields)
        except Exception:
            with self.db_lock, self.connect() as db:
                db.execute("UPDATE support_transactions SET payment_status='checkout_failed',updated_at=? WHERE support_id=?", (int(time.time()), support_id))
                db.commit()
            raise
        if not session.get("id") or not str(session.get("url", "")).startswith("https://checkout.stripe.com/"):
            raise SupportError("Stripe did not return a secure checkout.", 502)
        with self.db_lock, self.connect() as db:
            db.execute("UPDATE support_transactions SET provider_session_id=?,updated_at=? WHERE support_id=?", (session["id"], int(time.time()), support_id))
            db.commit()
        self.event_log("support_checkout_started", support_id=support_id, amount_cents=tip["amount_cents"])
        return {"url": session["url"]}

    def verify_signature(self, raw: bytes, signature: str, now: int | None = None) -> None:
        if not self.webhook_secret:
            raise SupportError("Stripe webhook is not configured.", 503)
        parts: dict[str, list[str]] = {}
        for item in signature.split(","):
            key, _, value = item.partition("=")
            parts.setdefault(key, []).append(value)
        try:
            timestamp = int(parts["t"][0])
        except (KeyError, ValueError, IndexError):
            raise SupportError("Invalid Stripe signature.", 400)
        if abs(int(now or time.time()) - timestamp) > self.WEBHOOK_TOLERANCE:
            raise SupportError("Expired Stripe signature.", 400)
        expected = hmac.new(self.webhook_secret.encode(), str(timestamp).encode() + b"." + raw, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", [])):
            raise SupportError("Invalid Stripe signature.", 400)

    def process_webhook(self, raw: bytes, signature: str) -> dict[str, Any]:
        self.verify_signature(raw, signature)
        try:
            event = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SupportError("Invalid Stripe event.")
        event_id, event_type = str(event.get("id", "")), str(event.get("type", ""))
        obj = event.get("data", {}).get("object", {})
        if not event_id.startswith("evt_") or not isinstance(obj, dict):
            raise SupportError("Invalid Stripe event.")
        expected_live = self.stripe_key.startswith("sk_live_")
        if self.stripe_key and bool(event.get("livemode")) != expected_live:
            raise SupportError("Stripe mode mismatch.")
        now = int(time.time())
        completed: dict[str, Any] | None = None
        with self.db_lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM support_webhook_events WHERE event_id=?", (event_id,)).fetchone():
                db.rollback()
                return {"ok": True, "duplicate": True}
            if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"} and obj.get("payment_status") == "paid":
                support_id = str(obj.get("client_reference_id") or obj.get("metadata", {}).get("support_id") or "")
                session_id = str(obj.get("id", ""))
                amount, currency = int(obj.get("amount_total") or 0), str(obj.get("currency", "")).lower()
                row = db.execute("SELECT * FROM support_transactions WHERE support_id=? AND provider_session_id=?", (support_id, session_id)).fetchone()
                if not row or amount != int(row["amount_cents"]) or currency != "usd":
                    db.rollback()
                    raise SupportError("Stripe payment does not match its support record.")
                db.execute("""UPDATE support_transactions SET provider_payment_id=?,payment_status='paid',completed_at=CASE WHEN completed_at=0 THEN ? ELSE completed_at END,updated_at=? WHERE id=?""",
                           (str(obj.get("payment_intent") or "")[:255], now, now, row["id"]))
                completed = dict(row)
            elif event_type in {"checkout.session.expired", "checkout.session.async_payment_failed"}:
                status = "cancelled" if event_type.endswith("expired") else "failed"
                db.execute("UPDATE support_transactions SET payment_status=?,updated_at=? WHERE provider_session_id=? AND payment_status!='paid'", (status, now, str(obj.get("id", ""))))
            elif event_type == "charge.refunded":
                db.execute("UPDATE support_transactions SET refunded_cents=MIN(amount_cents,?),updated_at=? WHERE provider_payment_id=?", (max(0, int(obj.get("amount_refunded") or 0)), now, str(obj.get("payment_intent") or "")))
            db.execute("INSERT INTO support_webhook_events(event_id,event_type,processed_at) VALUES(?,?,?)", (event_id, event_type, now))
            db.commit()
        self.event_log("support_webhook_processed", stripe_event_type=event_type, support_id=(completed or {}).get("support_id", ""))
        return {"ok": True, "duplicate": False}

    def public_state(self, since: int = 0) -> dict[str, Any]:
        with self.db_lock, self.connect() as db:
            settings = dict(db.execute("SELECT * FROM support_settings WHERE id=1").fetchone())
            start = int(settings["goal_start"] or 0)
            if settings["goal_reset_mode"] == "monthly":
                local = time.localtime()
                start = max(start, int(time.mktime((local.tm_year, local.tm_mon, 1, 0, 0, 0, 0, 0, -1))))
            total = db.execute("SELECT COALESCE(SUM(amount_cents-refunded_cents),0) FROM support_transactions WHERE payment_status='paid' AND completed_at>=?", (start,)).fetchone()[0]
            rows = db.execute("""SELECT id,support_id,amount_cents-refunded_cents AS amount_cents,currency,display_name,
                CASE WHEN message_visible=1 THEN supporter_message ELSE '' END AS message,completed_at
                FROM support_transactions WHERE payment_status='paid' AND public_display=1 AND public_visible=1
                ORDER BY id DESC LIMIT 12""").fetchall()
        venmo = os.environ.get("VENMO_SUPPORT_URL", "").strip()
        if not re.fullmatch(r"https://[^\s]+", venmo):
            venmo = ""
        return {
            "stripe_enabled": bool(self.stripe_key and self.webhook_secret), "minimum_cents": self.MIN_CENTS,
            "venmo_url": venmo,
            "goal": {"title": settings["goal_title"], "description": settings["goal_description"], "target_cents": settings["goal_target_cents"], "total_cents": int(total), "enabled": bool(settings["goal_enabled"]), "reset_mode": settings["goal_reset_mode"]},
            "public_feed_enabled": bool(settings["public_feed_enabled"]), "live_notifications_enabled": bool(settings["live_notifications_enabled"]),
            "supporters": [dict(row) for row in rows] if settings["public_feed_enabled"] else [],
        }

    def checkout_status(self, session_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"cs_(?:test_|live_)?[A-Za-z0-9]+", session_id):
            raise SupportError("Invalid checkout session.")
        with self.db_lock, self.connect() as db:
            row = db.execute("SELECT payment_status FROM support_transactions WHERE provider_session_id=?", (session_id,)).fetchone()
        return {"verified": bool(row and row["payment_status"] == "paid"), "status": row["payment_status"] if row else "unknown"}

    def dashboard(self) -> dict[str, Any]:
        now = int(time.time())
        local = time.localtime(now)
        today = int(time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1)))
        week = today - ((local.tm_wday) * 86400)
        month = int(time.mktime((local.tm_year, local.tm_mon, 1, 0, 0, 0, 0, 0, -1)))
        with self.db_lock, self.connect() as db:
            def metric(start: int) -> dict[str, int]:
                row = db.execute("SELECT COALESCE(SUM(amount_cents-refunded_cents),0),COUNT(*) FROM support_transactions WHERE payment_status='paid' AND completed_at>=?", (start,)).fetchone()
                return {"total_cents": int(row[0]), "supporters": int(row[1])}
            metrics = {"today": metric(today), "week": metric(week), "month": metric(month), "all_time": metric(0)}
            recent = [dict(row) for row in db.execute("""SELECT id,support_id,created_at,completed_at,amount_cents,currency,display_name,supporter_message,public_display,public_visible,message_visible,provider,payment_status,refunded_cents FROM support_transactions ORDER BY id DESC LIMIT 100""").fetchall()]
            settings = dict(db.execute("SELECT * FROM support_settings WHERE id=1").fetchone())
        return {"metrics": metrics, "recent": recent, "settings": settings, "stripe_configured": bool(self.stripe_key and self.webhook_secret), "venmo_configured": bool(os.environ.get("VENMO_SUPPORT_URL", "").strip())}

    def update_settings(self, data: dict[str, Any]) -> None:
        title = self.clean_text(data.get("goal_title"), 80) or "KEEP 140 ONLINE"
        description = self.clean_text(data.get("goal_description"), 240)
        try: target = int(data.get("goal_target_cents"))
        except (TypeError, ValueError): raise SupportError("Goal target must be a whole number of cents.")
        if not 100 <= target <= 100_000_000: raise SupportError("Goal target must be between $1 and $1,000,000.")
        reset = str(data.get("goal_reset_mode", "never"))
        if reset not in {"never", "monthly", "manual"}: raise SupportError("Invalid goal reset mode.")
        start = int(data.get("goal_start") or 0)
        with self.db_lock, self.connect() as db:
            db.execute("""UPDATE support_settings SET goal_title=?,goal_description=?,goal_target_cents=?,goal_start=?,goal_reset_mode=?,goal_enabled=?,public_feed_enabled=?,live_notifications_enabled=?,updated_at=? WHERE id=1""",
                       (title, description, target, max(0, start), reset, int(data.get("goal_enabled") is True), int(data.get("public_feed_enabled") is True), int(data.get("live_notifications_enabled") is True), int(time.time())))
            db.commit()

    def moderate(self, transaction_id: int, public_visible: bool, message_visible: bool) -> None:
        with self.db_lock, self.connect() as db:
            cursor = db.execute("UPDATE support_transactions SET public_visible=?,message_visible=?,updated_at=? WHERE id=?", (int(public_visible), int(message_visible), int(time.time()), transaction_id))
            db.commit()
        if cursor.rowcount != 1: raise SupportError("Support entry not found.", 404)
