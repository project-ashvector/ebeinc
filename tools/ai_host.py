#!/usr/bin/env python3
"""Fail-open local AI radio host primitives.

This module deliberately does not own the audio loop. Callers may request an
announcement; failures return ``None`` and music playback continues normally.
Voices and personalities are discovered from directories, so adding a voice
does not require editing Python source.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ANNOUNCEMENT_TYPES = ("STATION_ID", "SHARE_THE_STATION", "WEBSITE_PROMO", "LISTENER_ROAST", "FAKE_INFOMERCIAL", "ARTIST_TAKEOVER_PROMO", "ARTIST_TAKEOVER_TODAY", "ARTIST_TAKEOVER_STARTING", "ARTIST_TAKEOVER_ACTIVE", "ARTIST_TAKEOVER_ENDING", "ARTIST_SHOUTOUT", "TRACK_SUBMISSION_PROMO", "SPECIAL_EVENT", "RANDOM_HOST_BIT")
HUMOR_LEVELS = ("CLEAN", "NORMAL", "EDGY", "UNHINGED")
VOICE_MODES = ("SINGLE_HOST", "RANDOM_HOST", "WEIGHTED_HOST", "EVENT_SPECIFIC_HOST")
DEFAULT_WEIGHTS = {"STATION_ID": 20, "SHARE_THE_STATION": 15, "WEBSITE_PROMO": 10, "LISTENER_ROAST": 20, "FAKE_INFOMERCIAL": 10, "RANDOM_HOST_BIT": 25}

@dataclass
class VoiceProfile:
    id: str
    displayName: str
    provider: str
    modelPath: str = ""
    referenceAudioPath: str = ""
    referenceTranscript: str = ""
    speed: float = 1.0
    pitch: float = 0.0
    defaultPersona: str = ""
    enabled: bool = True

@dataclass
class Persona:
    id: str
    displayName: str
    systemPrompt: str
    humorLevel: str = "UNHINGED"
    voiceId: str = ""
    enabled: bool = True

@dataclass
class Takeover:
    id: str
    artistName: str
    displayName: str
    startDateTime: int
    endDateTime: int
    timezone: str = "America/Los_Angeles"
    announcementStartDate: int = 0
    status: str = "SCHEDULED"
    pronunciationHint: str = ""
    description: str = ""
    websiteUrl: str = ""
    socialUrl: str = ""
    artwork: str = ""
    customAnnouncementNotes: str = ""
    enabled: bool = True
    createdAt: int = 0
    updatedAt: int = 0

    def calculated_status(self, now: int | None = None) -> str:
        now = int(time.time()) if now is None else int(now)
        if not self.enabled or self.status == "CANCELLED": return "CANCELLED" if self.status == "CANCELLED" else "SCHEDULED"
        if now >= self.endDateTime: return "COMPLETED"
        if now >= self.startDateTime: return "LIVE"
        if now >= self.startDateTime - 7200: return "STARTING_SOON"
        if now >= self.startDateTime - 86400: return "TODAY"
        if self.announcementStartDate and now >= self.announcementStartDate: return "PROMOTING"
        return "SCHEDULED"

@dataclass
class AIConfig:
    enabled: bool = False
    parodyDisclosure: bool = True
    humorLevel: str = "UNHINGED"
    voiceMode: str = "SINGLE_HOST"
    preferredVoiceId: str = ""
    ollamaUrl: str = "http://127.0.0.1:11434"
    ollamaModel: str = "llama3.2:3b"
    stationUrl: str = "https://allthings140radio.online"
    minimumBreakSeconds: int = 240
    minimumTakeoverBreaks: int = 2
    minimumWebsiteBreaks: int = 3
    weights: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

@dataclass
class ReadyAnnouncement:
    announcementType: str
    text: str
    contextSignature: str
    createdAt: int
    audioPath: str = ""

class AIReadyQueue:
    """Small queue that invalidates event-bound announcements when facts change."""
    def __init__(self, maximum: int = 3): self.maximum, self.items = max(1, min(3, maximum)), []
    def add(self, item: ReadyAnnouncement) -> None:
        self.items.append(item); self.items = self.items[-self.maximum:]
    def invalidate(self, signature: str) -> None:
        self.items = [item for item in self.items if item.contextSignature == signature]
    def pop(self, signature: str) -> ReadyAnnouncement | None:
        while self.items:
            item = self.items.pop(0)
            if item.contextSignature == signature: return item
        return None
    def __len__(self): return len(self.items)

class AnnouncementScheduler:
    """Song-count gate for 4–7-song AI breaks; it never controls playback."""
    def __init__(self, minimum_songs: int = 4, maximum_songs: int = 7):
        self.minimum_songs, self.maximum_songs = max(1, minimum_songs), max(minimum_songs, maximum_songs)
        self.songs_since_break = 0
    def track_finished(self) -> bool:
        self.songs_since_break += 1
        return self.songs_since_break >= random.randint(self.minimum_songs, self.maximum_songs)
    def break_completed(self) -> None: self.songs_since_break = 0
    def reset(self) -> None: self.songs_since_break = 0

class TTSProvider:
    name = "base"
    def available(self) -> bool: return False
    def synthesize(self, text: str, voice: VoiceProfile, output: Path) -> bool: return False

class CommandTTSProvider(TTSProvider):
    executable = ""
    def command(self) -> str | None:
        override = os.environ.get("ALLTHINGS140_" + self.name.upper() + "_BIN")
        if override and Path(override).exists(): return override
        return shutil.which(self.executable)
    def available(self) -> bool: return bool(self.command())

class PiperProvider(CommandTTSProvider):
    name, executable = "piper", "piper"
    def synthesize(self, text, voice, output):
        command = self.command()
        if not command or not voice.modelPath: return False
        output.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([command, "--model", voice.modelPath, "--output_file", str(output)], input=text.encode(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)
        return result.returncode == 0 and output.exists() and output.stat().st_size > 0

class KokoroProvider(CommandTTSProvider):
    name, executable = "kokoro", "kokoro"

class F5TTSProvider(CommandTTSProvider):
    name, executable = "f5tts", "f5-tts_infer-cli"

class OpenVoiceProvider(CommandTTSProvider):
    name, executable = "openvoice", "openvoice"

class CustomVoiceProvider(CommandTTSProvider):
    name, executable = "custom", "custom-tts"

PROVIDERS = {p.name: p for p in (PiperProvider(), KokoroProvider(), F5TTSProvider(), OpenVoiceProvider(), CustomVoiceProvider())}

class VoiceLibrary:
    def __init__(self, root: Path): self.root = root
    def discover(self) -> list[VoiceProfile]:
        voices = []
        if not self.root.is_dir(): return voices
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir(): continue
            path = folder / "voice.json"
            try: data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"id": folder.name, "displayName": folder.name, "provider": "piper", "modelPath": str(folder / "model.onnx")}
            except (OSError, ValueError): continue
            try: voices.append(VoiceProfile(id=str(data.get("id", folder.name)), displayName=str(data.get("displayName", folder.name)), provider=str(data.get("provider", "piper")).lower(), modelPath=str(data.get("modelPath", "")), referenceAudioPath=str(data.get("referenceAudioPath", "")), referenceTranscript=str(data.get("referenceTranscript", "")), speed=float(data.get("speed", 1.0)), pitch=float(data.get("pitch", 0.0)), defaultPersona=str(data.get("defaultPersona", "")), enabled=bool(data.get("enabled", True))))
            except (TypeError, ValueError): continue
        return voices

class PersonaLibrary:
    def __init__(self, root: Path): self.root = root
    def discover(self) -> list[Persona]:
        result = []
        for path in (sorted(self.root.glob("*.json")) if self.root.is_dir() else []):
            try:
                data = json.loads(path.read_text(encoding="utf-8")); result.append(Persona(id=str(data["id"]), displayName=str(data.get("displayName", data["id"])), systemPrompt=str(data["systemPrompt"]), humorLevel=str(data.get("humorLevel", "UNHINGED")).upper(), voiceId=str(data.get("voiceId", "")), enabled=bool(data.get("enabled", True))))
            except (OSError, ValueError, KeyError, TypeError): continue
        return result

def takeover_context(takeovers: list[Takeover], now: int | None = None) -> dict[str, Any] | None:
    now = int(time.time()) if now is None else int(now)
    valid = [(t, t.calculated_status(now)) for t in takeovers if t.enabled and t.status != "CANCELLED" and t.endDateTime > now]
    if not valid: return None
    takeover, status = min(valid, key=lambda pair: pair[0].startDateTime)
    return {"id": takeover.id, "artist": takeover.displayName or takeover.artistName, "absoluteDate": time.strftime("%B %-d, %Y", time.localtime(takeover.startDateTime)), "relativeDescription": relative_description(takeover.startDateTime, now), "startTimestamp": takeover.startDateTime, "endTimestamp": takeover.endDateTime, "timezone": takeover.timezone, "status": status, "pronunciationHint": takeover.pronunciationHint, "notes": takeover.customAnnouncementNotes}

def relative_description(start: int, now: int) -> str:
    delta = start - now
    if delta <= 7200: return "in under two hours"
    if delta < 172800: return "tomorrow" if delta < 86400 else "in two days"
    return time.strftime("this %A", time.localtime(start))

class AIHost:
    def __init__(self, config: AIConfig, voice_root: Path, persona_root: Path, output_root: Path):
        self.config, self.voices, self.personas, self.output_root = config, VoiceLibrary(voice_root), PersonaLibrary(persona_root), output_root
        self.history: list[dict[str, Any]] = []
        self.last_by_type: dict[str, int] = {}
        self.ready = AIReadyQueue(3)
    def status(self) -> dict[str, Any]:
        voices = self.voices.discover(); return {"enabled": self.config.enabled, "humorLevel": self.config.humorLevel, "providers": {name: provider.available() for name, provider in PROVIDERS.items()}, "voices": [asdict(v) for v in voices], "personas": [asdict(p) for p in self.personas.discover()], "ready": bool(self.config.enabled and voices)}
    def select_type(self, context: dict[str, Any], now: int | None = None) -> str:
        now = int(time.time()) if now is None else int(now); takeover = context.get("upcomingTakeover") or {}
        status = str(takeover.get("status", ""))
        if status == "LIVE": return "ARTIST_TAKEOVER_ACTIVE"
        if status == "STARTING_SOON": return "ARTIST_TAKEOVER_STARTING"
        if status == "TODAY": return "ARTIST_TAKEOVER_TODAY"
        choices = [(kind, weight) for kind, weight in self.config.weights.items() if int(weight) > 0 and now - self.last_by_type.get(kind, 0) >= self.config.minimumBreakSeconds]
        if not choices: return "STATION_ID"
        return random.SystemRandom().choices([x[0] for x in choices], weights=[x[1] for x in choices], k=1)[0]
    def build_prompt(self, announcement_type: str, context: dict[str, Any], persona: Persona | None = None) -> str:
        verified = json.dumps({k: context.get(k) for k in ("previousTrack", "nextTrack", "songsSinceLastAnnouncement", "currentTime", "stationUrl", "upcomingTakeover", "activeTakeover") if context.get(k) is not None}, ensure_ascii=False)
        system = persona.systemPrompt if persona else "You are a funny, vulgar, unpredictable late-night bass-music radio host."
        disclosure = "Identify yourself as an AI-generated parody personality when appropriate." if self.config.parodyDisclosure else ""
        return f"{system}\n{disclosure}\nAnnouncement type: {announcement_type}\nVerified context (facts may not be changed): {verified}\nHumor level: {self.config.humorLevel}. Profanity is allowed, but no slurs, threats, graphic sexual content, hate, fake emergencies, or defamatory claims. Return only short spoken words, no stage directions or quotation marks. Invent jokes, never facts."
    def generate(self, announcement_type: str, context: dict[str, Any], persona: Persona | None = None) -> str | None:
        if not self.config.enabled: return None
        try:
            payload = json.dumps({"model": self.config.ollamaModel, "stream": False, "options": {"temperature": 0.9, "num_predict": 80}, "messages": [{"role": "system", "content": self.build_prompt(announcement_type, context, persona)}, {"role": "user", "content": "Write one fresh radio break in 1-3 short sentences."}]}).encode()
            request = urllib.request.Request(self.config.ollamaUrl.rstrip("/") + "/api/chat", data=payload, headers={"Content-Type": "application/json"}, method="POST")
            # Generation runs off the audio thread; allow slower local CPUs
            # time to finish while all playback paths remain fail-open.
            with urllib.request.urlopen(request, timeout=45) as response: data = json.loads(response.read())
            text = str(data.get("message", {}).get("content", "")).strip().replace('"', "")
            if not text or len(text) > 600 or not safe_comedy(text): return None
            self.history.append({"type": announcement_type, "text": text, "at": int(time.time())}); self.history = self.history[-200:]; self.last_by_type[announcement_type] = int(time.time()); return text
        except (OSError, ValueError, TypeError, urllib.error.URLError): return None
    def prune_cache(self, max_files: int = 50, max_age_seconds: int = 7 * 86400) -> int:
        if not self.output_root.is_dir(): return 0
        now = time.time(); pruned = 0
        try:
            files = sorted((f for f in self.output_root.glob("*.wav") if f.is_file() and f.name != "service-test.wav"), key=lambda f: f.stat().st_mtime)
            while len(files) > max_files or (files and (now - files[0].stat().st_mtime) > max_age_seconds):
                oldest = files.pop(0)
                try: oldest.unlink(missing_ok=True); pruned += 1
                except OSError: pass
        except Exception: pass
        return pruned

    def synthesize(self, text: str, voice_id: str = "") -> Path | None:
        if not text or not self.config.enabled: return None
        try:
            profiles = self.voices.discover(); preferred = voice_id or self.config.preferredVoiceId
            ordered = ([v for v in profiles if v.enabled and v.id == preferred] if preferred else []) + [v for v in profiles if v.enabled and v.id != preferred]
            for voice in ordered:
                provider = PROVIDERS.get(voice.provider); output = self.output_root / (hashlib.sha256(f"{voice.id}:{text}".encode()).hexdigest()[:24] + ".wav")
                if provider and provider.available() and provider.synthesize(text, voice, output):
                    self.prune_cache()
                    return output
        except (OSError, ValueError, subprocess.SubprocessError): pass
        return None

    @staticmethod
    def context_signature(context: dict[str, Any]) -> str:
        facts = {key: context.get(key) for key in ("upcomingTakeover", "activeTakeover", "previousTrack", "nextTrack")}
        return hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()

    def queue_announcement(self, announcement_type: str, context: dict[str, Any], persona: Persona | None = None) -> ReadyAnnouncement | None:
        signature = self.context_signature(context)
        text = self.generate(announcement_type, context, persona)
        if not text: return None
        item = ReadyAnnouncement(announcement_type, text, signature, int(time.time()))
        self.ready.add(item)
        return item

    def next_ready(self, context: dict[str, Any]) -> ReadyAnnouncement | None:
        return self.ready.pop(self.context_signature(context))

def safe_comedy(text: str) -> bool:
    lowered = text.lower()
    blocked = ("kill yourself", "bomb threat", "rape", "nigger", "faggot", "heil hitler")
    return not any(term in lowered for term in blocked)
