# EBE Talkie Talkie v0.1.1

Android family push-to-talk app for Cody, Mom, and Girlfriend.

## v0.1.1 upgrades

- Keeps the proven v0.1.0 WebRTC + encrypted signaling transport.
- Version code 2 so the APK updates the existing v0.1.0 debug install in place.
- Foreground listening service and ongoing notification for better background reliability.
- Partial wake lock while connected so Android is less likely to suspend the family channel.
- Saved name and family room, plus automatic reconnect on later launches after a successful connection.
- Explicit disconnect control to stop background listening and auto-connect.
- Share Room Code button using Android's share sheet.
- Clearer current-speaker UI with an animated transmission meter.
- Start/stop radio beeps and vibration feedback.
- Network online/offline recovery messaging and automatic broker reconnect.
- Proper EBE Talkie Talkie launcher/notification icon.

## Privacy / transport

Signaling uses encrypted AES-256-GCM payloads derived from the shared room code over MQTT/WebSocket. WebRTC media uses DTLS-SRTP. The current family build still relies on public Mosquitto signaling plus public STUN/TURN infrastructure; this is suitable for family testing but should be moved to EBE-controlled infrastructure before production-scale use.

## Test

Install v0.1.1 over v0.1.0 on all participating Android phones. Keep the same family room code, connect, confirm two-way PTT, then put one listener phone on the home screen with the screen locked and verify incoming speech still plays. Reopen the app and verify it returns to the saved room automatically.
