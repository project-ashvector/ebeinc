import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from subscription_system import SubscriptionService
from support_system import SupportError


class SubscriptionSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []
        self.stripe_calls = []

        def stripe(method, path, fields=None):
            self.stripe_calls.append((method, path, fields))
            if path.startswith("/v1/subscriptions/"):
                return self.subscription()
            if path == "/v1/checkout/sessions":
                return {"url": "https://checkout.stripe.com/c/pay/test"}
            return {"url": "https://billing.stripe.com/p/session/test"}

        self.service = SubscriptionService(str(Path(self.temp.name) / "test.db"), threading.RLock(), stripe, lambda *a, **k: None)
        self.service.init_schema()
        self.env = patch.dict(os.environ, {
            "STRIPE_PLUS_PRICE_ID": "price_plus", "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "public-key", "BILLING_SYNC_SECRET": "server-secret",
            "SITE_URL": "https://allthings140radio.online",
        }, clear=False)
        self.env.start()
        self.service._json_request = self.json_request

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def json_request(self, url, headers=None, data=None):
        self.calls.append((url, headers, data))
        if url.endswith("/auth/v1/user"):
            return {"id": "11111111-1111-1111-1111-111111111111", "email": "listener@example.com"}
        return {}

    @staticmethod
    def subscription(status="active", sid="sub_1"):
        return {"id": sid, "customer": "cus_1", "status": status, "metadata": {"user_id": "11111111-1111-1111-1111-111111111111"},
                "items": {"data": [{"current_period_end": 2_000_000_000, "price": {"id": "price_plus"}}]}}

    def event(self, status="active", event_id="evt_1", sid="sub_1"):
        return {"id": event_id, "type": "customer.subscription.updated", "data": {"object": self.subscription(status, sid)}}

    def test_checkout_requires_auth_and_uses_fixed_price(self):
        with self.assertRaises(SupportError) as error:
            self.service.checkout("")
        self.assertEqual(error.exception.status, 401)
        result = self.service.checkout("Bearer real-session")
        self.assertTrue(result["url"].startswith("https://checkout.stripe.com/"))
        fields = self.stripe_calls[-1][2]
        self.assertEqual(fields["line_items[0][price]"], "price_plus")
        self.assertEqual(fields["subscription_data[metadata][user_id]"], "11111111-1111-1111-1111-111111111111")
        self.assertNotIn("trial_period_days", fields)

    def test_verified_event_syncs_and_replay_is_idempotent(self):
        first = self.service.stripe_event(self.event())
        second = self.service.stripe_event(self.event())
        self.assertTrue(first["subscription"])
        self.assertTrue(second["duplicate"])
        rpc_calls = [call for call in self.calls if "/rest/v1/rpc/" in call[0]]
        self.assertEqual(len(rpc_calls), 1)
        self.assertEqual(rpc_calls[0][2]["p_status"], "active")
        self.assertEqual(self.service.status("Bearer real-session")["plus"], True)

    def test_subscription_owner_cannot_change(self):
        self.service.stripe_event(self.event())
        changed = self.event(event_id="evt_2")
        changed["data"]["object"]["metadata"]["user_id"] = "22222222-2222-2222-2222-222222222222"
        with self.assertRaises(SupportError) as error:
            self.service.stripe_event(changed)
        self.assertEqual(error.exception.status, 409)

    def test_unknown_product_is_rejected(self):
        event = self.event()
        event["data"]["object"]["items"]["data"][0]["price"]["id"] = "price_wrong"
        with self.assertRaises(SupportError):
            self.service.stripe_event(event)

    def test_cancellation_updates_status(self):
        self.service.stripe_event(self.event())
        self.service.stripe_event(self.event("canceled", "evt_2"))
        self.assertFalse(self.service.status("Bearer real-session")["plus"])


if __name__ == "__main__":
    unittest.main()
