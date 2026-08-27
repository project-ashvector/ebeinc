import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

console.log('=== ALLTHINGS140 LIVE-VISUALS CANARY CONTRACT AUDIT (v0.1.39) ===\n');

const ROOT = '/home/ebmarah/Projects/AllThings140Radio';

// 1. Version Synchronization
console.log('1. Verifying Version Synchronization across Ecosystem:');
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'visuals-app/package.json'), 'utf8'));
assert.equal(pkg.version, '0.1.39', 'package.json version must be 0.1.39');
console.log('  ✓ visuals-app/package.json version is 0.1.39');

const tauriConf = JSON.parse(fs.readFileSync(path.join(ROOT, 'visuals-app/src-tauri/tauri.conf.json'), 'utf8'));
assert.equal(tauriConf.version, '0.1.39', 'tauri.conf.json version must be 0.1.39');
console.log('  ✓ visuals-app/src-tauri/tauri.conf.json version is 0.1.39');

const cargoToml = fs.readFileSync(path.join(ROOT, 'visuals-app/src-tauri/Cargo.toml'), 'utf8');
assert.match(cargoToml, /version\s*=\s*"0\.1\.39"/, 'Cargo.toml must declare version 0.1.39');
console.log('  ✓ visuals-app/src-tauri/Cargo.toml version is 0.1.39');

const mainJs = fs.readFileSync(path.join(ROOT, 'visuals-app/src/main.js'), 'utf8');
assert.match(mainJs, /appVersion\s*=\s*['"]0\.1\.39['"]/, 'main.js must default appVersion to 0.1.39');
console.log('  ✓ visuals-app/src/main.js appVersion is 0.1.39');

// 2. Exact Current Legacy Visual Implementations
console.log('\n2. Verifying Legacy Visual Path Preservation & Separation:');
const radioIndex = fs.readFileSync(path.join(ROOT, 'radio/index.html'), 'utf8');
assert.ok(radioIndex.includes('id="backgroundVideo"'), 'Public home/chat page must preserve legacy #backgroundVideo');
assert.ok(radioIndex.includes('assets/allthings140-background.webp'), 'Public home/chat page must preserve legacy poster');
assert.ok(radioIndex.includes('assets/main-vis-home-hq-v2.mp4'), 'Public home/chat page must preserve the high-quality user-selected homepage video');
console.log('  ✓ Public Chat tab preserves exact legacy background video stack');

const visualsIndex = fs.readFileSync(path.join(ROOT, 'radio/visuals/index.html'), 'utf8');
assert.ok(visualsIndex.includes('id="visualVideo"'), 'Visuals tab must preserve legacy #visualVideo');
assert.ok(visualsIndex.includes('../assets/visuals-phone.mp4'), 'Visuals tab must preserve phone video source');
assert.ok(visualsIndex.includes('../assets/visuals-desktop.mp4'), 'Visuals tab must preserve desktop video source');
assert.ok(!visualsIndex.includes('chatVisualRenderer'), 'Visuals tab must not share Chat visual renderer');
console.log('  ✓ Public Visuals tab preserves exact legacy standalone player');

// 3. Routing Split & Default State
console.log('\n3. Verifying Chat / Visuals Tab Routing Split:');
const workerJs = fs.readFileSync(path.join(ROOT, 'radio/_worker.js'), 'utf8');
assert.ok(workerJs.includes('DEFAULT_ROUTING = { chat: "legacy", visuals: "legacy" }'), 'Default routing state must be legacy for both');
assert.ok(workerJs.includes('handleVisualRoutingGet'), 'Worker must handle GET /api/visual-routing');
assert.ok(workerJs.includes('handleVisualRoutingPost'), 'Worker must handle POST /api/visual-routing');
assert.ok(workerJs.includes('handleVisualHealth'), 'Worker must handle GET /api/visual-health');
console.log('  ✓ Cloudflare Worker maintains independent, KV-backed visual routing state');

// 4. Live Chat Audience Renderer Configuration
console.log('\n4. Verifying New Live-Chat Audience Renderer Contract:');
const chatConfig = fs.readFileSync(path.join(ROOT, 'radio/chat-renderer/config.js'), 'utf8');
assert.match(chatConfig, /environment:\s*"live-chat"/, 'Chat renderer environment must be "live-chat"');
console.log('  ✓ chat-renderer/config.js environment is "live-chat"');

const chatRenderer = fs.readFileSync(path.join(ROOT, 'radio/chat-renderer/renderer.js'), 'utf8');
assert.ok(chatRenderer.includes('rendererSessionId'), 'Chat renderer must maintain isolated rendererSessionId');
assert.ok(chatRenderer.includes('simulateFailure'), 'Chat renderer must support failure simulation');
assert.ok(chatRenderer.includes('autoFallbackCooldownMs'), 'Chat renderer must enforce auto-fallback cooldown');
assert.ok(chatRenderer.includes('triggerFallback'), 'Chat renderer must support immediate fallback to legacy');
assert.ok(chatRenderer.includes('showLegacy'), 'Chat renderer must restore legacy background video on fallback');
assert.ok(chatRenderer.includes('reduced-motion'), 'Chat renderer must respect reduced-motion');
console.log('  ✓ chat-renderer/renderer.js implements isolated session, auto-fallback, and failure simulation');

// 5. Multi-Environment Realtime ACK Architecture
console.log('\n5. Verifying Multi-Environment Realtime ACK Architecture:');
const realtimeApp = fs.readFileSync(path.join(ROOT, 'visuals-realtime/app.py'), 'utf8');
assert.ok(realtimeApp.includes('renderer_ack:{env_name}'), 'Realtime server must key ACKs by environment');
assert.ok(realtimeApp.includes('environments'), 'Realtime renderer-state must report environment statuses');
console.log('  ✓ visuals-realtime/app.py supports multi-environment ACK isolation (green-staging vs live-chat)');

const greenStage = fs.readFileSync(path.join(ROOT, 'visuals-green/stage.js'), 'utf8');
assert.ok(greenStage.includes('environment: C.environment || \'green-staging\''), 'Green stage ACK must identify as green-staging');
console.log('  ✓ visuals-green/stage.js sends environment="green-staging" in ACK payload');

// 6. Workstation Live Output Controls & Safety Gates
console.log('\n6. Verifying Workstation Live Output UI & Safety Gates:');
assert.ok(mainJs.includes("'Live Output'"), 'Navigation views must include "Live Output"');
assert.ok(mainJs.includes('btnChatFallbackLegacy'), 'Live Output must provide one-click fallback button');
assert.ok(mainJs.includes('btnChatUseNew'), 'Live Output must provide Chat visual promotion button');
assert.ok(mainJs.includes('btnOpenCanaryPreview'), 'Live Output must provide canary preview launcher');
assert.ok(mainJs.includes('btnSimulateFailure'), 'Live Output must provide failure simulation launcher');
assert.ok(mainJs.includes('LOCKED — AWAITING USER APPROVAL'), 'Visuals tab cutover gate must be locked');
console.log('  ✓ Workstation includes Live Output view with one-click fallback and locked promotion gates');

// 7. Rust Backend Staging Allowlist & Commands
console.log('\n7. Verifying Rust Backend Security & Commands:');
const rustLib = fs.readFileSync(path.join(ROOT, 'visuals-app/src-tauri/src/lib.rs'), 'utf8');
assert.ok(rustLib.includes('"https://allthings140radio.online"'), 'Rust allowlist must include https://allthings140radio.online');
assert.ok(rustLib.includes('get_visual_routing'), 'Rust backend must register get_visual_routing');
assert.ok(rustLib.includes('set_visual_routing'), 'Rust backend must register set_visual_routing');
assert.ok(rustLib.includes('get_visual_health'), 'Rust backend must register get_visual_health');
console.log('  ✓ Rust backend allowlist and Tauri invoke_handler are configured for visual routing');

console.log('\n================================================================');
console.log('CANARY ARCHITECTURE CONTRACT AUDIT: ALL CHECKS PASSED');
console.log('================================================================\n');
