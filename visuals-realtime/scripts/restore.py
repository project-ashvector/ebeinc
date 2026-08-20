#!/usr/bin/env python3
import argparse,hashlib,json,sqlite3,tarfile,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
with tempfile.TemporaryDirectory() as tmp:
 with tarfile.open(a.archive,'r:gz') as tar:tar.extractall(tmp,filter='data')
 root=Path(tmp)/'allthings140-visuals-state';manifest=json.loads((root/'manifest.json').read_text());db=root/'realtime.db'
 assert hashlib.sha256(db.read_bytes()).hexdigest()==manifest['database_sha256']
 with sqlite3.connect(db) as check:assert check.execute('pragma quick_check').fetchone()[0]=='ok'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(db.read_bytes());print(f'restored and verified: {a.output}')
