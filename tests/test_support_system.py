import hashlib
import hmac
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from support_system import SupportError, SupportService


class SupportSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.events = []
        self.service = SupportService(str(Path(self.temp.name) / "test.db"), threading.RLock(), lambda event, **fields: self.events.append((event, fields)))
        self.service.init_schema()
        self.env = patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_example", "STRIPE_WEBHOOK_SECRET": "whsec_test", "SITE_URL": "https://allthings140radio.online"}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def checkout(self, cents=500, public=True, name="BassGoblin420", message="Keep 140 alive 🔥"):
        with patch.object(self.service, "stripe_request", return_value={"id": "cs_test_" + str(cents), "url": "https://checkout.stripe.com/c/pay/test"}):
            result = self.service.create_checkout({"amount_cents": cents, "public_display": public, "display_name": name, "message": message})
        self.assertTrue(result["url"].startswith("https://checkout.stripe.com/"))
        with self.service.connect() as db:
            return dict(db.execute("SELECT * FROM support_transactions ORDER BY id DESC LIMIT 1").fetchone())

    def signed_event(self, event):
        raw = json.dumps(event, separators=(",", ":")).encode()
        timestamp = int(time.time())
        digest = hmac.new(b"whsec_test", str(timestamp).encode() + b"." + raw, hashlib.sha256).hexdigest()
        return raw, f"t={timestamp},v1={digest}"

    def paid_event(self, row, event_id="evt_paid_1"):
        return {"id": event_id, "type": "checkout.session.completed", "livemode": False, "data": {"object": {"id": row["provider_session_id"], "client_reference_id": row["support_id"], "metadata": {"support_id": row["support_id"]}, "payment_status": "paid", "amount_total": row["amount_cents"], "currency": "usd", "payment_intent": "pi_test_1"}}}

    def test_suggested_and_custom_amounts(self):
        for cents in (500, 1000, 1234): self.checkout(cents)
        for cents in (0, -500, 100001):
            with self.assertRaises(SupportError): self.service.validate_tip({"amount_cents": cents})

    def test_anonymous_discards_name_and_message(self):
        row = self.checkout(public=False, name="Real Name", message="private")
        self.assertEqual(row["display_name"], "Anonymous")
        self.assertEqual(row["supporter_message"], "")

    def test_markup_is_plain_text_and_bounded(self):
        row = self.checkout(name="<img src=x>Goblin", message="<script>alert(1)</script> keep it loud")
        self.assertNotIn("<", row["display_name"] + row["supporter_message"])
        self.assertLessEqual(len(row["supporter_message"]), 180)

    def test_verified_payment_counts_once(self):
        row = self.checkout(2000)
        raw, signature = self.signed_event(self.paid_event(row))
        self.assertFalse(self.service.process_webhook(raw, signature)["duplicate"])
        self.assertTrue(self.service.process_webhook(raw, signature)["duplicate"])
        state = self.service.public_state()
        self.assertEqual(state["goal"]["total_cents"], 2000)
        self.assertEqual(len(state["supporters"]), 1)

    def test_bad_signature_and_amount_mismatch_are_rejected(self):
        row = self.checkout()
        raw, signature = self.signed_event(self.paid_event(row))
        with self.assertRaises(SupportError): self.service.process_webhook(raw, signature + "bad")
        event = self.paid_event(row, "evt_wrong_amount");event["data"]["object"]["amount_total"] = 999
        raw, signature = self.signed_event(event)
        with self.assertRaises(SupportError): self.service.process_webhook(raw, signature)

    def test_failed_cancelled_and_refund_accounting(self):
        row = self.checkout(1000)
        raw, signature = self.signed_event(self.paid_event(row));self.service.process_webhook(raw, signature)
        refund = {"id": "evt_refund", "type": "charge.refunded", "livemode": False, "data": {"object": {"payment_intent": "pi_test_1", "amount_refunded": 400}}}
        raw, signature = self.signed_event(refund);self.service.process_webhook(raw, signature)
        self.assertEqual(self.service.public_state()["goal"]["total_cents"], 600)
        failed = self.checkout(500);event={"id":"evt_failed","type":"checkout.session.async_payment_failed","livemode":False,"data":{"object":{"id":failed["provider_session_id"]}}}
        raw,signature=self.signed_event(event);self.service.process_webhook(raw,signature)
        with self.service.connect() as db:self.assertEqual(db.execute("SELECT payment_status FROM support_transactions WHERE id=?",(failed["id"],)).fetchone()[0],"failed")


if __name__ == "__main__": unittest.main()
