# Computer roles

- **Production Oracle server:** sole broadcast/timeline authority, encoder, API, hot cache and database.
- **Primary workstation:** development, release packaging and authenticated administration; never required for playback.
- **Secondary controllers:** read-only monitoring by default, explicit admin actions over Tailscale, unique SSH/device identities.
- **Android phone:** public listener client and Android Auto host; contains no admin secret.
- **Automotive device:** installs the listener application and consumes the same public live feed.

Revoke a lost PC in Tailscale and remove its SSH public key without changing the station timeline.
