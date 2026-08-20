# Migration guide

The production server does not migrate merely because the primary laptop changes. Enroll the new PC in Tailscale, install its unique SSH key, clone/extract this package, restore protected local configuration, and run diagnostics. Use the control API through Tailscale/MagicDNS. Never expose ports 14080 or 14083 publicly. For an Oracle replacement, follow `SERVER-RECOVERY.md` and cut over Cloudflare Tunnel only after audio and metadata advance.
