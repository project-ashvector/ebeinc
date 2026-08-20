import fs from 'node:fs';

let passed = 0, failed = 0;
function assert(ok, msg) { if (ok) { console.log(`✓ ${msg}`); passed++; } else { console.error(`✗ ${msg}`); failed++; } }

const main = fs.readFileSync('visuals-app/src/main.js','utf8');
const rust = fs.readFileSync('visuals-app/src-tauri/src/lib.rs','utf8');
const rt = fs.readFileSync('visuals-realtime/app.py','utf8');
const green = fs.readFileSync('visuals-green/stage.js','utf8');

assert(main.includes("appVersion = '0.1.37'"), 'workstation reports v0.1.37');
assert(main.includes('CANONICAL_LAYER_COLLISION'), 'canonical resolver rejects duplicate built-in IDs/roles');
assert(main.includes('layerId: stageLayer.id') && main.includes('layerId: visualLayer.id'), 'layer identity is distinct from media asset identity');
assert(!main.includes('Mark as Stage Base'), 'custom media cannot be promoted into reserved stage/visual roles');
assert(rust.includes('playlist": if is_preview { json!([]) }'), 'preview publish omits full workstation playlist');
assert(rust.includes('MAX_LAYOUT_BYTES: usize = 128 * 1024'), 'workstation guards realtime payload size');
assert(rust.includes('runtime_media_extension'), 'staged media keeps correct runtime extension');
assert(rust.includes('payloadBytes'), 'publisher reports actual payload size');
assert(rt.includes('HTTP_MAX_PAYLOAD=262144'), 'realtime HTTP body limit is separate from websocket message limit');
assert(rt.includes('MAX_LAYOUT_BYTES=131072'), 'realtime rejects unexpectedly bloated layouts');
assert(green.includes('waitForDecodedFrame'), 'Green waits for decoded frame before switching visual buffers');
assert(green.includes('consecutiveFailures = 0'), 'successful buffer swap resets failure counter');

if (failed) process.exit(1);
console.log(`\n${passed}/${passed+failed} contract checks passed`);
