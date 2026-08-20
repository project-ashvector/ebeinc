# New PC setup

Supported baseline: current Ubuntu/Zorin-family Linux.

1. Extract `allthings140radio-backup-migration.zip` into a private working folder.
2. Run `./setup-allthings140radio.sh --dry-run`, review it, then run `./setup-allthings140radio.sh`.
3. Install/login to Tailscale and have an existing tailnet administrator authorize the device.
4. Add your own SSH public key to the Oracle server; do not share another computer's private key.
5. Configure rclone interactively only if this computer needs Drive administration.
6. Restore environment values named in `SECRETS-REQUIRED.md` into protected files outside Git.
7. Run `./setup-allthings140radio.sh --diagnose`.
8. Build Android with the documented signing key only after confirming certificate continuity.

The server keeps broadcasting during all workstation setup.
