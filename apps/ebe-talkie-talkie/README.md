# EBE Talkie Talkie v0.2.1 — Always-On Rooms

Private Android push-to-talk for family/friends.

## v0.2.1 persistent listening

v0.2.1 fixes the biggest background reliability problem in earlier builds: the old foreground service could remain alive while the real WebRTC/MQTT receiver had already died with the Activity/WebView.

The app now uses two coordinated radio engines:

- **Foreground/UI:** the proven WebView WebRTC push-to-talk implementation owns the microphone while the app is open.
- **Background:** a native Android, receive-only WebRTC engine runs inside the foreground media service after the UI leaves the screen.

If a user joins a room and does not explicitly press **LEAVE**, the active room ID, room name, permanent radio code, user/device identity, and armed state are persisted. The foreground service takes the room when the app is backgrounded or swiped away, keeps social presence alive, and reconnects signaling after network interruptions. Reopening the app hands the room back to the full PTT UI.

### Reliability protections

- Foreground mediaPlayback service with START_STICKY.
- Sticky process recreation treats the Activity as gone and recovers the saved armed room.
- onTaskRemoved recovery for task swipes.
- Native receive-only WebRTC in the service; no background microphone capture.
- MQTT keepalive and exponential reconnect.
- Network callback reconnect.
- PTT heartbeat/stale-talker recovery.
- Social room presence heartbeat while backgrounded.
- No permanent partial wake lock.
- Optional Android battery-optimization exemption exposed as **MAXIMIZE SAMSUNG RELIABILITY**.
- Boot receiver preserves room state and posts a one-tap resume reminder after a phone restart.

## Platform limits

Android **Force stop** is intentionally authoritative: after the user force-stops the app in system settings, Android blocks the app from restarting until the user launches it again.

On current Android versions a mediaPlayback foreground service cannot be freely started from BOOT_COMPLETED, so after a full phone reboot EBE Talkie Talkie posts a resume reminder instead of attempting a prohibited boot-time media service start.

The family build still uses public Mosquitto signaling and public STUN/TURN test infrastructure. The client reconnects automatically, but production-grade uptime ultimately requires EBE-controlled signaling and TURN servers.

## Social system

The claimed social backend is:

https://ebe-talkie-talkie-social.peat-leather.workers.dev

It provides username/password accounts, friends, profile pictures, synced friend-visible/private rooms, PIN locks, room membership, and live presence.

## Signing

Package: online.ebeinc.talkietalkie

Family builds continue using the existing family-test certificate so v0.2.1 installs as an update over v0.2.0. Before public/Play distribution, migrate to private production signing and EBE-controlled communications infrastructure.
