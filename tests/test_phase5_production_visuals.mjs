import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=rel=>fs.readFileSync(path.join(ROOT,rel),'utf8');
let passed=0;
const check=(condition,message)=>{assert.ok(condition,message);passed++;console.log(`✓ ${message}`)};
const worker=read('radio/_worker.js');
const live=read('radio/visuals/live.html');
const cfg=read('radio/visuals/config-live.js');
const roomEngine=read('radio/room/stage.js');
const greenEngine=read('visuals-green/stage.js');
const legacy=read('radio/visuals/index.html');

check(worker.includes('state.visuals === "new" ? "/visuals/live.html" : "/visuals/index.html"'),'edge routing selects immutable live or legacy Visuals documents');
check(worker.includes('X-AT140-Visuals-Mode'),'production responses expose the selected Visuals mode');
check(worker.includes('handlePublicVisualsRoutingGet'),'Visuals has a read-only adapter for its independent KV selector');
check(cfg.includes('environment:"live"') && cfg.includes('ws?environment=live'),'public Visuals registers explicitly as Live');
check(cfg.includes('/api/visuals-routing'),'public Visuals reads only the Visuals routing selector');
check(live.includes('../room/stage.js?v=2.5.0'),'public Visuals uses the shared reviewed renderer engine');
check(roomEngine===greenEngine,'Green and public renderers remain byte-identical');
check(legacy.includes('assets/visuals-desktop-v8/index.m3u8'),'legacy fallback preserves the Phase 2 desktop HLS');
check(legacy.includes('phone-visuals-authoritative-v1.mp4'),'legacy fallback preserves the separate mobile Visuals asset');
check(read('radio/sw.js')===read('radio/sw-v47.js'),'service worker entry files remain synchronized');
check(read('radio/sw.js').includes('allthings140-radio-v61'),'service worker cache namespace advances for the production cutover');
console.log(`${passed}/${passed} Phase 5 production Visuals checks passed`);
