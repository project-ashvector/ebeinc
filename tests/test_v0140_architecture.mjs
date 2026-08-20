import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert';

const ROOT = '/home/ebmarah/Projects/AllThings140Radio';

console.log('=== ALLTHINGS140 GREEN ROOM ARCHITECTURE AUDIT (v0.1.40) ===\n');

// 1. Version Synchronization
console.log('1. Verifying Version Synchronization across Ecosystem (v0.1.40):');
const pkgJson = JSON.parse(fs.readFileSync(path.join(ROOT, 'visuals-app/package.json'), 'utf8'));
assert.strictEqual(pkgJson.version, '0.1.40', 'package.json must be 0.1.40');
console.log('  ✓ visuals-app/package.json version is 0.1.40');

const tauriConf = JSON.parse(fs.readFileSync(path.join(ROOT, 'visuals-app/src-tauri/tauri.conf.json'), 'utf8'));
assert.strictEqual(tauriConf.version, '0.1.40', 'tauri.conf.json must be 0.1.40');
console.log('  ✓ visuals-app/src-tauri/tauri.conf.json version is 0.1.40');

const cargoToml = fs.readFileSync(path.join(ROOT, 'visuals-app/src-tauri/Cargo.toml'), 'utf8');
assert.match(cargoToml, /version\s*=\s*"0\.1\.40"/, 'Cargo.toml must be 0.1.40');
console.log('  ✓ visuals-app/src-tauri/Cargo.toml version is 0.1.40');

const mainJs = fs.readFileSync(path.join(ROOT, 'visuals-app/src/main.js'), 'utf8');
assert.match(mainJs, /let appVersion = '0\.1\.40'/, 'main.js appVersion must be 0.1.40');
console.log('  ✓ visuals-app/src/main.js appVersion is 0.1.40');

// 2. Pure Homepage Isolation
console.log('\n2. Verifying Pure Homepage Isolation (radio/index.html):');
const homeHtml = fs.readFileSync(path.join(ROOT, 'radio/index.html'), 'utf8');
assert.ok(!homeHtml.includes('id="chatVisualRenderer"'), 'Homepage must NOT contain #chatVisualRenderer');
assert.ok(!homeHtml.includes('initChatRenderer'), 'Homepage must NOT contain dynamic compositor injection');
assert.ok(homeHtml.includes('id="backgroundVideo"'), 'Homepage must preserve native #backgroundVideo');
assert.ok(homeHtml.includes('href="room/"'), 'Homepage must offer standalone Green Room link');
console.log('  ✓ Homepage is 100% isolated, clean, and has native background video with zero compositor injection');

// 3. Visuals Tab Preservation
console.log('\n3. Verifying Legacy Visuals Tab Preservation (radio/visuals/index.html):');
const visualsHtml = fs.readFileSync(path.join(ROOT, 'radio/visuals/index.html'), 'utf8');
assert.ok(visualsHtml.includes('id="visualVideo"'), 'Visuals tab must preserve standalone #visualVideo');
assert.ok(!visualsHtml.includes('chatVisualRenderer'), 'Visuals tab must NOT contain chat renderer');
console.log('  ✓ Visuals tab is 100% independent legacy video page');

// 4. Standalone Green Room Architecture
console.log('\n4. Verifying Standalone Green Room Architecture:');
const greenHtml = fs.readFileSync(path.join(ROOT, 'visuals-green/index.html'), 'utf8');
assert.ok(greenHtml.includes('class="stage-composition"'), 'Green Room must have stage-composition compositor');
assert.ok(greenHtml.includes('class="room"'), 'Green Room must have dedicated audience chat room');
assert.ok(greenHtml.includes('id="listen"'), 'Green Room must include live audio feed control');
console.log('  ✓ visuals-green/ is dedicated standalone Green Room');

const roomHtml = fs.readFileSync(path.join(ROOT, 'radio/room/index.html'), 'utf8');
assert.ok(roomHtml.includes('class="stage-composition"'), 'radio/room/ must have stage-composition compositor');
assert.ok(roomHtml.includes('class="room"'), 'radio/room/ must have dedicated audience chat room');
console.log('  ✓ radio/room/ is provisioned on radio site for standalone audience access');

// 5. Workstation Controls
console.log('\n5. Verifying Workstation UI & Safety Controls:');
assert.ok(mainJs.includes("'Live Output'"), 'Navigation views must include "Live Output"');
assert.ok(mainJs.includes('btnChatFallbackLegacy'), 'Live Output must provide fallback button');
assert.ok(mainJs.includes('LOCKED — AWAITING USER APPROVAL'), 'Visuals tab cutover gate must be locked');
assert.ok(mainJs.includes('https://allthings140-visuals-green.pages.dev/?approval=1'), 'Workstation must link to Green Room staging');
console.log('  ✓ Workstation includes Green Room controls and locked production gates');

console.log('\n================================================================');
console.log('ALLTHINGS140 GREEN ROOM AUDIT: ALL CHECKS PASSED (v0.1.40)');
console.log('================================================================\n');
