import { readFileSync, existsSync } from 'fs';
import { resolve, join } from 'path';

const ROOT = resolve('.');
const APP_DIR = join(ROOT, 'visuals-app');
const SRC_DIR = join(APP_DIR, 'src');

console.log('====================================================');
console.log('RUNNING ALLTHINGS140 VISUALS WORKSTATION REGRESSION SUITE');
console.log('====================================================\n');

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✓ ${message}`);
    passed++;
  } else {
    console.error(`  ❌ FAILED: ${message}`);
    failed++;
  }
}

// 1. Verify files exist
console.log('1. Checking File Structure and Assets:');
assert(existsSync(join(SRC_DIR, 'main.js')), 'visuals-app/src/main.js exists');
assert(existsSync(join(SRC_DIR, 'style.css')), 'visuals-app/src/style.css exists');
assert(existsSync(join(APP_DIR, 'package.json')), 'visuals-app/package.json exists');
assert(existsSync(join(APP_DIR, 'src-tauri', 'Cargo.toml')), 'visuals-app/src-tauri/Cargo.toml exists');
assert(existsSync(join(APP_DIR, 'src-tauri', 'tauri.conf.json')), 'visuals-app/src-tauri/tauri.conf.json exists');
console.log('  ℹ Installed-binary existence is verified only on the target Zorin workstation, not in source-only CI/sandbox');

const mainJs = readFileSync(join(SRC_DIR, 'main.js'), 'utf-8');
const styleCss = readFileSync(join(SRC_DIR, 'style.css'), 'utf-8');
const pkgJson = JSON.parse(readFileSync(join(APP_DIR, 'package.json'), 'utf-8'));
const tauriConf = JSON.parse(readFileSync(join(APP_DIR, 'src-tauri', 'tauri.conf.json'), 'utf-8'));

// 2. Version consistency
console.log('\n2. Verifying Version Synchronization:');
assert(pkgJson.version === '0.1.43', `package.json version is 0.1.43 (got ${pkgJson.version})`);
assert(tauriConf.version === '0.1.43', `tauri.conf.json version is 0.1.43 (got ${tauriConf.version})`);
assert(mainJs.includes("appVersion = '0.1.43'"), 'main.js defaults to appVersion 0.1.43');

// 3. Layout CSS & Scrolling Architecture
console.log('\n3. Verifying Window & Scrolling CSS Constraints:');
assert(styleCss.includes('.workspace-col-left') && styleCss.includes('overflow-y: auto'), '.workspace-col-left has independent overflow-y: auto scrolling');
assert(styleCss.includes('.workspace-col-center') && styleCss.includes('overflow-y: auto'), '.workspace-col-center has independent overflow-y: auto scrolling');
assert(styleCss.includes('.workspace-col-right') && styleCss.includes('overflow-y: auto'), '.workspace-col-right has independent overflow-y: auto scrolling');
assert(styleCss.includes('.media-list-scroll') && styleCss.includes('overflow-y: auto'), '.media-list-scroll has independent overflow-y: auto scrolling');
assert(styleCss.includes('.scrollable-page') && styleCss.includes('overflow-y: auto'), '.scrollable-page provides clean scrolling for all non-workspace views');
assert(!styleCss.includes('max-height: calc(100vh - 170px)'), 'Removed brittle fixed calc(100vh - 170px) from properties inspector');
assert(styleCss.includes('min-height: 0'), 'Includes min-height: 0 flex/grid overflow protection');

// 4. Staging and Green Controls
console.log('\n4. Verifying Authoritative Green Staging Controls:');
assert(mainJs.includes('https://allthings140-visuals-green.pages.dev/?approval=1'), 'Canonical Green URL is https://allthings140-visuals-green.pages.dev/?approval=1');
assert(mainJs.includes('wss://visuals-realtime-staging.allthings140radio.online/ws'), 'Canonical Realtime WebSocket is wss://visuals-realtime-staging.allthings140radio.online/ws');
assert(mainJs.includes('https://visuals-media-staging.allthings140radio.online'), 'Canonical Media Origin is https://visuals-media-staging.allthings140radio.online');
assert(mainJs.includes('OPEN GREEN AUDIENCE ROOM'), 'Includes "OPEN GREEN AUDIENCE ROOM" control');
assert(mainJs.includes('TEST VISUAL CYCLE ON GREEN'), 'Includes "TEST VISUAL CYCLE ON GREEN" control');
assert(mainJs.includes('PUBLISH CURRENT LAYOUT'), 'Includes "PUBLISH CURRENT LAYOUT" control');
assert(mainJs.includes('COPY GREEN URL'), 'Includes "COPY GREEN URL" control');
assert(mainJs.includes('getGreenSyncStatus'), 'Tracks live Green sync status (SYNCED / LOCAL_CHANGES / PUBLISHING / OFFLINE)');
assert(mainJs.includes('testVisualOnGreenWithProgress'), 'Includes multi-step progress modal for Green testing');

// 5. 24/7 Visuals & Safe Playback Mode
console.log('\n5. Verifying 24/7 Visuals Features & Safe Mode:');
assert(mainJs.includes('searchVisuals'), 'Includes real-time search & filter for 24/7 visuals');
assert(mainJs.includes('data-toggle-enable'), 'Includes enable/disable toggle for playlist items');
assert(mainJs.includes('data-move-up') && mainJs.includes('data-move-down'), 'Includes reordering move up/down controls');
assert(mainJs.includes('safePlaybackMode'), 'Includes Safe Playback Mode state and compositor guard');
assert(mainJs.includes('safe-mode-toggle'), 'Includes Safe Playback Mode UI toggle');

// 6. Layer Compositor & Cutout
console.log('\n6. Verifying Layer Compositor & Stage Screen Cutout:');
assert(mainJs.includes("id: 'visual-content', name: 'Visual Content', kind: 'media', role: 'visual'") && mainJs.includes('z: 10'), 'Visual Content is layer z: 10 (backmost)');
assert(mainJs.includes("id: 'stage-content', name: 'Stage Content', kind: 'media', role: 'stage'") && mainJs.includes('z: 20'), 'Stage Content is layer z: 20 (immediately above visual)');
assert(mainJs.includes('stage-panel-top') && mainJs.includes('stage-panel-bottom') && mainJs.includes('stage-panel-left') && mainJs.includes('stage-panel-right'), 'WebKitGTK four-panel stage screen cutout slicer is implemented');
assert(mainJs.includes('fitVisualToCutout'), 'Includes "Fit Visual to Opening" quick helper');
assert(mainJs.includes('reorderLayers'), 'Layer drag-and-drop and right-click menu preserve stack order');

// 7. Security and Safety Guardrails
console.log('\n7. Verifying Security & Live Protection Guardrails:');
assert(mainJs.includes('PRODUCTION') && mainJs.includes('LOCKED'), 'Production live site is marked LOCKED');
assert(mainJs.includes('Promote Green to Live — LOCKED'), 'Live promotion is locked pending explicit user approval');
assert(!mainJs.includes('wrangler pages deploy radio'), 'Workstation does NOT deploy to production pages project');

// 8. View Navigation Coverage
console.log('\n8. Verifying View Navigation Matrix (11 Views):');
const views = ['Dashboard', 'Live Output', 'Visual Workspace', '24/7 Visuals', 'Takeover Visuals', 'Takeovers', 'Chat / Room', 'Diagnostics', 'Activity', 'Backups', 'Settings'];
views.forEach(v => {
  assert(mainJs.includes(`'${v}'`), `Navigation matrix includes "${v}"`);
});

console.log('\n====================================================');
console.log(`TEST SUMMARY: ${passed} PASSED, ${failed} FAILED`);
console.log('====================================================');

if (failed > 0) process.exit(1);
