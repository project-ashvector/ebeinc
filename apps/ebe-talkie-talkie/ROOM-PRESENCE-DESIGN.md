# Room Presence

v0.1.4 displays a live online count beside every saved room. Presence is inferred from the existing encrypted per-room signaling heartbeat, so monitoring a room does not open its microphone or WebRTC audio connection. A device remains counted while an encrypted signaling message from its device ID has been seen within roughly 22 seconds.
