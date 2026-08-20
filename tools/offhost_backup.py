#!/usr/bin/env python3
"""Create, verify, encrypt, upload, retain, and restore-test station state."""
from __future__ import annotations
import hashlib, json, os, shutil, sqlite3, subprocess, tarfile, tempfile, time
from pathlib import Path

STATE = Path("/var/lib/allthings140radio")
CONFIG = Path("/etc/allthings140radio")
REMOTE = os.environ.get("ALLTHINGS140_BACKUP_REMOTE", "at140drive:BACKUPS/ENCRYPTED")
KEY = Path(os.environ.get("ALLTHINGS140_BACKUP_KEY", "/etc/allthings140radio/offhost-backup.key"))

def run(*args: str) -> None:
    subprocess.run(args, check=True)

def main() -> int:
    stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
    with tempfile.TemporaryDirectory(prefix="at140-backup-") as raw:
        root=Path(raw); payload=root/"payload"; payload.mkdir()
        db_out=payload/"station.db"
        with sqlite3.connect(f"file:{STATE/'station.db'}?mode=ro",uri=True) as src, sqlite3.connect(db_out) as dst: src.backup(dst)
        with sqlite3.connect(db_out) as db:
            assert db.execute("pragma quick_check").fetchone()[0]=="ok"
        for source,name in ((STATE/"rotation-state.json","rotation-state.json"),(STATE/"ads.json","ads.json"),(CONFIG/"config.json","config.json")):
            if source.exists(): shutil.copy2(source,payload/name)
        manifest={"schema":1,"created_at":stamp,"files":{}}
        for item in payload.iterdir(): manifest["files"][item.name]={"size":item.stat().st_size,"sha256":hashlib.sha256(item.read_bytes()).hexdigest()}
        (payload/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        archive=root/f"allthings140-state-{stamp}.tar.gz"
        with tarfile.open(archive,"w:gz") as tar: tar.add(payload,arcname="allthings140-state")
        encrypted=Path("/srv/allthings140radio/backups")/(archive.name+".enc")
        run("openssl","enc","-aes-256-cbc","-pbkdf2","-salt","-pass",f"file:{KEY}","-in",str(archive),"-out",str(encrypted))
        restore=root/"restore.tar.gz"
        run("openssl","enc","-d","-aes-256-cbc","-pbkdf2","-pass",f"file:{KEY}","-in",str(encrypted),"-out",str(restore))
        with tarfile.open(restore,"r:gz") as tar: tar.extractall(root/"restore",filter="data")
        restored=root/"restore/allthings140-state/station.db"
        with sqlite3.connect(restored) as db: assert db.execute("pragma quick_check").fetchone()[0]=="ok"
        run("rclone","copyto",str(encrypted),f"{REMOTE}/{encrypted.name}","--config=/etc/allthings140radio/rclone.conf","--checksum","--retries=3")
        run("rclone","delete",REMOTE,"--config=/etc/allthings140radio/rclone.conf","--min-age=35d","--include=*.enc")
        status={"schema":1,"state":"healthy","last_success":int(time.time()),"archive":encrypted.name,"size":encrypted.stat().st_size,"restore_test":"passed","remote":REMOTE}
        (STATE/"offhost-backup-status.json").write_text(json.dumps(status,indent=2)+"\n")
        print(json.dumps(status))
    return 0
if __name__=="__main__": raise SystemExit(main())
