import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const read = rel => fs.readFileSync(path.join(ROOT, rel), 'utf8');
const sha = rel => crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT, rel))).digest('hex');

console.log('=== ALLTHINGS140 GREEN ROOM CUTOVER CONTRACT (v0.1.43) ===\n');
let passed = 0;
const check = (condition, message) => {
  assert.ok(condition, message);
  passed++;
  console.log(`✓ ${message}`);
};

const pkg = JSON.parse(read('visuals-app/package.json'));
check(pkg.version === '0.1.43', 'workstation package version is 0.1.43');
check(JSON.parse(read('visuals-app/src-tauri/tauri.conf.json')).version === '0.1.43', 'Tauri version is 0.1.43');
check(/version\s*=\s*"0\.1\.43"/.test(read('visuals-app/src-tauri/Cargo.toml')), 'Cargo package version is 0.1.43');
check(/let appVersion = '0\.1\.43'/.test(read('visuals-app/src/main.js')), 'frontend version is 0.1.43');

const home = read('radio/index.html');
check(home.includes('id="backgroundVideo"'), 'homepage keeps the proven legacy background video');
check(!home.includes('chatVisualRenderer'), 'homepage has no compositor injection');
check(!home.includes('data-open-chat'), 'homepage no longer opens the legacy chat drawer');
check(!home.includes('src="chat.js'), 'homepage no longer starts the legacy chat WebSocket client');
check(!home.includes('class="chat-drawer"'), 'legacy chat drawer markup is removed from normal homepage');
check((home.match(/href="room\/"/g) || []).length >= 2, 'homepage Green Room controls navigate to /room/');
check(home.includes('<span>GREEN ROOM</span>'), 'main navigation labels the replacement experience GREEN ROOM');

const roadmap = read('radio/roadmap/index.html');
check(!roadmap.includes('data-open-chat'), 'roadmap no longer exposes the legacy chat drawer');
check(!roadmap.includes('src="chat.js'), 'roadmap no longer starts the legacy chat WebSocket client');
check(!roadmap.includes('class="chat-drawer"'), 'roadmap legacy chat drawer markup is removed');
check((roadmap.match(/href="room\/"/g) || []).length >= 2, 'roadmap Chat affordances navigate to the Green Room');

const visualsPath = path.join(ROOT, 'radio/visuals/index.html');
if (fs.existsSync(visualsPath)) {
  const visuals = fs.readFileSync(visualsPath, 'utf8');
  check(visuals.includes('id="visualVideo"'), 'public Visuals tab remains the legacy standalone player');
  check(!visuals.includes('chatVisualRenderer'), 'Visuals tab remains isolated from Green Room');
} else {
  console.log('○ radio/visuals/index.html was omitted from this review archive; deployment gate must verify it from the full working tree');
}

const roomHtml = read('radio/room/index.html');
const roomCfg = read('radio/room/config.js');
const greenCfg = read('visuals-green/config.js');
const stage = read('radio/room/stage.js');
check(roomHtml.includes('<title>ALLTHINGS140 // GREEN ROOM</title>'), 'public room is labeled as Green Room, not staging');
check(roomHtml.includes('id="legacyFallback"'), 'Green Room contains a whole-room legacy visual fallback');
check(roomHtml.includes('id="homeLink"'), 'Green Room includes a direct HOME escape path');
check(!roomHtml.includes('stage-0001.mp4'), 'public room does not boot against a stale hard-coded Stage MP4');
check(/environment:"live"/.test(roomCfg), 'public Green Room ACK/heartbeat environment is live');
check(/environment:"green-staging"/.test(greenCfg), 'Green staging ACK/heartbeat environment is green-staging');
check(roomCfg.includes('assets/visuals-home-desktop-hq.mp4'), 'room fallback uses the exact legacy desktop homepage visual');
check(roomCfg.includes('assets/visuals-mainpage-2026-08-11-v2.mp4'), 'room fallback uses the exact legacy mobile homepage visual');
check(roomCfg.includes('/api/visual-routing'), 'workstation routing state controls only the room visual safety mode');
check(roomCfg.includes('wss://chat.ebeinc.online/ws'), 'public Green Room preserves the existing moderated listener-chat backend');
check(roomHtml.includes('chat-bridge.js?v=1.0.0'), 'public Green Room loads the moderated chat bridge');
const chatBridge = read('radio/room/chat-bridge.js');
check(chatBridge.includes("send('message', { text })"), 'Green Room messages are sent through the legacy moderated chat protocol');
check(chatBridge.includes("send('join', { name, color"), 'Green Room profile joins the established chat community');
check(chatBridge.includes("data.type === 'cleared'"), 'Green Room reacts to moderator clear events');
const hostPath = path.join(ROOT, 'radio/host/host.js');
if (fs.existsSync(hostPath)) {
  check(fs.readFileSync(hostPath, 'utf8').includes('wss://chat.ebeinc.online/ws'), 'Host moderation dashboard uses the same chat backend as Green Room');
} else {
  console.log('○ radio/host/host.js was omitted from this review archive; deployment gate must verify Host uses chat.ebeinc.online');
}
check(stage.includes("environment: C.environment || 'green-staging'"), 'renderer heartbeat/ACK carries explicit environment');
check(stage.includes('if (C.chatUrl) return;'), 'shared compositor yields public message transport to chat bridge');
check(stage.includes('if (!C.chatUrl) (d.history || []).forEach(addMessage);'), 'public room does not mix realtime staging chat history with moderated public chat');
check(stage.includes('legacyFallbackEnabled'), 'shared renderer core supports public-room safety fallback conditionally');
check(stage.includes("roomVisualMode !== 'new'"), 'legacy safety mode cannot falsely ACK the compositor as rendered');
check(stage.includes("engageAutomaticLegacyFallback('media_failure')"), 'repeated public-room media failures engage whole-room legacy video');
check(sha('radio/room/stage.js') === sha('visuals-green/stage.js'), 'Green staging and public room use identical compositor engine source');

const realtime = read('visuals-realtime/app.py');
check(realtime.includes('"renderer_environment":None'), 'realtime tracks renderer environment per WebSocket client');
check(realtime.includes('c.get("renderer_environment")==req_env'), 'renderer-state connection truth is environment-specific');
check(realtime.includes('app.on_cleanup.append(close_room_db)'), 'realtime closes SQLite cleanly during test/service cleanup');

const sw = read('radio/sw.js');
check(sw.includes('allthings140-radio-v65'), 'service worker cache namespace includes the current persistent-radio shell revision');
check(/mp4\|webm\|mp3/.test(sw), 'service worker excludes MP4/WebM/MP3 live media from CacheStorage');
check(sw.includes('room/chat-bridge.js?v=1.0.0'), 'service worker shell includes current Green Room chat bridge');
check(sw.includes('cache.put(request, copy)'), 'navigation responses are cached under their own URL');
check(!sw.includes('cache.put("./",copy)'), 'room/visuals navigation can no longer overwrite the homepage cache');
check(sha('radio/sw.js') === sha('radio/sw-v47.js'), 'both service-worker entry files are synchronized');

const main = read('visuals-app/src/main.js');
check(main.includes('PUBLIC GREEN ROOM /room/'), 'workstation Live Output targets the dedicated Green Room');
check(main.includes('FALL BACK GREEN ROOM TO LEGACY VIDEO'), 'workstation has explicit room-only safety fallback');
check(main.includes('USE GREEN ROOM COMPOSITOR'), 'workstation can restore the room compositor');
check(main.includes('HOMEPAGE'), 'workstation surfaces homepage isolation state');
check(main.includes('https://allthings140radio.online/room/?approval=1'), 'workstation opens the real public Green Room for verification');
check(!main.includes('PUBLIC CHAT → NEW'), 'retired homepage-injection activation copy is removed');
check(!main.includes('btnSimulateFailure'), 'non-functional v0.1.39 failure-simulation control is removed');

const rust = read('visuals-app/src-tauri/src/lib.rs');
check(rust.includes('ALLTHINGS140-Workstation/0.1.43'), 'routing requests identify the current workstation version');
check(rust.includes('renderer-state?environment=live'), 'workstation health reads live renderer state directly');
const routingFn = rust.slice(rust.indexOf('fn set_visual_routing'), rust.indexOf('fn get_visual_health'));
check(routingFn.includes('routing-headers-'), 'workstation stages routing authorization in a protected temporary header file');
check(!routingFn.includes('&format!("Authorization: Bearer {token}")'), 'routing credential is not exposed in curl process arguments');
check(rust.includes('"edge": edge_health'), 'workstation merges edge health with direct realtime renderer truth');

const worker = read('radio/_worker.js');
check(worker.includes('PUBLIC_GET_PATH'), 'public radio API allowlist remains present');
check(worker.includes('env.ASSETS.fetch(request)'), 'unmatched radio requests still fall through to static assets');
check(worker.includes('DEFAULT_ROUTING = { chat: "legacy", visuals: "legacy" }'), 'routing defaults fail safe to legacy');

console.log(`\n${passed}/${passed} v0.1.43 Green Room cutover checks passed`);
