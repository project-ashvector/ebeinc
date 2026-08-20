# Local voice library

Create one folder per user-supplied or authorized voice. No celebrity audio is
downloaded by this project.

Example `voices/bass_bro/voice.json`:

```json
{
  "id": "bass_bro",
  "displayName": "Bass Bro",
  "provider": "piper",
  "modelPath": "voices/bass_bro/model.onnx",
  "speed": 1.0,
  "defaultPersona": "bass_music_bro",
  "enabled": true
}
```

F5-TTS and OpenVoice profiles may additionally set `referenceAudioPath` and
`referenceTranscript`. The engine must be installed separately by the owner.
