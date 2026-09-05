"""Server-authoritative PLUS subscriptions; clients cannot grant entitlement."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from support_system import SupportError

ACTIVE = {"active", "trialing", "past_due", "in_grace_period"}


class SubscriptionService:
    def __init__(self, db_path, db_lock, stripe_request, event_log):
        self.db_path, self.db_lock = db_path, db_lock
        self.stripe_request, self.event_log = stripe_request, event_log

    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def init_schema(self):
        with self.db_lock, self.connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS billing_links(
                provider TEXT NOT NULL,provider_subscription_id TEXT NOT NULL,user_id TEXT NOT NULL,
                customer_id TEXT NOT NULL DEFAULT '',product_id TEXT NOT NULL,status TEXT NOT NULL,
                period_end INTEGER NOT NULL DEFAULT 0,cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL,PRIMARY KEY(provider,provider_subscription_id));
              CREATE INDEX IF NOT EXISTS billing_links_user ON billing_links(user_id,provider,updated_at);
              CREATE TABLE IF NOT EXISTS billing_webhook_events(
                provider TEXT NOT NULL,event_id TEXT NOT NULL,event_type TEXT NOT NULL,
                processed_at INTEGER NOT NULL,PRIMARY KEY(provider,event_id));""")

    @property
    def configured(self):
        return all(os.getenv(k, "").strip() for k in (
            "STRIPE_PLUS_PRICE_ID", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "BILLING_SYNC_SECRET"))

    def _json_request(self, url, headers=None, data=None):
        raw = None if data is None else json.dumps(data, separators=(",", ":")).encode()
        request = urllib.request.Request(url, data=raw, headers=headers or {}, method="GET" if data is None else "POST")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            raise SupportError("Subscription authority rejected the request.", exc.code) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SupportError("Subscription authority is temporarily unavailable.", 503) from exc

    def authenticate(self, authorization):
        if not authorization.startswith("Bearer "):
            raise SupportError("Sign in is required.", 401)
        key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
        user = self._json_request(os.getenv("SUPABASE_URL", "").rstrip("/") + "/auth/v1/user",
                                  {"apikey": key, "Authorization": authorization})
        user_id = str(user.get("id", ""))
        if not user_id:
            raise SupportError("Your account session is invalid.", 401)
        return {"id": user_id, "email": str(user.get("email", ""))}

    def checkout(self, authorization):
        if not self.configured:
            raise SupportError("PLUS checkout is not configured.", 503)
        user = self.authenticate(authorization)
        with self.connect() as db:
            active = db.execute("SELECT 1 FROM billing_links WHERE user_id=? AND status IN ('active','trialing','past_due','in_grace_period') LIMIT 1", (user["id"],)).fetchone()
        if active:
            raise SupportError("This account already has an active PLUS membership.", 409)
        site = os.environ.get("SITE_URL", "https://allthings140radio.online").rstrip("/")
        session = self.stripe_request("POST", "/v1/checkout/sessions", {
            "mode": "subscription", "client_reference_id": user["id"], "customer_email": user["email"],
            "line_items[0][price]": os.environ["STRIPE_PLUS_PRICE_ID"], "line_items[0][quantity]": 1,
            "metadata[user_id]": user["id"], "subscription_data[metadata][user_id]": user["id"],
            "success_url": site + "/?plus=success#account", "cancel_url": site + "/?plus=cancelled#account"})
        url = str(session.get("url", ""))
        if not url.startswith("https://checkout.stripe.com/"):
            raise SupportError("Stripe did not return a secure checkout.", 502)
        self.event_log("plus_checkout_started", user_id=user["id"])
        return {"url": url}

    def portal(self, authorization):
        user = self.authenticate(authorization)
        with self.connect() as db:
            row = db.execute("SELECT customer_id FROM billing_links WHERE user_id=? AND provider='stripe' AND customer_id!='' ORDER BY updated_at DESC LIMIT 1", (user["id"],)).fetchone()
        if not row:
            raise SupportError("No Stripe membership was found.", 404)
        site = os.environ.get("SITE_URL", "https://allthings140radio.online").rstrip("/")
        result = self.stripe_request("POST", "/v1/billing_portal/sessions", {"customer": row["customer_id"], "return_url": site + "/#account"})
        url = str(result.get("url", ""))
        if not url.startswith("https://billing.stripe.com/"):
            raise SupportError("Stripe did not return a secure billing portal.", 502)
        return {"url": url}

    def status(self, authorization):
        user = self.authenticate(authorization)
        with self.connect() as db:
            rows = db.execute("SELECT provider,status,period_end,cancel_at_period_end FROM billing_links WHERE user_id=? ORDER BY updated_at DESC", (user["id"],)).fetchall()
        return {"plus": any(row["status"] in ACTIVE for row in rows), "subscriptions": [dict(row) for row in rows]}

    def _sync(self, provider, sid, uid, customer, product, status, period_end=0, cancel=False, metadata=None):
        if not uid or not sid:
            raise SupportError("Subscription is missing its verified account owner.")
        with self.db_lock, self.connect() as db:
            prior = db.execute("SELECT user_id FROM billing_links WHERE provider=? AND provider_subscription_id=?", (provider, sid)).fetchone()
            if prior and prior["user_id"] != uid:
                raise SupportError("Subscription ownership cannot be changed.", 409)
            db.execute("""INSERT INTO billing_links VALUES(?,?,?,?,?,?,?,?,?)
              ON CONFLICT(provider,provider_subscription_id) DO UPDATE SET customer_id=excluded.customer_id,
              product_id=excluded.product_id,status=excluded.status,period_end=excluded.period_end,
              cancel_at_period_end=excluded.cancel_at_period_end,updated_at=excluded.updated_at""",
              (provider, sid, uid, customer, product, status, int(period_end or 0), int(cancel), int(time.time())))
        key = os.environ["SUPABASE_PUBLISHABLE_KEY"]
        self._json_request(os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/rpc/billing_apply_entitlement",
          {"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"},
          {"p_secret": os.environ["BILLING_SYNC_SECRET"], "p_provider": provider, "p_subscription_id": sid,
           "p_user_id": uid, "p_customer_id": customer, "p_product_id": product, "p_status": status,
           "p_period_end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(period_end)) if period_end else None,
           "p_cancel_at_period_end": bool(cancel), "p_metadata": metadata or {}})

    def stripe_event(self, event: dict[str, Any]):
        event_id, event_type = str(event.get("id", "")), str(event.get("type", ""))
        if not event_id.startswith("evt_"):
            raise SupportError("Invalid Stripe event.")
        with self.connect() as db:
            if db.execute("SELECT 1 FROM billing_webhook_events WHERE provider='stripe' AND event_id=?", (event_id,)).fetchone():
                return {"ok": True, "duplicate": True}
        obj, relevant = event.get("data", {}).get("object", {}), False
        if event_type == "checkout.session.completed" and obj.get("mode") == "subscription":
            obj = self.stripe_request("GET", "/v1/subscriptions/" + urllib.parse.quote(str(obj.get("subscription", ""))))
            relevant = True
        elif event_type.startswith("customer.subscription."):
            relevant = True
        if relevant:
            item = (((obj.get("items") or {}).get("data")) or [{}])[0]
            price = item.get("price") or {}
            if str(price.get("id", "")) != os.environ.get("STRIPE_PLUS_PRICE_ID", ""):
                raise SupportError("Unknown Stripe subscription product.")
            period_end = int(obj.get("current_period_end") or item.get("current_period_end") or 0)
            self._sync("stripe", str(obj.get("id", "")), str((obj.get("metadata") or {}).get("user_id", "")),
                       str(obj.get("customer", "")), str(price.get("id", "")), str(obj.get("status", "")),
                       period_end, bool(obj.get("cancel_at_period_end")), {"event": event_type})
        with self.db_lock, self.connect() as db:
            db.execute("INSERT OR IGNORE INTO billing_webhook_events VALUES(?,?,?,?)", ("stripe", event_id, event_type, int(time.time())))
        return {"ok": True, "duplicate": False, "subscription": relevant}
