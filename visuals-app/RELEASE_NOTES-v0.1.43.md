# ALLTHINGS140Radio Visuals 0.1.43 RC1

Local release candidate only. Not deployed to Green or production.

## Fixed

- Green cycle testing now publishes the complete enabled Visuals rotation instead of persisting a single selected preview with an empty playlist.
- The selected Visual is placed first without dropping the remainder of the ordered library.
- Duplicate enabled asset IDs fail preflight instead of creating ambiguous rotation entries.
- WebSocket callbacks are generation-safe, and reconnect/shutdown cannot let a stale socket replace the current connection.
- The localhost media server uses eight bounded workers, a bounded queue, read/write deadlines, overload responses and explicit shutdown signaling while retaining byte ranges.
- Media routes discard missing paths and are capped; probe memory and on-disk index growth are capped.
- `media-index.json` and workstation state use flushed atomic replacement. Invalid current state is preserved before recovery.
- State loading validates schema, preset references, layer IDs, finite geometry, ranges and top-level collection types while accepting recoverable schema-3 legacy state.
- Completed/cancelled publish IDs are cleaned and the cancellation collection is bounded.
- Takeover SSH and legacy publishing subprocesses now have connection and wall-clock timeouts with child reap behavior.
- A PID-aware single-instance lock prevents simultaneous state writers and recovers from stale crash locks.
- Public `/room/` routing changes now require an explicit typed production confirmation at both UI and backend boundaries.
- Tauri media scopes use `$HOME` rather than one fixed Linux username; existing absolute state paths remain compatible.

## Verification

- Existing rollout, Green cutover, workstation UI, renderer contract and geometry suites pass.
- New cycle contract tests cover complete-list serialization, disabled items, selected-first ordering and duplicate filenames.
- Rust tests cover semantic state rejection, atomic writes, cancellation cleanup, duplicate asset IDs and parallel byte-range serving.
- A bounded local binary soak and package inspection are recorded in the Phase 3 report.

## Known limitations

- No Green or production deployment is part of this release candidate.
- Green/live hard isolation remains a separate infrastructure phase.
- The current Green renderer retains its established random anti-repeat selection after the deterministic selected-first seed; changing renderer navigation semantics belongs to the later Green phase.
- This phase is a bounded local soak, not a multi-day reliability claim.
