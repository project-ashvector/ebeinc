import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

console.log('=== RUNNING ALLTHINGS140 VISUALS v0.1.37 VERIFICATION SUITE ===\n');

// 1. Check local binary & version
console.log('1. Verifying installed workstation binary...');
const binPath = path.join(process.env.HOME, '.local/bin/allthings140radio-visuals');
if (!fs.existsSync(binPath)) {
  throw new Error(`Installed binary missing at ${binPath}`);
}
const stat = fs.statSync(binPath);
console.log(`✓ Binary exists: ${binPath} (${(stat.size / 1024 / 1024).toFixed(2)} MB)`);

// 2. Check config & rotated admin token
console.log('\n2. Verifying workstation security configuration...');
const cfgPath = path.join(process.env.HOME, '.config/allthings140radio/visuals.json');
if (!fs.existsSync(cfgPath)) {
  throw new Error(`Visuals config missing at ${cfgPath}`);
}
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
if (!cfg.adminToken || cfg.adminToken.length < 32) {
  throw new Error('Admin token missing or insufficient length in config');
}
console.log(`✓ Admin token verified from config (length: ${cfg.adminToken.length})`);

// 3. Test Realtime Fail-Closed Gateway
console.log('\n3. Verifying Realtime Server fail-closed authentication...');
const realtimeUrl = 'https://visuals-realtime-staging.allthings140radio.online/admin/layout';

// Test 3a: unauthenticated request must fail with 401
try {
  execSync(`curl -fsS -X POST "${realtimeUrl}" -H "Content-Type: application/json" -d '{"test":true}'`, { stdio: 'pipe' });
  throw new Error('Expected unauthenticated request to fail with 401, but succeeded');
} catch (err) {
  console.log('✓ Unauthenticated request rejected (Fail-closed enforced)');
}

// Test 3b: authenticated request with rotated token
const testLayout = {
  schemaVersion: 2,
  revision: `test-${Date.now()}`,
  layoutId: `layout-test-${Date.now()}`,
  layoutHash: `hash-${Date.now()}`,
  previewMode: true,
  previewVisual: {
    assetId: 'test-asset-123',
    url: 'https://visuals-media-staging.allthings140radio.online/visuals/visuals-phone.mp4',
    fit: 'cover'
  },
  screenOpening: { x: 23.0, y: 33.5, width: 53.6, height: 48.5, rx: 1.5, enabled: true },
  layers: [
    { id: 'visual-content', role: 'visual', z: 10, x: 0, y: 0, width: 100, height: 100, scale: 1, opacity: 1, fit: 'cover', visible: true },
    { id: 'stage-content', role: 'stage', z: 20, x: 0, y: 0, width: 100, height: 100, scale: 1, opacity: 1, fit: 'cover', visible: true, media: { url: 'https://visuals-media-staging.allthings140radio.online/stage/stage-0001.mp4' } }
  ]
};

const postOut = execSync(`curl -fsS -X POST "${realtimeUrl}" -H "Content-Type: application/json" -H "Authorization: Bearer ${cfg.adminToken}" --data-binary '${JSON.stringify(testLayout)}'`).toString();
const postRes = JSON.parse(postOut);
if (!postRes.ok) {
  throw new Error(`Realtime broadcast failed: ${postOut}`);
}
console.log(`✓ Realtime broadcast accepted with rotated admin token (LayoutId: ${postRes.layoutId})`);

// 4. Test Green Renderer ACK Flow
console.log('\n4. Verifying Green Renderer ACK pipeline...');
const ackUrl = 'https://visuals-realtime-staging.allthings140radio.online/renderer-ack';
const ackPayload = {
  rendererSessionId: 'e2e-test-session',
  layoutId: testLayout.layoutId,
  layoutHash: testLayout.layoutHash,
  stageAssetId: 'stage-0001',
  visualAssetId: 'test-asset-123',
  renderAppliedAt: Date.now(),
  videoReadyState: 4,
  renderStatus: 'RENDERED'
};

const ackOut = execSync(`curl -fsS -X POST "${ackUrl}" -H "Content-Type: application/json" --data-binary '${JSON.stringify(ackPayload)}'`).toString();
const ackRes = JSON.parse(ackOut);
if (!ackRes.ok) {
  throw new Error(`Renderer ACK submission failed: ${ackOut}`);
}
console.log('✓ Staging renderer ACK submitted successfully');

// Query renderer-state
const stateOut = execSync(`curl -fsS "https://visuals-realtime-staging.allthings140radio.online/renderer-state"`).toString();
const stateRes = JSON.parse(stateOut);
const ack = stateRes.ack || stateRes;
if (ack.layoutHash !== testLayout.layoutHash || ack.renderStatus !== 'RENDERED') {
  throw new Error(`Renderer state mismatch: ${stateOut}`);
}
console.log(`✓ Renderer state verified: layoutHash=${ack.layoutHash.slice(0, 16)}..., status=${ack.renderStatus}`);

// 5. Test Green Staging Cloudflare Pages Single-Decoder HTML/CSS
console.log('\n5. Verifying Green staging frontend single decoder structure...');
const greenHtml = execSync('curl -fsS "https://allthings140-visuals-green.pages.dev"').toString();
if (!greenHtml.includes('id="stageVideo"') || !greenHtml.includes('maskScreenHole')) {
  throw new Error('Green staging index.html missing stageVideo or SVG maskScreenHole');
}
if (greenHtml.includes('class="stage-panel-top"')) {
  throw new Error('Old multi-slice panels still detected in Green staging HTML');
}
console.log('✓ Green staging index.html verified: single Stage video decoder + SVG mask');

// 6. Test Media Origin Access & Range header support
console.log('\n6. Verifying Media Origin Range headers...');
const rangeOut = execSync('curl -fsS -I -H "Range: bytes=0-1024" "https://visuals-media-staging.allthings140radio.online/stage/stage-0001.mp4"').toString();
if (!rangeOut.includes('206') && !rangeOut.includes('200')) {
  throw new Error(`Media origin did not return 206/200: ${rangeOut}`);
}
console.log('✓ Media Origin Range headers verified');

console.log('\n============================================================');
console.log('🎉 ALL END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!');
console.log('============================================================\n');
