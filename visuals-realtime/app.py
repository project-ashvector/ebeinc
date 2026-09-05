#!/usr/bin/env python3
"""Small, portable realtime room. It has no radio-control dependencies."""
from __future__ import annotations
import asyncio, json, logging, math, os, re, secrets, sqlite3, time
from collections import defaultdict, deque
from pathlib import Path
from aiohttp import WSMsgType, web

VERSION="0.3.0-workstation"; WS_MAX_PAYLOAD=16384; HTTP_MAX_PAYLOAD=262144; MAX_LAYOUT_BYTES=131072
LIVE_LEASE_MS=6000
NAME=re.compile(r"[^\w ._-]",re.UNICODE); TAGS=re.compile(r"<[^>]*>")
REACTIONS={"fire":8,"skull":7,"heart":6,"bolt":9,"bass":10}
ENVIRONMENTS=frozenset({"green-staging","live"})

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
  self.db.executescript("""PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=3000; CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,name TEXT,text TEXT,avatar TEXT,created_at INTEGER); CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC); CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY,title TEXT,artist TEXT,visual_url TEXT,start_at INTEGER,end_at INTEGER,enabled INTEGER); CREATE TABLE IF NOT EXISTS stats(key TEXT PRIMARY KEY,value INTEGER NOT NULL); INSERT OR IGNORE INTO stats VALUES('total_reactions',0);""")
  self._migrate_environment_state(); self.db.commit()
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
 def _migrate_environment_state(self):
  columns={row[1] for row in self.db.execute("PRAGMA table_info(schedules)")}
  if "environment" not in columns:
   self.db.execute("ALTER TABLE schedules ADD COLUMN environment TEXT NOT NULL DEFAULT 'live'")
  self.db.execute("CREATE INDEX IF NOT EXISTS idx_schedules_environment_time ON schedules(environment,enabled,start_at,end_at)")
  global_row=self.db.execute("SELECT value FROM stats WHERE key='active_layout'").fetchone()
  if global_row and global_row[0]:
   try:
    legacy=json.loads(global_row[0])
   except Exception:
    legacy=None
   # Historical workstation tests are explicitly previewMode=true and belong to
   # Green. A non-preview historical layout is treated as the pre-migration Live
   # authority. The original row is retained as forensic rollback evidence.
   if isinstance(legacy,dict):
    target="green-staging" if legacy.get("previewMode") is True else "live"
    self.db.execute("INSERT OR IGNORE INTO stats(key,value) VALUES(?,?)",(f"active_layout:{target}",global_row[0]))
  legacy_ack=self.db.execute("SELECT value FROM stats WHERE key='renderer_ack:live-chat'").fetchone()
  if legacy_ack and legacy_ack[0]:
   self.db.execute("INSERT OR IGNORE INTO stats(key,value) VALUES('renderer_ack:live',?)",(legacy_ack[0],))
  self.db.execute("INSERT OR IGNORE INTO stats(key,value) VALUES('environment_schema_version',2)")

 async def broadcast(self,payload,environment=None):
  self.sequence+=1; payload.setdefault("sequence",self.sequence)
  async def send_one(sid,state):
   try:
    await asyncio.wait_for(state["ws"].send_json(payload),timeout=2.0)
    return None
   except Exception:
    return sid
  targets=[(sid,state) for sid,state in list(self.clients.items()) if environment is None or state.get("environment")==environment]
  results=await asyncio.gather(*(send_one(sid,state) for sid,state in targets),return_exceptions=False)
  for sid in results:
   if sid:self.clients.pop(sid,None)

def live_snapshot(app):
 state=app['workstation_live']; now=int(time.time()*1000)
 active=bool(state.get('active') and now-state.get('lastHeartbeat',0)<=LIVE_LEASE_MS)
 return {"active":active,"source":"workstation" if active else "fallback","layoutHash":state.get('layoutHash','') if active else '',"startedAt":state.get('startedAt',0) if active else 0,"lastHeartbeat":state.get('lastHeartbeat',0),"ageMs":max(0,now-state.get('lastHeartbeat',0)) if state.get('lastHeartbeat') else None,"leaseMs":LIVE_LEASE_MS,"serverTime":now}

async def health(request):
 return web.json_response({"ok":True,"service":"allthings140-visuals-realtime","version":VERSION,"connections":len(request.app['room'].clients),"environment":os.getenv('ENVIRONMENT','staging'),"workstationLive":live_snapshot(request.app)},headers={"Cache-Control":"no-store"})

async def live_state(request):
 environment=request_environment(request)
 if environment!='live':return web.json_response({"error":"live_environment_required"},status=400)
 return web.json_response({"ok":True,"environment":"live",**live_snapshot(request.app)},headers={"Cache-Control":"no-store"})

async def workstation_live(request):
 try: body=await request.json()
 except Exception:return web.json_response({"error":"invalid_json"},status=400)
 environment=request_environment(request,body)
 if environment!='live':return web.json_response({"error":"live_environment_required"},status=400)
 status,err=check_admin(request,environment)
 if status!=200:return web.json_response({"error":err},status=status)
 action=clean(body.get('action'),24); now=int(time.time()*1000); state=request.app['workstation_live']
 if action in {'start','heartbeat'}:
  layout_hash=clean(body.get('layoutHash'),64)
  active_layout,_=read_layout(request.app['room'],'live'); active_hash=clean((active_layout or {}).get('layoutHash'),64)
  if not layout_hash or layout_hash!=active_hash:return web.json_response({"error":"layout_hash_not_active"},status=409)
  if action=='start' or not state.get('active') or state.get('layoutHash')!=layout_hash:
   state.update({"active":True,"layoutHash":layout_hash,"startedAt":now,"lastHeartbeat":now})
   await request.app['room'].broadcast({"type":"workstation_live","environment":"live",**live_snapshot(request.app)},'live')
  else:state['lastHeartbeat']=now
 elif action=='stop':
  state.update({"active":False,"layoutHash":"","startedAt":0,"lastHeartbeat":now})
  await request.app['room'].broadcast({"type":"workstation_live","environment":"live",**live_snapshot(request.app)},'live')
 else:return web.json_response({"error":"invalid_action"},status=400)
 return web.json_response({"ok":True,"environment":"live",**live_snapshot(request.app)},headers={"Cache-Control":"no-store"})

async def media_asset(request):
 name=clean(request.match_info.get('name'),160)
 if not re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:mp4|webm)",name):raise web.HTTPNotFound()
 root=request.app['media_root']; target=(root/name).resolve()
 if not (target.is_file() and target.is_relative_to(root)):
  cand = None
  for sub in ("stage", "visuals", "playlist"):
   t = (root / sub / name).resolve()
   if t.is_file() and t.is_relative_to(root):
    cand = t; break
  if cand: target = cand
  else: raise web.HTTPNotFound()
 response=web.FileResponse(target)
 response.headers.update({
  "Cache-Control":"public, max-age=31536000, immutable",
  "Accept-Ranges":"bytes",
  "X-Content-Type-Options":"nosniff",
  "Access-Control-Allow-Origin":"*",
  "Access-Control-Allow-Methods":"GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers":"Range, Content-Type",
  "Access-Control-Expose-Headers":"Accept-Ranges, Content-Length, Content-Range, Content-Type"
 })
 return response


def valid_environment(value):
 value=clean(value,32)
 return value if value in ENVIRONMENTS else None

def request_environment(request,body=None):
 candidates=[request.query.get("environment"),request.headers.get("X-AT140-Environment")]
 if isinstance(body,dict): candidates.append(body.get("environment"))
 values={clean(value,32) for value in candidates if value not in (None,"")}
 if len(values)!=1:return None
 return valid_environment(values.pop())

def check_admin(request,environment):
 key="GREEN_ADMIN_TOKEN" if environment=="green-staging" else "LIVE_ADMIN_TOKEN"
 expected=os.getenv(key,"").strip()
 if not expected: return 503, f"{environment} publishing disabled"
 token=request.headers.get("Authorization","").removeprefix("Bearer ").strip()
 if not token or not secrets.compare_digest(token,expected): return 401, "unauthorized"
 return 200, ""

def read_layout(room,environment):
 row=room.db.execute("SELECT value FROM stats WHERE key=?",(f"active_layout:{environment}",)).fetchone()
 if not row or not row[0]: return None,None
 try:
  value=json.loads(row[0])
  if not isinstance(value,dict):raise ValueError("layout is not an object")
  return value,None
 except Exception as exc:
  logging.error("Stored layout is invalid env=%s error=%s",environment,type(exc).__name__)
  return None,"stored_layout_invalid"

async def visual_state(request):
 environment=request_environment(request)
 if not environment:return web.json_response({"error":"valid_environment_required"},status=400)
 room=request.app['room']; now=int(time.time()*1000)
 row=room.db.execute("SELECT * FROM schedules WHERE environment=? AND enabled=1 AND start_at<=? AND end_at>? ORDER BY start_at DESC LIMIT 1",(environment,now,now)).fetchone()
 return web.json_response({"ok":True,"environment":environment,"server_time":now,"sequence":room.sequence,"takeover":dict(row) if row else None},headers={"Cache-Control":"no-store"})

async def layout_state(request):
 environment=request_environment(request)
 if not environment:return web.json_response({"error":"valid_environment_required"},status=400)
 layout,error=read_layout(request.app['room'],environment)
 return web.json_response({"ok":error is None,"environment":environment,"layout":layout,"layoutHash":(layout or {}).get("layoutHash","") ,"error":error},headers={"Cache-Control":"no-store"})

async def publish_layout(request):
 raw=await request.read()
 if len(raw)>MAX_LAYOUT_BYTES:
  return web.json_response({"error":"layout_too_large","bytes":len(raw),"limit":MAX_LAYOUT_BYTES},status=413)
 try: body=json.loads(raw)
 except Exception: return web.json_response({"error":"invalid_json"},status=400)
 environment=request_environment(request,body)
 if not environment:return web.json_response({"error":"valid_environment_required"},status=400)
 status, err = check_admin(request,environment)
 if status != 200: return web.json_response({"error":err}, status=status)
 if not isinstance(body,dict) or not body.get("layoutHash") or not isinstance(body.get("layers"),list):
  return web.json_response({"error":"invalid_layout_contract"},status=400)
 playlist=body.get("playlist",[])
 if not isinstance(playlist,list):return web.json_response({"error":"invalid_playlist_contract"},status=400)
 asset_ids=[]
 for item in playlist:
  if not isinstance(item,dict) or item.get("enabled") is False:continue
  asset_id=clean(item.get("id") or item.get("assetId"),128)
  if not asset_id or not str(item.get("url","")).startswith("https://"):
   return web.json_response({"error":"invalid_playlist_item"},status=400)
  asset_ids.append(asset_id)
 if len(asset_ids)!=len(set(asset_ids)):
  return web.json_response({"error":"duplicate_playlist_asset_id"},status=400)
 body["environment"]=environment
 room=request.app['room']; layout_json=json.dumps(body,separators=(",",":"))
 room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES(?, ?)",(f"active_layout:{environment}",layout_json)); room.db.commit()
 await room.broadcast({"type":"layout_update","environment":environment,"layout":body,"layoutHash":body.get("layoutHash","")},environment)
 return web.json_response({"ok":True,"environment":environment,"layoutId":body.get("layoutId","") ,"layoutHash":body.get("layoutHash",""),"bytes":len(raw)},status=200)

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
 env_name=request_environment(request,body)
 if not env_name:return web.json_response({"error":"valid_environment_required"},status=400)
 if state.get("environment") != env_name:
  return web.json_response({"error":"renderer_environment_mismatch"},status=409)
 existing_env=state.get("renderer_environment")
 if existing_env and existing_env != env_name:
  return web.json_response({"error":"renderer_environment_mismatch"},status=409)
 active_layout,_=read_layout(room,env_name); active_layout=active_layout or {}
 active_hash=clean(active_layout.get("layoutHash"),64)
 if active_hash and active_hash != layout_hash:
  return web.json_response({"error":"layout_hash_not_active"},status=409)
 now_ts=int(time.time()*1000)
 state["is_renderer"]=True
 state["renderer_environment"]=env_name
 state["visual_mode"]="new"
 renderer_role=clean(body.get("rendererRole"),32) or "unknown-renderer"
 if renderer_role not in {"green-room-renderer","visuals-page-renderer","unknown-renderer"}:renderer_role="unknown-renderer"
 state["renderer_role"]=renderer_role
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
  "rotationRound":int(body.get("rotationRound",0)),
  "rotationPosition":int(body.get("rotationPosition",0)),
  "libraryCount":int(body.get("libraryCount",0)),
  "visualMode":"new",
  "rendererRole":renderer_role,
  "renderStatus":clean(body.get("renderStatus","rendered"),32),
  "receivedAt":now_ts,
  "lastSeen":now_ts
 }
 state["renderer_ack"]=ack_data
 room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES(?, ?)",(f"renderer_ack:{env_name}",json.dumps(ack_data)))
 room.db.commit()
 await room.broadcast({"type":"renderer_ack_received","environment":env_name,"ack":ack_data},env_name)
 logging.info("RENDERER ACK RECEIVED (HTTP) env=%s sid=%s hash=%s status=%s", env_name, sid, ack_data["layoutHash"][:16], ack_data["renderStatus"])
 return web.json_response({"ok":True,"ack":ack_data},status=200)

async def renderer_state(request):
 room=request.app['room']; now_ts=int(time.time()*1000)
 req_env=request_environment(request)
 if not req_env:return web.json_response({"error":"valid_environment_required"},status=400)
 rows=room.db.execute("SELECT key, value FROM stats WHERE key LIKE 'renderer_ack%'").fetchall()
 acks_by_env={}
 for row in rows:
  k=row[0]
  try: val=json.loads(row[1]) if row[1] else None
  except Exception: val=None
  if k.startswith('renderer_ack:'):
   env_k=k.split(':',1)[1]
   acks_by_env[env_k]=val
 target_ack=acks_by_env.get(req_env)
 live_pairs=[(sid,c) for sid,c in room.clients.items() if c.get("is_renderer") and c.get("renderer_environment")==req_env]
 live_states=[c for _,c in live_pairs]
 live_socket=bool(live_pairs)
 new_clients=sum(1 for _,c in live_pairs if c.get("visual_mode")=="new")
 legacy_clients=sum(1 for _,c in live_pairs if c.get("visual_mode")=="legacy")
 live_visual_mode=("mixed" if new_clients and legacy_clients else "new" if new_clients else "legacy" if legacy_clients else "unknown")
 active_layout,_=read_layout(room,req_env); active_layout=active_layout or {}
 active_hash=clean(active_layout.get("layoutHash"),64)
 # Renderer truth is per live socket. A legacy/fallback client must never
 # overwrite a fresh workstation renderer ACK for the same environment.
 matching_acks=[c.get("renderer_ack") for _,c in live_pairs
                if c.get("visual_mode")=="new" and c.get("renderer_ack")
                and c.get("renderer_ack",{}).get("layoutHash")==active_hash]
 if matching_acks:
  target_ack=max(matching_acks,key=lambda a:a.get("lastSeen",a.get("receivedAt",0)))
 role_acks={}
 for _,client in live_pairs:
  candidate=client.get("renderer_ack") or {}
  role=client.get("renderer_role") or candidate.get("rendererRole") or "unknown-renderer"
  if client.get("visual_mode")!="new" or candidate.get("layoutHash")!=active_hash:continue
  existing=role_acks.get(role) or {}
  if candidate.get("lastSeen",candidate.get("receivedAt",0))>existing.get("lastSeen",existing.get("receivedAt",0)):
   role_acks[role]=candidate
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
  "environments":env_summaries,
  "renderersByRole":role_acks
 }
 return web.json_response(resp_data,headers={"Cache-Control":"no-store"})

async def schedule(request):
 try: body=await request.json()
 except Exception:return web.json_response({"error":"invalid_json"},status=400)
 environment=request_environment(request,body)
 if not environment:return web.json_response({"error":"valid_environment_required"},status=400)
 status, err = check_admin(request,environment)
 if status != 200: return web.json_response({"error":err}, status=status)
 start=int(body.get("start_at",0));end=int(body.get("end_at",0));url=clean(body.get("visual_url"),500)
 if end<=start or end-start>86400000 or not url.startswith("https://"):return web.json_response({"error":"invalid_schedule"},status=400)
 room=request.app['room']
 item=(secrets.token_urlsafe(10),clean(body.get("title"),80),clean(body.get("artist"),60),url,start,end,1,environment);room.db.execute("INSERT INTO schedules(id,title,artist,visual_url,start_at,end_at,enabled,environment) VALUES(?,?,?,?,?,?,?,?)",item);room.db.commit();await room.broadcast({"type":"takeover_schedule_changed","environment":environment},environment);return web.json_response({"ok":True,"environment":environment,"id":item[0]},status=201)

async def ws_handler(request):
 room=request.app['room']; origin=request.headers.get("Origin",""); allowed=request.app['origins']
 if origin not in allowed:return web.json_response({"error":"origin_not_allowed"},status=403)
 environment=request_environment(request)
 if not environment:return web.json_response({"error":"valid_environment_required"},status=400)
 ip=request.headers.get("CF-Connecting-IP") or request.remote or "unknown"
 if len(room.clients)>=int(os.getenv("MAX_CONNECTIONS","500")) or not room.allow((ip,"connect"),12,60):return web.json_response({"error":"rate_limited"},status=429)
 ws=web.WebSocketResponse(heartbeat=25,receive_timeout=70,max_msg_size=WS_MAX_PAYLOAD,autoping=True); await ws.prepare(request)
 sid=secrets.token_urlsafe(12); room.clients[sid]={"ws":ws,"name":f"Listener-{sid[:4].upper()}","avatar":"orb-purple","ip":ip,"last_reaction":0.,"seen":deque(maxlen=32),"is_audience":False,"is_renderer":False,"environment":environment,"renderer_environment":None,"renderer_role":None,"visual_mode":"unknown"}
 rows=room.db.execute("SELECT id,name,text,avatar,created_at FROM messages ORDER BY created_at DESC LIMIT ?",(int(os.getenv("CHAT_HISTORY_LIMIT","50")),)).fetchall()
 active_layout,_=read_layout(room,environment)
 snap=room.snapshot();snap.pop("type",None);await ws.send_json({"type":"welcome","session_id":sid,"environment":environment,"history":[dict(x) for x in reversed(rows)],"active_layout":active_layout,**snap}); await room.broadcast(room.snapshot())
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
    join_env=valid_environment(body.get("environment"))
    if join_env != environment:
     await ws.send_json({"type":"error","code":"environment_mismatch"}); continue
    state["name"]=NAME.sub("",clean(body.get("name"),24)) or state["name"]
    avatar=clean(body.get("avatar"),32); state["avatar"]=avatar if avatar in {"orb-purple","orb-cyan","orb-pink","orb-green","orb-fire"} else "orb-purple"
    # Operator/workstation/staging renderer sockets can observe the room without
    # inflating listener presence. Backward-compatible clients default to audience.
    state["is_audience"]=bool(body.get("audience",True))
    await room.broadcast(room.snapshot())
   elif kind=="renderer_ack":
    now_ts=int(time.time()*1000)
    env_name=valid_environment(body.get("environment"))
    if not env_name:
     await ws.send_json({"type":"error","code":"valid_environment_required"}); continue
    if env_name != environment:
     await ws.send_json({"type":"error","code":"renderer_environment_mismatch"}); continue
    existing_env=state.get("renderer_environment")
    if existing_env and existing_env != env_name:
     await ws.send_json({"type":"error","code":"renderer_environment_mismatch"}); continue
    ack_hash=clean(body.get("layoutHash"),64)
    active_layout,_=read_layout(room,env_name); active_layout=active_layout or {}
    active_hash=clean(active_layout.get("layoutHash"),64)
    if not ack_hash:
     await ws.send_json({"type":"error","code":"layout_hash_required"}); continue
    if active_hash and active_hash != ack_hash:
     await ws.send_json({"type":"error","code":"layout_hash_not_active"}); continue
    state["is_renderer"]=True
    state["renderer_environment"]=env_name
    state["visual_mode"]="new"
    renderer_role=clean(body.get("rendererRole"),32) or "unknown-renderer"
    if renderer_role not in {"green-room-renderer","visuals-page-renderer","unknown-renderer"}:renderer_role="unknown-renderer"
    state["renderer_role"]=renderer_role
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
     "rotationRound":int(body.get("rotationRound",0)),
     "rotationPosition":int(body.get("rotationPosition",0)),
     "libraryCount":int(body.get("libraryCount",0)),
     "visualMode":"new",
     "rendererRole":renderer_role,
     "renderStatus":clean(body.get("renderStatus","rendered"),32),
     "receivedAt":now_ts,
     "lastSeen":now_ts
    }
    state["renderer_ack"]=ack_data
    room.db.execute("INSERT OR REPLACE INTO stats(key, value) VALUES(?, ?)",(f"renderer_ack:{env_name}",json.dumps(ack_data)))
    room.db.commit()
    await room.broadcast({"type":"renderer_ack_received","environment":env_name,"ack":ack_data},env_name)
    logging.info("RENDERER ACK RECEIVED (WS) env=%s sid=%s hash=%s status=%s", env_name, sid, ack_data["layoutHash"][:16], ack_data["renderStatus"])
   elif kind=="renderer_heartbeat":
    state["is_renderer"]=True
    now_ts=int(time.time()*1000)
    env_name=valid_environment(body.get("environment"))
    if not env_name:
     await ws.send_json({"type":"error","code":"valid_environment_required"}); continue
    if env_name != environment:
     await ws.send_json({"type":"error","code":"renderer_environment_mismatch"}); continue
    existing_env=state.get("renderer_environment")
    if existing_env and existing_env != env_name:
     await ws.send_json({"type":"error","code":"renderer_environment_mismatch"}); continue
    state["renderer_environment"]=env_name
    visual_mode=clean(body.get("visualMode"),16) or "new"
    state["visual_mode"]=visual_mode
    heartbeat_role=clean(body.get("rendererRole"),32)
    if heartbeat_role in {"green-room-renderer","visuals-page-renderer","unknown-renderer"}:state["renderer_role"]=heartbeat_role
    h_hash=clean(body.get("layoutHash"),64)
    client_ack=state.get("renderer_ack") or {}
    if client_ack and visual_mode == "new" and (not h_hash or client_ack.get("layoutHash")==h_hash):
     client_ack["lastSeen"]=now_ts
     client_ack["videoReadyState"]=int(body.get("videoReadyState",client_ack.get("videoReadyState",0)))
     client_ack["visualMode"]="new"
     state["renderer_ack"]=client_ack
    for stat_key in (f"renderer_ack:{env_name}",):
     row=room.db.execute("SELECT value FROM stats WHERE key=?", (stat_key,)).fetchone()
     ack=json.loads(row[0]) if row and row[0] else {}
     if ack and ack.get("rendererSessionId")==sid and visual_mode == "new" and (not h_hash or ack.get("layoutHash")==h_hash):
      ack["lastSeen"]=now_ts
      ack["videoReadyState"]=int(body.get("videoReadyState",ack.get("videoReadyState",0)))
      ack["visualMode"]=visual_mode
      state["renderer_ack"]=ack
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
 origins={x.strip() for x in os.getenv("ALLOWED_ORIGINS","").split(",") if x.strip()}
 if not origins:raise RuntimeError("ALLOWED_ORIGINS must contain at least one explicit origin")
 green_token=os.getenv("GREEN_ADMIN_TOKEN","").strip(); live_token=os.getenv("LIVE_ADMIN_TOKEN","").strip()
 if not green_token:raise RuntimeError("GREEN_ADMIN_TOKEN is required")
 if not live_token:raise RuntimeError("LIVE_ADMIN_TOKEN is required")
 if secrets.compare_digest(green_token,live_token):raise RuntimeError("Green and Live admin credentials must be different")
 path=db_path or os.getenv("DATABASE_PATH","./realtime.db");Path(path).parent.mkdir(parents=True,exist_ok=True)
 media_root=Path(os.getenv("MEDIA_ROOT","/home/ebmarah/Videos/at140radio/desktop visuals/generated/web-v1")).expanduser().resolve()
 if not media_root.is_dir():raise RuntimeError(f"MEDIA_ROOT does not exist: {media_root}")
 app=web.Application(client_max_size=HTTP_MAX_PAYLOAD,middlewares=[cors]);app['room']=Room(path);app['origins']=origins;app['media_root']=media_root;app['workstation_live']={"active":False,"layoutHash":"","startedAt":0,"lastHeartbeat":0};app.add_routes([web.get('/health',health),web.get('/live-state',live_state),web.post('/admin/live',workstation_live),web.get('/media/visuals/{name}',media_asset),web.get('/media/stage/{name}',media_asset),web.get('/media/{name}',media_asset),web.get('/visuals/{name}',media_asset),web.get('/stage/{name}',media_asset),web.get('/visuals-state',visual_state),web.get('/layout-state',layout_state),web.post('/admin/schedule',schedule),web.post('/admin/layout',publish_layout),web.post('/renderer-ack',renderer_ack),web.get('/renderer-state',renderer_state),web.get('/ws',ws_handler)]);app.on_shutdown.append(shutdown_clients);app.on_cleanup.append(close_room_db);return app
if __name__=="__main__":logging.basicConfig(level=logging.INFO);web.run_app(create_app(),host=os.getenv("REALTIME_HOST","127.0.0.1"),port=int(os.getenv("REALTIME_PORT","14140")))
