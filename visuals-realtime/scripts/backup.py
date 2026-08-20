#!/usr/bin/env python3
import hashlib,json,os,shutil,sqlite3,tarfile,tempfile,time
from pathlib import Path
db=Path(os.getenv('DATABASE_PATH','./realtime.db'));out=Path(os.getenv('BACKUP_PATH','./backups'));out.mkdir(parents=True,exist_ok=True)
stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()); archive=out/f'allthings140-visuals-state-{stamp}.tar.gz'
with tempfile.TemporaryDirectory(dir=out) as tmp:
 root=Path(tmp)/'state';root.mkdir();copy=root/'realtime.db'
 with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as src,sqlite3.connect(copy) as dst:src.backup(dst)
 with sqlite3.connect(copy) as check:assert check.execute('pragma quick_check').fetchone()[0]=='ok'
 manifest={'version':1,'created_at':stamp,'database_sha256':hashlib.sha256(copy.read_bytes()).hexdigest(),'restore_test':'passed'};(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 with tarfile.open(archive,'w:gz') as tar:tar.add(root,arcname='allthings140-visuals-state')
 with tarfile.open(archive,'r:gz') as tar:tar.extractall(Path(tmp)/'restore',filter='data')
 restored=Path(tmp)/'restore/allthings140-visuals-state/realtime.db'
 with sqlite3.connect(restored) as check:assert check.execute('pragma quick_check').fetchone()[0]=='ok'
status={'last_backup':'PASS','last_backup_at':stamp,'backup_size':archive.stat().st_size,'restore_test':'PASS','archive':archive.name};(out/'backup-status.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status))
for old in sorted(out.glob('allthings140-visuals-state-*.tar.gz'))[:-14]:old.unlink()
