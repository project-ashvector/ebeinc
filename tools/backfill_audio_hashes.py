#!/usr/bin/env python3
"""One-time resumable SHA-256 backfill for existing catalog audio."""
import hashlib, sqlite3, time
from pathlib import Path
from audio_ingest import ensure_schema

db=sqlite3.connect("/var/lib/allthings140radio/station.db");db.row_factory=sqlite3.Row;ensure_schema(db)
added=dupes=missing=0
for row in db.execute("SELECT id,filename FROM tracks").fetchall():
    if db.execute("SELECT 1 FROM audio_assets WHERE track_id=?",(row["id"],)).fetchone():continue
    path=Path("/srv/allthings140radio/data/music")/row["filename"]
    if not path.is_file():path=Path("/mnt/allthings140radio-drive")/row["filename"]
    if not path.is_file():missing+=1;continue
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):digest.update(chunk)
    value=digest.hexdigest();existing=db.execute("SELECT track_id FROM audio_assets WHERE sha256=?",(value,)).fetchone()
    if existing:
        dupes+=1;db.execute("INSERT INTO ingest_events(source_path,sha256,state,detail,created_at) VALUES(?,?,?,?,?)",(str(path),value,"duplicate",f"existing track {existing[0]}",int(time.time())))
    else:
        db.execute("INSERT INTO audio_assets(track_id,sha256,source_path,size_bytes,codec,sample_rate,channels,duration,metadata_confidence,ingested_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(row["id"],value,str(path),path.stat().st_size,"existing",0,0,0,"existing",int(time.time())));added+=1
    db.commit()
total=db.execute("SELECT count(*) FROM audio_assets").fetchone()[0]
print(f"hashes_added={added} duplicates={dupes} missing={missing} assets_total={total}")
