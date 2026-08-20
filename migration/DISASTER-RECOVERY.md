# Workstation disaster recovery

1. Confirm the public stream remains healthy; do not restart Oracle just because a laptop failed.
2. Extract the migration ZIP on a trusted replacement computer.
3. Follow `NEW-PC-SETUP.md`, enroll a new Tailscale identity and SSH key, then revoke the lost device/key.
4. Recover encrypted local secrets only from the separately protected secret backup, or rotate/reissue them.
5. Run public diagnostics before any deployment.
