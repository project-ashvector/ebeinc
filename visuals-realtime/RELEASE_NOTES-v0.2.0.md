# Visuals Realtime 0.2.0-staging

- Active layouts, schedules, renderer sessions, acknowledgements and Visuals broadcasts are explicitly scoped to `green-staging` or `live`.
- Missing, conflicting or unknown environment identities fail closed.
- Green and Live publishing use different credentials; startup rejects missing or shared credentials.
- Existing preview state migrates idempotently to Green, while non-preview state migrates to Live. The legacy row is retained for rollback evidence.
- Malformed stored layout JSON is logged and contained without crashing the service or crossing environments.
- Empty origin configuration now prevents startup.
- Layout validation rejects duplicate playlist asset IDs and invalid hosted media entries.

The service remains independent of Icecast, AutoDJ and all production radio processes.
