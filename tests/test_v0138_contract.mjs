import fs from 'node:fs';

let passed = 0, failed = 0;
function assert(ok, msg) { if (ok) { console.log(`✓ ${msg}`); passed++; } else { console.error(`✗ ${msg}`); failed++; } }

const main = fs.readFileSync('visuals-app/src/main.js','utf8');
const rust = fs.readFileSync('visuals-app/src-tauri/src/lib.rs','utf8');
const rt = fs.readFileSync('visuals-realtime/app.py','utf8');
const green = fs.readFileSync('visuals-green/stage.js','utf8');
const pkg = JSON.parse(fs.readFileSync('visuals-app/package.json','utf8'));
const tauri = JSON.parse(fs.readFileSync('visuals-app/src-tauri/tauri.conf.json','utf8'));

assert((['0.1.43','0.1.42','0.1.41','0.1.40','0.1.39','0.1.38'].includes(pkg.version)) && tauri.version === pkg.version && main.includes(`appVersion = '${pkg.version}'`), `workstation version is synchronized at v${pkg.version}`);
const pkgLock = JSON.parse(fs.readFileSync('visuals-app/package-lock.json','utf8'));
const cargoLock = fs.readFileSync('visuals-app/src-tauri/Cargo.lock','utf8');
assert(pkgLock.version === pkg.version && pkgLock.packages[''].version === pkg.version && cargoLock.includes(`name = "allthings140radio-visuals"\nversion = "${pkg.version}"`), 'npm/Cargo lock metadata matches workstation release version');
assert(main.includes('CANONICAL_LAYER_COLLISION'), 'canonical resolver rejects duplicate built-in IDs/roles');
assert(main.includes('layerId: stageLayer.id') && main.includes('layerId: visualLayer.id'), 'layer identity is distinct from media asset identity');
assert(!main.includes('Mark as Stage Base'), 'custom media cannot be promoted into reserved stage/visual roles');

// v0.1.38 workstation smoothness / publishing guardrails
assert(main.includes('function compactPlaylistEntry') && !main.includes('const snapshot = structuredClone(state);'), 'publish snapshot is deliberately compact instead of cloning all workstation state');
assert(main.includes("playlist: mode === 'single' ? [] : orderedCyclePlaylist()"), 'single-media diagnostics stay compact while Green cycle tests retain the complete ordered playlist');
assert(main.includes("invoke('publish_layout_fast'") && main.includes('Publish Layout to Green'), 'normal workstation layout publish uses fast realtime path');
assert(!main.includes("invoke('publish_staging', { state: livePublishSnapshot(preview) })"), 'normal layout publish no longer redeploys Cloudflare Pages');
assert(main.includes('clearVideoSource(fullVideo)') && main.includes('slices.forEach(clearVideoSource)'), 'workstation releases hidden/unused Stage decoder sources');
assert(main.includes('Gateway stored layout') && main.includes('but Green renderer did not ACK it'), 'gateway storage is no longer treated as renderer success');
assert(main.includes('payloadBytes') && main.includes('realtimeHttpStatus'), 'Green test visibly reports realtime payload bytes and HTTP status');

// Publisher contract
assert(rust.includes('let playlist_contract = if is_preview { json!([]) }'), 'explicit single-media realtime diagnostics omit the full workstation playlist');
assert(rust.includes('MAX_LAYOUT_BYTES: usize = 128 * 1024'), 'workstation guards realtime payload size');
assert(rust.includes('runtime_media_extension'), 'staged media keeps correct runtime extension');
assert(rust.includes('payloadBytes'), 'publisher reports actual payload size');
assert(rust.includes('safePlaybackMode'), 'safe playback mode is carried into canonical Green layout');

assert(rust.includes('headers-{file_tag}.txt') && rust.includes('format!("@{}", header_path.display())') && !rust.includes('&format!("Authorization: Bearer {}", admin_token)'), 'realtime admin credential is not exposed in curl process arguments');

// Green runtime smoothness
assert(green.includes('visualTransitionInFlight') && green.includes('queuedCustomVisual'), 'Green serializes overlapping visual buffer swaps');
assert(green.includes('event?.currentTarget !== videos[activeIndex]'), 'inactive video ended events cannot advance the playlist');
assert(!green.includes('function preload(offset = 1)'), 'incorrect eager preload path was removed');
assert(green.includes('fetchWithTimeout') && green.includes('stationPollInFlight') && green.includes('takeoverPollInFlight'), 'Green network polling is bounded and non-overlapping');
assert(green.includes('waitForDecodedFrame'), 'Green waits for decoded frame before switching visual buffers');
assert(green.includes('lastRendererAckKey'), 'duplicate renderer acknowledgements are suppressed');
assert(green.includes("layout?.safePlaybackMode === true"), 'Green safe playback mode disables reactive visual effects');


assert(main.includes('function numberOr(value, fallback)') && main.includes('numberOr(so.x, 23.0)'), 'workstation cutout geometry preserves valid zero coordinates');
assert(main.includes("await invoke('cancel_staging_publish', { jobId })") && main.includes("activity('Green test failed'"), 'failed Green tests cancel any native publish job');
assert(rust.includes('run_cmd_with_timeout(ffmpeg, 180, None)'), 'background runtime transcoding has a hard native timeout');
assert(green.includes('function resetAudioReactiveFx()') && green.includes("setProperty('--visual-pulse', '1')"), 'Safe Playback Mode actively clears any previously applied reactive transforms');
assert(green.includes('lastAppliedLayoutHash') && green.includes('incomingHash === lastAppliedLayoutHash'), 'duplicate layout delivery is deduplicated instead of reloading media');
assert(green.includes('numberOr(screenOpening.x, 23)'), 'Green aperture geometry preserves valid zero coordinates');


assert(green.includes('Emergency fallback is not a normal rotation item') && !green.includes('playlist = [...playlist.filter(x => x?.url), fallback]'), 'emergency fallback is excluded from healthy 24/7 rotation');
assert(green.includes('sentOverWebSocket') && green.includes('if (!sentOverWebSocket)'), 'renderer ACK uses HTTP only as a WebSocket fallback instead of double-posting every ACK');
assert(main.includes('wsRetryCount') && main.includes('Math.min(30000') && main.includes("window.addEventListener('online'"), 'workstation realtime reconnect uses bounded exponential backoff and immediate online recovery');

// Realtime scalability / reliability
assert(rt.includes('HTTP_MAX_PAYLOAD=262144') && rt.includes('MAX_LAYOUT_BYTES=131072'), 'realtime HTTP layout limits remain explicit and separate from websocket limit');
assert(rt.includes('request.method == "OPTIONS"') && rt.includes('Access-Control-Allow-Headers'), 'realtime service answers CORS preflight for Green renderer acknowledgement');
assert(rt.includes('PRAGMA synchronous=NORMAL') && rt.includes('PRAGMA busy_timeout=3000'), 'realtime SQLite is tuned for small reliable live writes');
assert(rt.includes('asyncio.wait_for(state["ws"].send_json(payload),timeout=2.0)') && rt.includes('asyncio.gather'), 'slow websocket clients cannot serialize/block the entire broadcast fanout');

if (failed) process.exit(1);
console.log(`\n${passed}/${passed+failed} v0.1.38 contract checks passed`);
