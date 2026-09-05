#!/usr/bin/env python3
"""Stateful component health supervisor with bounded corrective actions."""
from __future__ import annotations
import json, os, re, subprocess, time, urllib.request
from pathlib import Path

STATE_PATH=Path("/var/lib/allthings140radio/supervisor-state.json")
COMPONENTS=("server","icecast","drive","tunnel")

def active(unit:str)->bool: return subprocess.run(["systemctl","is-active","--quiet",unit]).returncode==0
def api_ok()->bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:14080/api/health",timeout=6) as r:
            d=json.load(r)
            autodj=d.get("autodj",{})
            icecast=d.get("icecast",{})
            # An active Icecast daemon is not proof that listeners have audio.
            # Require the encoder's listener-facing mount to be attached as well,
            # otherwise the supervisor must recover the broadcast engine after
            # the existing consecutive-failure threshold.
            return bool(
                d.get("ok")
                and autodj.get("running")
                and icecast.get("online")
                and icecast.get("live_source")
            )
    except Exception:return False

def listener_audio_ok()->bool:
    """Confirm listener-facing audio has real signal, not merely an open mount."""
    try:
        probe=subprocess.run(
            ["ffmpeg","-hide_banner","-nostdin","-loglevel","info","-t","4",
             "-i","http://127.0.0.1:14000/live.mp3","-af","volumedetect",
             "-f","null","-"],
            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=10,check=False,
        )
        match=re.search(r"max_volume:\s*(-?(?:\d+(?:\.\d+)?|inf))\s*dB",probe.stderr,re.I)
        return bool(probe.returncode==0 and match and match.group(1).lower()!="-inf" and float(match.group(1))>-55.0)
    except Exception:return False

def main()->int:
    now=int(time.time())
    try: state=json.loads(STATE_PATH.read_text())
    except Exception: state={"schema":1,"components":{},"last_success":0,"last_action":"","overall":"starting"}
    server_active=active("allthings140radio-server.service")
    server_api_ok=server_active and api_ok()
    # A control-plane timeout must not interrupt healthy listener audio.  When
    # the API is unavailable, only restart after the existing failure threshold
    # if the listener-facing stream also lacks a real decoded audio signal.
    checks={"server":server_api_ok or (server_active and listener_audio_ok()),"icecast":active("allthings140radio-icecast.service"),"drive":active("allthings140radio-drive.service"),"tunnel":active("allthings140radio-tunnel.service")}
    degraded=[]
    for name,ok in checks.items():
        item=state["components"].setdefault(name,{"consecutive_failures":0,"last_success":0,"last_failure":0,"last_restart":0})
        if ok:item["consecutive_failures"]=0;item["last_success"]=now
        else:
            degraded.append(name);item["consecutive_failures"]+=1;item["last_failure"]=now
            cooldown=min(3600,60*(2**min(item["consecutive_failures"]-3,5)))
            if item["consecutive_failures"]>=3 and now-item.get("last_restart",0)>=cooldown:
                unit=f"allthings140radio-{name}.service"
                subprocess.run(["systemctl","restart",unit],check=False)
                item["last_restart"]=now;state["last_action"]=f"restart {name} after {item['consecutive_failures']} failures"
    state["checked_at"]=now;state["degraded_components"]=degraded
    state["overall"]="healthy" if not degraded else "warning" if max(state["components"][x]["consecutive_failures"] for x in degraded)<3 else "degraded"
    if not degraded:state["last_success"]=now
    tmp=STATE_PATH.with_suffix(".tmp");tmp.write_text(json.dumps(state,indent=2)+"\n");os.replace(tmp,STATE_PATH)
    print(json.dumps(state))
    return 0 if not degraded else 1
if __name__=="__main__": raise SystemExit(main())
