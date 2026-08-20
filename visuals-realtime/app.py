#!/usr/bin/env python3
"""Small, portable realtime room. It has no radio-control dependencies."""
from __future__ import annotations
import asyncio, json, logging, math, os, re, secrets, sqlite3, time
from collections import defaultdict, deque
from pathlib import Path
from aiohttp import WSMsgType, web

VERSION="0.1.4-staging"; WS_MAX_PAYLOAD=16384; HTTP_MAX_PAYLOAD=262144; MAX_LAYOUT_BYTES=131072
NAME=re.compile(r"[^\w ._-]",re.UNICODE); TAGS=re.compile(r"<[^>]*>")
REACTIONS={"fire":8,"skull":7,"heart":6,"bolt":9,"bass":10}

@web.middleware
async def cors(request,handler):
 origin=request.headers.get("Origin","")
 if request.method == "OPTIONS":
  response=web.Response(status=204)
 else:
  response=await handler(request)
 if origin and origin in request.app['origins']:
  response.headers["Access-Control-Allow-Origin"]=origin
  response.headers["Vary"]="Origin"
  response.headers["Access-Control-Allow-Methods"]="GET, POST, OPTIONS"
  response.headers["Access-Control-Allow-Headers"]="Content-Type, Authorization"
  response.headers["Access-Control-Max-Age"]="600"
 return response

def clean(value,limit): return TAGS.sub("",str(value or "")).replace("\x00","").strip()[:limit]
class Room:
 def __init__(self,db_path):
  self.db=sqlite3.connect(db_path); self.db.row_factory=sqlite3.Row
  self.db.executescript("""PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=3000; CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,name TEXT,text TEXT,avatar TEXT,created_at INTEGER); CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC); CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY,title TEXT,artist TEXT,visual_url TEXT,start_at INTEGER,end_at INTEGER,enabled INTEGER); CREATE TABLE IF NOT EXISTS stats(key TEXT PRIMARY KEY,value INTEGER NOT NULL); INSERT OR IGNORE INTO stats VALUES('total_reactions',0);"""); self.db.commit()
  self.clients={}; self.ip_events=defaultdict(deque); self.energy=0.; self.energy_at=time.monotonic(); self.sequence=0
 def decay(self):
  now=time.monotonic(); self.energy=max(0.,self.energy-(now-self.energy_at)*1.4); self.energy_at=now; return round(min(100,self.energy),1)
 def allow(self,key,limit,window):
  q=self.ip_events[key]; now=time.monotonic()
  while q and now-q[0]>window:q.popleft()
  if len(q)>=limit:return False
  q.append(now)
  if len(self.ip_events)>500:
   stale=[k for k,v in self.ip_events.items() if not v or (now-v[-1]>120)]
   for k in stale:self.ip_events.pop(k,None)
  return True
 def snapshot(self):
  total=self.db.execute("SELECT value FROM stats WHERE key='total_reactions'").fetchone()[0]
  audience=[(sid,state) for sid,state in self.clients.items() if state.get("is_audience")]
  return {"type":"room_state","sequence":self.sequence,"presence":len(audience),"energy":self.decay(),"total_reactions":total,"profiles":[{"session_id":sid,"name":state['name'],"avatar":state['avatar']} for sid,state in audience]}
 async def broadcast(self,payload):
  self.sequence+=1; payload.setdefault("sequence",self.sequence)
  async def send_one(sid,state):
   try:
    await asyncio.wait_for(state["ws"].send_json(payload),timeout=2.0)
    return None
   except Exception:
    return sid
  results=await asyncio.gather(*(send_one(sid,state) for sid,state in list(self.clients.items())),return_exceptions=False)
  for sid in results:
   if sid:self.clients.pop(sid,None)

async def health(request): return web.json_response({"ok":True,"service":"allthings140-visuals-realtime","version":VERSION,"connections":len(request.app['room'].clients),"environment":os.getenv('ENVIRONMENT','staging')},headers={"Cache-Control":"no-store"})

def check_admin(request):
 expected=os.getenv("ADMIN_TOKEN","").strip()
 if not expected: return 503, "admin publishing disabled"
 token=request.headers.get("Authorization","").removeprefix("Bearer ").strip()
 if not token or not secrets.compare_digest(token,expected): return 401, "unauthorized"
 return 200, ""

async def visual_state(request):
 room=request.app['room']; now=int(time.time()*1000)
 row=room.db.execute("SELECT * FROM schedules WHERE enabled=1 AND start_at<=? AND end_at>? ORDER BY start_at DESC LIMIT 1",(now,now)).fetchone()
 return web.json_response({"ok":True,"server_time":now,"sequence":room.sequence,"takeover":dict(row) if row else None},headers={"Cache-Control":"no-store"})

async def layout_state(request):
 room=request.app['room']
 row=room.db.execute("SELECT value FROM stats WHERE key='active_layout'").fetchone()
 layout=json.loads(row[0]) if row and row[0] else None
 return web.json_response({"ok":True,"layout":layout,"layoutHash":(layout or {}).get("layoutHash","")},headers={"Cache-Control":"no-store"})

async def publish_layout(request):
 status, err = check_admin(request)
 if status != 200: return web.json_response({"error":err}, status=status)
 raw=await request.read()
 if len(raw)>MAX_LAYOUT_BYTES:
  return web.json_response({"error":"layout_too_large","bytes":len(raw),"limit":MAX_LAYOUT_BYTES},status=413)
 try: body=json.loads(raw)
 except Exception: return web.json_response({"error":"invalid_json"},status=400)
 if not isinstance(body,dict) or not body.get("layoutHash") or not isinstance(body.get("layers"),list):
  return web.json_response({"error":"invalid_layout_contract"},status=400)
 room=request.app['room']; layout_json=json.dumps(body,separators=(",",":"))
 room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES('active_layout', ?)",(layout_json,)); room.db.commit()
 await room.broadcast({"type":"layout_update","layout":body,"layoutHash":body.get("layoutHash","")})
 return web.json_response({"ok":True,"layoutId":body.get("layoutId","") ,"layoutHash":body.get("layoutHash",""),"bytes":len(raw)},status=200)

async def renderer_ack(request):
 try:
  body=await request.json()
 except Exception:
  return web.json_response({"error":"invalid_json"},status=400)
 room=request.app['room']
 layout_hash=clean(body.get("layoutHash"),64)
 if not layout_hash:
  return web.json_response({"error":"layout_hash_required"},status=400)
 sid=clean(body.get("rendererSessionId"),64)
 if not sid or sid not in room.clients:
  return web.json_response({"error":"renderer_session_not_active"},status=409)
 state=room.clients[sid]
 env_name=clean(body.get("environment"),32) or "green-staging"
 existing_env=state.get("renderer_environment")
 if existing_env and existing_env != env_name:
  return web.json_response({"error":"renderer_environment_mismatch"},status=409)
 row=room.db.execute("SELECT value FROM stats WHERE key='active_layout'").fetchone()
 try: active_layout=json.loads(row[0]) if row and row[0] else {}
 except Exception: active_layout={}
 active_hash=clean(active_layout.get("layoutHash"),64)
 if active_hash and active_hash != layout_hash:
  return web.json_response({"error":"layout_hash_not_active"},status=409)
 now_ts=int(time.time()*1000)
 state["is_renderer"]=True
 state["renderer_environment"]=env_name
 ack_data={
  "rendererSessionId":sid,
  "environment":env_name,
  "layoutId":clean(body.get("layoutId"),64),
  "layoutHash":layout_hash,
  "stageAssetId":clean(body.get("stageAssetId"),64),
  "visualAssetId":clean(body.get("visualAssetId"),64),
  "renderAppliedAt":int(body.get("renderAppliedAt",now_ts)),
  "videoReadyState":int(body.get("videoReadyState",0)),
  "stageReadyState":int(body.get("stageReadyState",0)),
  "visualMode":"new",
  "renderStatus":clean(body.get("renderStatus","rendered"),32),
  "receivedAt":now_ts,
  "lastSeen":now_ts
 }
 room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES('renderer_ack', ?)",(json.dumps(ack_data),))
 room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES(?, ?)",(f"renderer_ack:{env_name}",json.dumps(ack_data)))
 room.db.commit()
 await room.broadcast({"type":"renderer_ack_received","environment":env_name,"ack":ack_data})
 logging.info("RENDERER ACK RECEIVED (HTTP) env=%s sid=%s hash=%s status=%s", env_name, sid, ack_data["layoutHash"][:16], ack_data["renderStatus"])
 return web.json_response({"ok":True,"ack":ack_data},status=200)

async def renderer_state(request):
 room=request.app['room']; now_ts=int(time.time()*1000)
 req_env=request.query.get("environment","").strip()
 rows=room.db.execute("SELECT key, value FROM stats WHERE key LIKE 'renderer_ack%'").fetchall()
 acks_by_env={}; main_ack=None
 for row in rows:
  k=row[0]
  try: val=json.loads(row[1]) if row[1] else None
  except Exception: val=None
  if k=='renderer_ack': main_ack=val
  elif k.startswith('renderer_ack:'):
   env_k=k.split(':',1)[1]
   acks_by_env[env_k]=val
 target_ack=acks_by_env.get(req_env) if req_env else (main_ack or acks_by_env.get("green-staging") or acks_by_env.get("live-chat"))
 if req_env:
  live_pairs=[(sid,c) for sid,c in room.clients.items() if c.get("is_renderer") and c.get("renderer_environment")==req_env]
 else:
  live_pairs=[(sid,c) for sid,c in room.clients.items() if c.get("is_renderer")]
 live_states=[c for _,c in live_pairs]
 live_socket=bool(live_pairs)
 new_clients=sum(1 for _,c in live_pairs if c.get("visual_mode")=="new")
 legacy_clients=sum(1 for _,c in live_pairs if c.get("visual_mode")=="legacy")
 live_visual_mode=("mixed" if new_clients and legacy_clients else "new" if new_clients else "legacy" if legacy_clients else "unknown")
 row=room.db.execute("SELECT value FROM stats WHERE key='active_layout'").fetchone()
 try: active_layout=json.loads(row[0]) if row and row[0] else {}
 except Exception: active_layout={}
 active_hash=clean(active_layout.get("layoutHash"),64)
 ack_age=(now_ts - (target_ack or {}).get("lastSeen",(target_ack or {}).get("receivedAt",0))) if target_ack else 10**12
 ack_sid=(target_ack or {}).get("rendererSessionId","")
 ack_live_state=next((c for sid,c in live_pairs if sid==ack_sid),None)
 ack_session_live=ack_live_state is not None
 rendering_current=bool(ack_session_live and ack_live_state.get("visual_mode") == "new" and target_ack and ack_age < 15000 and (target_ack or {}).get("layoutHash") == active_hash and str((target_ack or {}).get("renderStatus","")).lower() == "rendered")
 env_names=set(acks_by_env)
 env_names.update(c.get("renderer_environment") for c in room.clients.values() if c.get("is_renderer") and c.get("renderer_environment"))
 env_summaries={}
 for env_n in sorted(env_names):
  env_a=acks_by_env.get(env_n) or {}
  env_pairs=[(sid,c) for sid,c in room.clients.items() if c.get("is_renderer") and c.get("renderer_environment")==env_n]
  env_new=sum(1 for _,c in env_pairs if c.get("visual_mode")=="new")
  env_legacy=sum(1 for _,c in env_pairs if c.get("visual_mode")=="legacy")
  seen_ts=env_a.get("lastSeen",env_a.get("receivedAt",0))
  age=now_ts-seen_ts if seen_ts else 10**12
  env_ack_sid=env_a.get("rendererSessionId","")
  env_ack_session_live=any(sid==env_ack_sid for sid,_ in env_pairs)
  env_summaries[env_n]={
   "connected":bool(env_pairs),
   "rendererClients":len(env_pairs),
   "renderingClients":env_new,
   "fallbackClients":env_legacy,
   "visualMode":"mixed" if env_new and env_legacy else "new" if env_new else "legacy" if env_legacy else "unknown",
   "ackSessionLive":env_ack_session_live,
   "status":"fresh" if env_ack_session_live and age<15000 else "stale" if env_ack_session_live and age<45000 else "offline",
   "layoutHash":env_a.get("layoutHash",""),
   "layoutId":env_a.get("layoutId",""),
   "rendererSessionId":env_ack_sid,
   "renderStatus":env_a.get("renderStatus","UNKNOWN"),
   "lastSeen":seen_ts,
   "ageMs":age,
   "ack":env_a
  }
 resp_data={
  "ok":True,
  "rendererConnected":live_socket,
  "rendererClients":len(live_pairs),
  "renderingClients":new_clients,
  "fallbackClients":legacy_clients,
  "ackSessionLive":ack_session_live,
  "layoutHash":(target_ack or {}).get("layoutHash",""),
  "layoutId":(target_ack or {}).get("layoutId",""),
  "rendererSessionId":(target_ack or {}).get("rendererSessionId",""),
  "environment":(target_ack or {}).get("environment",req_env or "default"),
  "stageAssetId":(target_ack or {}).get("stageAssetId",""),
  "visualAssetId":(target_ack or {}).get("visualAssetId",""),
  "renderStatus":(target_ack or {}).get("renderStatus","UNKNOWN"),
  "visualMode":live_visual_mode,
  "renderingCurrentLayout":rendering_current,
  "activeLayoutHash":active_hash,
  "videoReadyState":(target_ack or {}).get("videoReadyState",0),
  "stageReadyState":(target_ack or {}).get("stageReadyState",0),
  "renderAppliedAt":(target_ack or {}).get("renderAppliedAt",0),
  "lastSeen":(target_ack or {}).get("lastSeen",(target_ack or {}).get("receivedAt",0)),
  "ack":target_ack,
  "environments":env_summaries
 }
 return web.json_response(resp_data,headers={"Cache-Control":"no-store"})

async def schedule(request):
 status, err = check_admin(request)
 if status != 200: return web.json_response({"error":err}, status=status)
 body=await request.json();start=int(body.get("start_at",0));end=int(body.get("end_at",0));url=clean(body.get("visual_url"),500)
 if end<=start or end-start>86400000 or not url.startswith("https://"):return web.json_response({"error":"invalid_schedule"},status=400)
 room=request.app['room']
 item=(secrets.token_urlsafe(10),clean(body.get("title"),80),clean(body.get("artist"),60),url,start,end,1);room.db.execute("INSERT INTO schedules VALUES(?,?,?,?,?,?,?)",item);room.db.commit();await room.broadcast({"type":"takeover_schedule_changed"});return web.json_response({"ok":True,"id":item[0]},status=201)

async def ws_handler(request):
 room=request.app['room']; origin=request.headers.get("Origin",""); allowed=request.app['origins']
 if allowed and origin not in allowed:return web.json_response({"error":"origin_not_allowed"},status=403)
 ip=request.headers.get("CF-Connecting-IP") or request.remote or "unknown"
 if len(room.clients)>=int(os.getenv("MAX_CONNECTIONS","500")) or not room.allow((ip,"connect"),12,60):return web.json_response({"error":"rate_limited"},status=429)
 ws=web.WebSocketResponse(heartbeat=25,receive_timeout=70,max_msg_size=WS_MAX_PAYLOAD,autoping=True); await ws.prepare(request)
 sid=secrets.token_urlsafe(12); room.clients[sid]={"ws":ws,"name":f"Listener-{sid[:4].upper()}","avatar":"orb-purple","ip":ip,"last_reaction":0.,"seen":deque(maxlen=32),"is_audience":False,"is_renderer":False,"renderer_environment":None,"visual_mode":"unknown"}
 rows=room.db.execute("SELECT id,name,text,avatar,created_at FROM messages ORDER BY created_at DESC LIMIT ?",(int(os.getenv("CHAT_HISTORY_LIMIT","50")),)).fetchall()
 row=room.db.execute("SELECT value FROM stats WHERE key='active_layout'").fetchone()
 active_layout=json.loads(row[0]) if row and row[0] else None
 snap=room.snapshot();snap.pop("type",None);await ws.send_json({"type":"welcome","session_id":sid,"history":[dict(x) for x in reversed(rows)],"active_layout":active_layout,**snap}); await room.broadcast(room.snapshot())
 try:
  async for msg in ws:
   if msg.type!=WSMsgType.TEXT: continue
   if len(msg.data)>WS_MAX_PAYLOAD: await ws.close(code=1009,message=b"payload too large"); break
   try: body=json.loads(msg.data)
   except Exception: await ws.send_json({"type":"error","code":"invalid_json"}); continue
   kind=body.get("type"); state=room.clients.get(sid)
   if not state:break
   eid=clean(body.get("event_id"),64)
   if eid and eid in state["seen"]:continue
   if eid:state["seen"].append(eid)
   if kind=="join":
    state["name"]=NAME.sub("",clean(body.get("name"),24)) or state["name"]
    avatar=clean(body.get("avatar"),32); state["avatar"]=avatar if avatar in {"orb-purple","orb-cyan","orb-pink","orb-green","orb-fire"} else "orb-purple"
    # Operator/workstation/staging renderer sockets can observe the room without
    # inflating listener presence. Backward-compatible clients default to audience.
    state["is_audience"]=bool(body.get("audience",True))
    await room.broadcast(room.snapshot())
   elif kind=="renderer_ack":
    now_ts=int(time.time()*1000)
    env_name=clean(body.get("environment"),32) or "green-staging"
    existing_env=state.get("renderer_environment")
    if existing_env and existing_env != env_name:
     await ws.send_json({"type":"error","code":"renderer_environment_mismatch"}); continue
    ack_hash=clean(body.get("layoutHash"),64)
    row=room.db.execute("SELECT value FROM stats WHERE key='active_layout'").fetchone()
    try: active_layout=json.loads(row[0]) if row and row[0] else {}
    except Exception: active_layout={}
    active_hash=clean(active_layout.get("layoutHash"),64)
    if not ack_hash:
     await ws.send_json({"type":"error","code":"layout_hash_required"}); continue
    if active_hash and active_hash != ack_hash:
     await ws.send_json({"type":"error","code":"layout_hash_not_active"}); continue
    state["is_renderer"]=True
    state["renderer_environment"]=env_name
    ack_data={
     "rendererSessionId":sid,
     "environment":env_name,
     "layoutId":clean(body.get("layoutId"),64),
     "layoutHash":ack_hash,
     "stageAssetId":clean(body.get("stageAssetId"),64),
     "visualAssetId":clean(body.get("visualAssetId"),64),
     "renderAppliedAt":int(body.get("renderAppliedAt",now_ts)),
     "videoReadyState":int(body.get("videoReadyState",0)),
     "stageReadyState":int(body.get("stageReadyState",0)),
     "visualMode":"new",
     "renderStatus":clean(body.get("renderStatus","rendered"),32),
     "receivedAt":now_ts,
     "lastSeen":now_ts
    }
    room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES('renderer_ack', ?)",(json.dumps(ack_data),))
    room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES(?, ?)",(f"renderer_ack:{env_name}",json.dumps(ack_data)))
    room.db.commit()
    await room.broadcast({"type":"renderer_ack_received","environment":env_name,"ack":ack_data})
    logging.info("RENDERER ACK RECEIVED (WS) env=%s sid=%s hash=%s status=%s", env_name, sid, ack_data["layoutHash"][:16], ack_data["renderStatus"])
   elif kind=="renderer_heartbeat":
    state["is_renderer"]=True
    now_ts=int(time.time()*1000)
    env_name=clean(body.get("environment"),32) or "green-staging"
    existing_env=state.get("renderer_environment")
    if existing_env and existing_env != env_name:
     await ws.send_json({"type":"error","code":"renderer_environment_mismatch"}); continue
    state["renderer_environment"]=env_name
    visual_mode=clean(body.get("visualMode"),16) or "new"
    state["visual_mode"]=visual_mode
    h_hash=clean(body.get("layoutHash"),64)
    for stat_key in ('renderer_ack', f"renderer_ack:{env_name}"):
     row=room.db.execute("SELECT value FROM stats WHERE key=?", (stat_key,)).fetchone()
     ack=json.loads(row[0]) if row and row[0] else {}
     if ack and ack.get("rendererSessionId")==sid and visual_mode == "new" and (not h_hash or ack.get("layoutHash")==h_hash):
      ack["lastSeen"]=now_ts
      ack["videoReadyState"]=int(body.get("videoReadyState",ack.get("videoReadyState",0)))
      ack["visualMode"]=visual_mode
      room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES(?, ?)",(stat_key,json.dumps(ack)))
    room.db.commit()
    await ws.send_json({"type":"renderer_heartbeat_ack","environment":env_name,"server_time":now_ts})
   elif kind=="message":
    if not room.allow((sid,"message"),4,10) or not room.allow((ip,"message"),12,30):await ws.send_json({"type":"error","code":"slow_down"});continue
    text=clean(body.get("text"),240)
    if not text:continue
    item={"id":secrets.token_urlsafe(10),"name":state["name"],"text":text,"avatar":state["avatar"],"created_at":int(time.time()*1000),"session_id":sid}
    room.db.execute("INSERT INTO messages VALUES(?,?,?,?,?)",(item["id"],item["name"],item["text"],item["avatar"],item["created_at"]));room.db.execute("DELETE FROM messages WHERE id NOT IN (SELECT id FROM messages ORDER BY created_at DESC LIMIT 100)");room.db.commit();await room.broadcast({"type":"message","message":item,"speech_ttl_ms":6500})
   elif kind=="reaction":
    if not state.get("is_audience"):
     await ws.send_json({"type":"error","code":"observer_cannot_react"}); continue
    now=time.monotonic(); reaction=clean(body.get("reaction"),12)
    if reaction not in REACTIONS or now-state["last_reaction"]<0.65 or not room.allow((sid,"reaction"),8,10) or not room.allow((ip,"reaction"),24,10):await ws.send_json({"type":"error","code":"reaction_rate_limited"});continue
    state["last_reaction"]=now;room.decay();room.energy=min(100.,room.energy+REACTIONS[reaction]);room.db.execute("UPDATE stats SET value=value+1 WHERE key='total_reactions'");room.db.commit();await room.broadcast({"type":"reaction","reaction":reaction,"name":state["name"],"energy":room.decay(),"total_reactions":room.db.execute("SELECT value FROM stats WHERE key='total_reactions'").fetchone()[0]})
   elif kind=="ping":await ws.send_json({"type":"pong","server_time":int(time.time()*1000),"sequence":room.sequence})
   else:await ws.send_json({"type":"error","code":"unknown_event"})
 finally:
  room.ip_events.pop((sid,"message"),None)
  room.ip_events.pop((sid,"reaction"),None)
  room.clients.pop(sid,None);await room.broadcast(room.snapshot())
 return ws

async def shutdown_clients(app):
 clients=list(app['room'].clients.values())
 if clients:await asyncio.gather(*(state['ws'].close(code=1001,message=b'service restart') for state in clients),return_exceptions=True)
 app['room'].clients.clear()

async def close_room_db(app):
 try: app['room'].db.close()
 except Exception: pass

def create_app(db_path=None):
 path=db_path or os.getenv("DATABASE_PATH","./realtime.db");Path(path).parent.mkdir(parents=True,exist_ok=True)
 app=web.Application(client_max_size=HTTP_MAX_PAYLOAD,middlewares=[cors]);app['room']=Room(path);app['origins']={x.strip() for x in os.getenv("ALLOWED_ORIGINS","").split(",") if x.strip()};app.add_routes([web.get('/health',health),web.get('/visuals-state',visual_state),web.get('/layout-state',layout_state),web.post('/admin/schedule',schedule),web.post('/admin/layout',publish_layout),web.post('/renderer-ack',renderer_ack),web.get('/renderer-state',renderer_state),web.get('/ws',ws_handler)]);app.on_shutdown.append(shutdown_clients);app.on_cleanup.append(close_room_db);return app
if __name__=="__main__":logging.basicConfig(level=logging.INFO);web.run_app(create_app(),host=os.getenv("REALTIME_HOST","127.0.0.1"),port=int(os.getenv("REALTIME_PORT","14140")))
