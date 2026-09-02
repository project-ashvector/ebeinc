# EBE Talkie Talkie v0.1.0

Android family push-to-talk prototype.

## First-test behavior

- Internet PTT over WebRTC audio.
- Encrypted signaling over MQTT/WebSocket.
- Shared family room code built into every copy of the APK; the room can also be changed in the UI.
- Mesh audio supports Cody, Mom, and Girlfriend simultaneously in the same room.
- Large hold-to-talk control; releasing immediately mutes the local microphone.
- Deterministic soft floor control prevents most simultaneous transmissions.
- Speaker routing and echo/noise processing are enabled for a walkie-talkie style experience.

## Privacy model

The signaling broker is public test infrastructure, but signaling payloads are encrypted with AES-256-GCM using a PBKDF2-derived room key. WebRTC media uses DTLS-SRTP. The first build includes public STUN/TURN infrastructure to maximize NAT/cellular connectivity; migrate these endpoints to EBE-operated infrastructure before treating the app as production-grade private communications.

## Test

Install the same APK on all three Android phones, open it, enter a different display name on each phone, keep the same family room code, and tap Connect. Hold the large button to speak and release it to listen.
