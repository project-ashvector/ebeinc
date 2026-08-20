# Background playback reliability

## Authoritative path

The listener receives one continuous MP3 broadcast. The browser never selects,
starts, seeks, skips, or advances station tracks.

`AutoDJ/guest source -> persistent FFmpeg encoder -> loopback Icecast :14000 -> Oracle cloudflared -> stream.ebeinc.online/live.mp3 -> one HTMLAudioElement`

Metadata follows a separate read-only path:

`Oracle public gateway :14082 -> status.ebeinc.online/api/public/status -> browser`

The status response contains `station_generation_id`, monotonic
`station_sequence`, `server_time`, track start/position/duration, next track,
mode, takeover, advertisement-derived sequence changes, and stream health.
Status reads do not mutate AutoDJ.

## Resume behavior (frontend 1.6.1)

The client has one audio element and no WebSocket, SSE, Web Audio, or
client-coordinated playlist. It listens for `visibilitychange`, `pageshow`,
`focus`, `online`, document `freeze`, and document `resume`.

On resume it performs one deduplicated recovery transaction:

1. Cancel a frozen reconnect timer and abort an old in-flight status fetch.
2. Fetch fresh no-store station state.
3. Reject an older response from the same generation/sequence.
4. Replace stale local metadata and timing with the server response.
5. If playback was requested and the stream is stale, attach a fresh URL to
   the same audio element and call `play()`.
6. If autoplay policy rejects the resumed play, retain the requested state and
   show a user-action recovery instead of touching the broadcast.

Reconnect uses bounded exponential backoff (1-30 seconds) with jitter.
Generation guards, intentional-pause suppression, timer cancellation, and a
single resume promise prevent duplicate attachment races and reconnect storms.
Visual video is paused while hidden and is independent of audio.

## Diagnostics

Open `https://allthings140radio.online/?diagnostics=1`. The local, read-only
panel shows frontend/server generation and sequence, last state sync,
reconnect count, media ready/network/error state, visibility, online state,
requested playback, stream URL, and the latest 100 timestamped connection
events. The same data is available in DevTools:

```js
AllThings140Diagnostics.snapshot()
```

Expected events include `page_hidden`, `page_frozen`, `page_resumed`,
`network_offline`, `network_online`, `station_state_refresh`,
`station_state_mismatch`, `resync_performed`, `stream_attach`, `audio_waiting`,
`audio_stalled`, `audio_error`, and `audio_playing`. No secrets are recorded.

## Verification performed 2026-08-13

- Chromium foreground playback reached media ready state 4.
- A lifecycle freeze spanning a track transition resumed on the new server
  sequence and current track.
- The first test found and led to removal of an intentional-pause reconnect
  race. The repeated v1.6.1 test made exactly one post-resume stream attach and
  returned to ready state 4/playing.
- Network emulation and a long suspended/throttled run recovered automatically
  to the then-current sequence without a server control request.
- Nineteen Python integration/unit tests passed, including explicit proof that
  repeated public status reads do not change broadcast sequence.

Android and iOS may still stop browser networking/audio for battery policy.
The site does not attempt to defeat those policies; it immediately resyncs on
wake. Media Session supplies metadata and play/pause/stop controls. A platform
may require one new tap if it revokes autoplay permission after process death.
