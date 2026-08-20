#!/usr/bin/env python3
"""Preview and apply high-confidence track metadata repairs."""
from __future__ import annotations
import argparse, json, os, sqlite3
from pathlib import Path
from audio_ingest import parse_filename

def proposals(db_path: Path) -> list[dict]:
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id,title,artist,filename FROM tracks WHERE trim(artist)='' OR lower(trim(artist))='unknown'").fetchall()
    result=[]
    for row in rows:
        artist,title,confidence=parse_filename(row["filename"])
        result.append({"id":row["id"],"before":{"artist":row["artist"],"title":row["title"]},"after":{"artist":artist,"title":title},"confidence":confidence})
    return result

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--db",type=Path,default=Path(os.environ.get("ALLTHINGS140_DB_PATH","/var/lib/allthings140radio/station.db"))); p.add_argument("--apply-high-confidence",action="store_true"); p.add_argument("--output",type=Path); a=p.parse_args()
    items=proposals(a.db); applied=0
    if a.apply_high_confidence:
        with sqlite3.connect(a.db) as db:
            for item in items:
                if item["confidence"]=="high" and item["after"]["artist"]:
                    db.execute("UPDATE tracks SET artist=?,title=? WHERE id=?",(item["after"]["artist"],item["after"]["title"],item["id"])); applied+=1
            db.commit()
    report={"unknown":len(items),"high_confidence":sum(x["confidence"]=="high" for x in items),"applied":applied,"proposals":items}
    text=json.dumps(report,indent=2,ensure_ascii=False); print(text if not a.output else json.dumps({k:v for k,v in report.items() if k!="proposals"},indent=2))
    if a.output: a.output.write_text(text,encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
