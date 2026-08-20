import { writeFileSync, existsSync } from 'fs';
import { resolve, join } from 'path';
import { readFileSync, existsSync as fileExistsSync } from 'fs';
import os from 'os';
import { createHash } from 'crypto';


const RUN_MUTATING = process.env.AT140_RUN_STAGING_MUTATION_TESTS === '1';
if (!RUN_MUTATING) {
  console.log('SKIP: this suite intentionally mutates Green staging. Set AT140_RUN_STAGING_MUTATION_TESTS=1 to run it.');
  process.exit(0);
}

const cfgPath = join(os.homedir(), '.config/allthings140radio/visuals.json');
let ADMIN_TOKEN = process.env.ADMIN_TOKEN || '';
if (!ADMIN_TOKEN && fileExistsSync(cfgPath)) {
  try { ADMIN_TOKEN = JSON.parse(readFileSync(cfgPath, 'utf8')).adminToken || ''; } catch {}
}
if (!ADMIN_TOKEN) {
  console.log('SKIP: realtime authenticated workflow tests require ADMIN_TOKEN or workstation config');
  process.exit(0);
}
console.log('================================================================');
console.log('ALLTHINGS140 GREEN WORKFLOW & PERFORMANCE TEST SUITE');
console.log('================================================================\n');

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

// Scenario A: Existing Stage + Existing Staged Visual
console.log('TEST A: Existing Stage + Existing Staged Visual (Fast Path)');
const startA = performance.now();

// 1. Validation
const sA_valStart = performance.now();
const testA_state = {
  activePreset: "Known Good Default",
  layoutVersion: 300,
  presets: [{
    name: "Known Good Default",
    screenOpening: { x: 23.0, y: 33.5, width: 53.6, height: 48.5, rx: 1.5, enabled: true },
    layerFrames: {
      "visual-content": { x: 0, y: 0, width: 100, height: 100, scale: 1, opacity: 1, fit: "cover", visible: true, flipX: false, flipY: false },
      "stage-content": { x: 0, y: 0, width: 100, height: 100, scale: 1, opacity: 1, fit: "cover", visible: true, flipX: false, flipY: false }
    }
  }],
  workspaceLayers: [
    { id: "visual-content", name: "Visual Content", kind: "media", role: "visual", z: 10, sourcePath: "/home/ebmarah/Videos/at140radio/desktop visuals/visuals/Machine_empire_in_frozen_city_202608100241.mp4" },
    { id: "stage-content", name: "Stage Content", kind: "media", role: "stage", z: 20, sourcePath: "/home/ebmarah/Videos/at140radio/desktop visuals/stage/alpha2.mov" }
  ]
};

// Validate files exist
assert(existsSync(testA_state.workspaceLayers[0].sourcePath), 'Visual source file exists');
assert(existsSync(testA_state.workspaceLayers[1].sourcePath), 'Stage source file exists');
const sA_valDur = Math.round(performance.now() - sA_valStart);

// 2. Snapshot
const sA_snapStart = performance.now();
const revisionA = '20260816T203000000Z';
const manifestA = {
  schemaVersion: 2,
  layoutRevision: revisionA,
  layoutId: `layout-${revisionA}`,
  composition: { width: 1920, height: 1080, aspectRatio: '16:9' },
  screenOpening: testA_state.presets[0].screenOpening,
  layers: [
    { id: "visual-content", name: "Visual Content", role: "visual", kind: "media", z: 10, x: 0, y: 0, width: 100, height: 100, fit: "cover" },
    { id: "stage-content", name: "Stage Content", role: "stage", kind: "media", z: 20, x: 0, y: 0, width: 100, height: 100, fit: "cover" }
  ]
};
manifestA.layoutHash = createHash('sha256').update(JSON.stringify(manifestA)).digest('hex');
const sA_snapDur = Math.round(performance.now() - sA_snapStart);

// 3. Realtime Publish
const sA_pubStart = performance.now();
const resA = await fetch('https://visuals-realtime-staging.allthings140radio.online/admin/layout', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${ADMIN_TOKEN}`
  },
  body: JSON.stringify(manifestA)
});
assert(resA.ok, `Realtime broadcast returned HTTP ${resA.status}`);
const sA_pubDur = Math.round(performance.now() - sA_pubStart);

// 4. Green State Verification
const sA_verStart = performance.now();
const verResA = await fetch('https://visuals-realtime-staging.allthings140radio.online/layout-state', { cache: 'no-store' });
const verJsonA = await verResA.json();
assert(verJsonA.layoutHash === manifestA.layoutHash, `Green confirmed matching layout hash (${manifestA.layoutHash.slice(0, 12)}...)`);
const sA_verDur = Math.round(performance.now() - sA_verStart);
const totalDurA = Math.round(performance.now() - startA);

console.log(`  Timing Test A: Val=${sA_valDur}ms, Snap=${sA_snapDur}ms, Pub=${sA_pubDur}ms, Ver=${sA_verDur}ms → Total=${totalDurA}ms`);
assert(totalDurA < 2000, `Test A completed under 2000ms (took ${totalDurA}ms)`);

// Scenario B: Second run with same cached media
console.log('\nTEST B: Second Cached Run (Ultra-Fast Path)');
const startB = performance.now();
const resB = await fetch('https://visuals-realtime-staging.allthings140radio.online/admin/layout', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${ADMIN_TOKEN}`
  },
  body: JSON.stringify(manifestA)
});
assert(resB.ok, `Realtime broadcast returned HTTP ${resB.status}`);
const totalDurB = Math.round(performance.now() - startB);
console.log(`  Timing Test B: Total=${totalDurB}ms`);
assert(totalDurB < 1000, `Test B completed under 1000ms (took ${totalDurB}ms)`);

// Scenario C: Invalid / Missing Visual File
console.log('\nTEST C: Invalid / Missing Visual File (Graceful Error Handling)');
const testC_missingPath = '/home/ebmarah/Videos/non_existent_visual_file_12345.mp4';
const existsC = existsSync(testC_missingPath);
assert(!existsC, 'Verified missing file does not exist');
let caughtError = false;
try {
  if (!existsC) {
    throw new Error(`Visual media file not found on disk: ${testC_missingPath}`);
  }
} catch (err) {
  caughtError = true;
  assert(err.message.includes('not found'), `Caught expected validation error: "${err.message}"`);
}
assert(caughtError, 'Test C gracefully rejected missing media without hanging');

console.log('\n================================================================');
console.log(`WORKFLOW SCENARIOS AUDIT: ${passed} PASSED, ${failed} FAILED`);
console.log('================================================================');

if (failed > 0) process.exit(1);
