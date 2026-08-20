# ALLTHINGS140 Radio Support System Setup

## What is implemented

The listener site now has a Stripe-hosted one-time tip flow with $5, $10, $20, $50, and custom USD amounts ($1–$1,000). A supporter can optionally publish a display name and plain-text message. Verified tips power the recent-supporter feed, live neon notification, configurable goal, and authenticated DJ Support dashboard.

The browser never marks a tip paid. Only a signature-verified Stripe webhook can do that. Stripe event IDs and Checkout Session IDs are unique in SQLite, duplicate webhooks are safe, failed/expired payments do not count, and refunds subtract from totals. The support code is separate from AutoDJ and cannot issue playback commands.

## Stripe account and Test Mode setup

1. Sign in at `https://dashboard.stripe.com/` and select a Sandbox/Test environment.
2. Open Developers/Workbench → API keys.
3. Copy the test publishable key (`pk_test_...`) and reveal/copy the test secret key (`sk_test_...`).
4. Put the values in the Oracle service environment described below. Do not paste them into frontend files or Git.
5. Open Developers/Workbench → Webhooks → Create destination → Webhook endpoint.
6. Use this exact endpoint URL:

   `https://allthings140radio.online/api/public/support/webhook`

7. Subscribe to these events:

   - `checkout.session.completed`
   - `checkout.session.async_payment_succeeded`
   - `checkout.session.async_payment_failed`
   - `checkout.session.expired`
   - `charge.refunded`

8. Copy that endpoint's signing secret (`whsec_...`) into `STRIPE_WEBHOOK_SECRET`. Test and live endpoints have different secrets.

The backend creates a fresh Stripe Checkout Session for the server-validated amount. Stripe hosts all card fields. Cards and compatible wallets are selected by Stripe; enable Apple Pay and Google Pay under Stripe Dashboard → Settings → Payment methods if they are not already enabled.

## Environment variables

Production variables belong in the server's protected systemd environment file, not Cloudflare Pages and not browser JavaScript:

```dotenv
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
SITE_URL=https://allthings140radio.online
VENMO_SUPPORT_URL=
```

`STRIPE_PUBLISHABLE_KEY` is reserved for future client-side Stripe features; hosted Checkout currently requires no frontend key. Set `VENMO_SUPPORT_URL` only to an HTTPS Venmo Business destination. When blank or invalid, the button is hidden.

On Oracle, create `/etc/allthings140radio/support.env` owned by root with mode `0600`, add `EnvironmentFile=/etc/allthings140radio/support.env` to the radio service override, run `systemctl daemon-reload`, then restart only the API service during a planned deployment. Never print the file in logs.

## Test payments

Use Stripe Test Mode—never real card details. Stripe's successful interactive test card is `4242 4242 4242 4242`, with any future date and any three-digit CVC. `4000 0000 0000 0002` simulates a decline.

Test $5, $10, a custom amount, cancel, decline, anonymous/public, a message, and markup such as `<script>alert(1)</script>`. The markup must appear only as sanitized text, never executable HTML. In Stripe's webhook delivery history, resend the same event; the dashboard total must remain unchanged. Create a test refund and confirm the goal decreases by the refunded amount.

The automated suite is:

```bash
python3 -m unittest tests.test_support_system -v
```

It covers amount validation, anonymous privacy, sanitization, signature rejection, paid webhook processing, duplicate delivery, failure state, and refund accounting.

## Goal, feed, moderation, and Venmo

Open the existing ALLTHINGS140 Radio DJ app, sign in as an administrator, and select **Support**. The dashboard shows today/week/month/all-time totals and safe transaction fields. From there you can edit the goal title, description, target, visibility, feed visibility, and live notifications. A manager or administrator can hide an entire supporter entry, hide only its message, or restore it. No email, billing data, card data, IP, Stripe customer ID, or full payment payload is stored or displayed.

The database tables are `support_transactions`, `support_webhook_events`, and singleton `support_settings` in the existing station SQLite database. The reusable internal completion object is represented by the safe `support_transactions` row and the `support_webhook_processed` operational event. It includes the support ID, amount/currency, public name/message, timestamp, provider, and payment reference for future on-air automation; payment references never reach the public API.

## Disable components

- Remove/blank Stripe variables and restart: Checkout is disabled and the UI clearly says setup is in progress.
- Blank `VENMO_SUPPORT_URL`: Venmo disappears.
- Use the DJ Support tab: disable the goal, public feed, or live notifications independently.
- Hide an individual entry/message from the same tab.

Existing verified records remain in SQLite when presentation is disabled.

## Deployment

1. Back up the project, Oracle server package/config, and station database.
2. Run Python compilation, unit tests, JS syntax checks, and existing radio tests.
3. Install `tools/server.py`, `tools/support_system.py`, and the updated DJ app through the existing package/deployment process.
4. Configure Test Mode environment variables and webhook.
5. Restart the API service once. AutoDJ/encoder/Icecast should remain independently healthy; verify the stream before and after.
6. Deploy `radio/` to the existing Cloudflare Pages project using Wrangler.
7. Confirm `/api/public/support` returns no-store JSON and the webhook route reaches Oracle.
8. Complete the full Test Mode matrix before accepting live money.

## Switching to live mode

1. Complete Stripe account/business verification and bank payout setup.
2. In Stripe live mode, enable cards and desired wallets.
3. Create a new live webhook destination with the same URL and event list.
4. During a planned change window, replace `sk_test_...` with `sk_live_...`, `pk_test_...` with `pk_live_...`, and the test `whsec_...` with the new live endpoint secret.
5. Restart the API, verify `stripe_configured` in the authenticated Support dashboard, and make one small real tip.
6. Confirm the payment is paid in Stripe, appears once in the DJ dashboard, updates the public goal once, and refunds correctly. Do not use Stripe test card numbers in live mode.

## Troubleshooting

- Checkout disabled: verify all three Stripe variables exist in the service environment and restart the API.
- Checkout returns 502/503: inspect `journalctl -u allthings140radio-server` for `support_stripe_error` or `support_stripe_unavailable` (no secrets are logged).
- Success page keeps confirming: inspect Stripe webhook delivery status and confirm its signing secret matches the environment/mode.
- Duplicate total: inspect `support_webhook_events`; its primary key prevents replay. Never manually delete webhook event rows without a recovery plan.
- Goal does not move: only `paid` webhook-confirmed records count. Pending, failed, expired, or checkout-created records do not.
- Feed absent: confirm the supporter opted in and both feed visibility and entry visibility are enabled.
- Public API check: `curl -fsS https://allthings140radio.online/api/public/support`
- Service log: `sudo journalctl -u allthings140radio-server --since "1 hour ago" | grep support_`
- Stripe delivery log: Dashboard → Developers/Workbench → Webhooks → destination → Event deliveries.

Back up `/var/lib/allthings140radio/station.db` before manual database work. Never modify payment status by hand unless reconciling against Stripe records under a documented recovery procedure.
