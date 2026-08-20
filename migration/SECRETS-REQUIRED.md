# Secrets required (names only)

- `ADMIN_TOKEN` / manager credentials: authenticated control operations.
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`: support Checkout and verified webhooks.
- Icecast source/admin passwords: encoder and administration.
- Cloudflare Tunnel credentials/API authorization: public routing/deployments.
- Oracle SSH private key: unique per controller; never copy casually.
- Tailscale device authorization: private control network.
- rclone Google Drive authorization: master library/backup access.
- Android signing keystore, alias and passwords: release identity continuity.
- Discord/email provider credentials when those integrations are enabled.

Store values in protected OS/service environments. The migration ZIP intentionally contains none.
