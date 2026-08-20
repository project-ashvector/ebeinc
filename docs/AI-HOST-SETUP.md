# AI host architecture and setup

The AI host is fail-open and disabled by default. It never owns AutoDJ, Icecast,
live DJ handoff, or the station watchdog. A failed model, provider, voice,
network request, or ffmpeg process returns no announcement and music continues.

## Architecture

- `tools/ai_host.py` contains the provider interface, voice discovery,
  personality discovery, verified takeover context, weighted announcement type
  selection, prompt construction, history/cooldowns, and local synthesis.
- `config/ai-dj.example.json` is the starting configuration. Copy it to the
  server config directory and set `enabled` only after testing.
- `voices/<id>/voice.json` makes a voice installable without source edits.
- `personas/*.json` keeps personality from voice. A persona can use any voice.
- Takeover data must be supplied as structured records; the prompt includes
  only verified artist/date/time/status fields.
- The bounded ready queue holds at most three announcements and discards
  event-bound audio when takeover facts change. `AnnouncementScheduler` gates
  breaks to a configurable 4–7 finished-song window.

## Ollama

Install Ollama from https://ollama.com/download for the host operating system,
start it, then run:

```bash
ollama pull llama3.2:3b
ollama run llama3.2:3b
```

Set `ollamaUrl` and `ollamaModel` in the AI configuration. No cloud key is
required for the local path.

## Free local voices

Piper is the simplest first provider. Install the Piper executable/model using
the official package or release for the operating system, place the model in a
voice folder, and create its `voice.json`. The provider detector checks for the
`piper` executable. Kokoro, F5-TTS, OpenVoice, and custom providers are detected
when their owner-installed executables are present.

F5-TTS/OpenVoice reference audio must be supplied by the user and authorized
for use. This project does not scrape or download celebrity recordings.

## Test flow

```bash
python3 -m py_compile tools/ai_host.py
python3 - <<'PY'
from pathlib import Path
from tools.ai_host import AIConfig, AIHost
h = AIHost(AIConfig(enabled=False), Path('voices'), Path('personas'), Path('/tmp/at140-ai'))
print(h.status())
PY
```

The DJ app Settings panel exposes AI status, a test-announcement action, and
an immediate disable button. The authenticated server controls are
`GET /api/ai/status`, `POST /api/ai/test`, and `POST /api/ai/disable`.

To test the song gate without waiting for real songs:

```bash
python3 - <<'PY'
from tools.ai_host import AnnouncementScheduler
s = AnnouncementScheduler(4, 7)
for number in range(1, 8):
    print(number, s.track_finished())
PY
```

Enable the global switch only after the local model and voice are confirmed.
Set `enabled` to `false` to disable the entire AI layer instantly without
changing music playback.
