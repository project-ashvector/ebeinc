# RELEASE NOTES — visuals-app v0.2.2

## LIVE reconnect / UI truth / auto-recover

- On heartbeat CONNECTION LOST, Dashboard fully resyncs (no stale ● LIVE banner).
- Primary button shows `RECONNECT ● LIVE` (still re-arms lease); STOP remains explicit when live.
- `recoverWorkstationLive()` re-arms lease from last layout hash without media republish and **without** routing KV changes.
- Optional auto-recover (max 3 attempts) only when `wantLive` is set and Realtime WS is healthy.
- Manual STOP clears `wantLive` and cancels auto-recover.
- On Realtime reconnect, may adopt an already-active matching server lease or schedule recover.

No Cloudflare / GCP changes in this package.
