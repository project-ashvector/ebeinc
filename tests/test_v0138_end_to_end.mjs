import fs from 'node:fs';
import path from 'node:path';

console.log('=== ALLTHINGS140 VISUALS v0.1.38 TARGET-WORKSTATION VERIFICATION ===\n');
const RUN_MUTATING = process.env.AT140_RUN_STAGING_MUTATION_TESTS === '1';

function requireOk(cond, msg) { if (!cond) throw new Error(msg); console.log(`✓ ${msg}`); }
async function fetchTimeout(url, options = {}, ms = 6000) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms);
  try { return await fetch(url, { ...options, signal: c.signal }); }
  finally { clearTimeout(t); }
}

// 1. Installed binary
const binPath = path.join(process.env.HOME, '.local/bin/allthings140radio-visuals');
requireOk(fs.existsSync(binPath), `Installed binary exists: ${binPath}`);
const stat = fs.statSync(binPath);
console.log(`  Binary size: ${(stat.size / 1024 / 1024).toFixed(2)} MB`);

// 2. Config exists; never print or shell the token.
const cfgPath = path.join(process.env.HOME, '.config/allthings140radio/visuals.json');
requireOk(fs.existsSync(cfgPath), `Visuals config exists: ${cfgPath}`);
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
requireOk(typeof cfg.adminToken === 'string' && cfg.adminToken.length >= 32, 'Admin token is configured (value not printed)');
const mode = fs.statSync(cfgPath).mode & 0o777;
requireOk((mode & 0o077) === 0, `Visuals config is not group/world-readable (mode ${mode.toString(8)})`);

// 3. Realtime health & fail-closed auth
const base = 'https://visuals-realtime-staging.allthings140radio.online';
let res = await fetchTimeout(`${base}/health`, { cache: 'no-store' });
requireOk(res.ok, `Realtime health responds HTTP ${res.status}`);
const health = await res.json();
console.log(`  Realtime version: ${health.version}`);

res = await fetchTimeout(`${base}/admin/layout`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ test: true })
});
requireOk(res.status === 401 || res.status === 503, `Unauthenticated admin publish fails closed (HTTP ${res.status})`);

// 4. Green frontend structure (read-only)
const greenUrl = 'https://allthings140-visuals-green.pages.dev/?approval=1';
res = await fetchTimeout(greenUrl, { cache: 'no-store' });
requireOk(res.ok, `Green staging responds HTTP ${res.status}`);
const greenHtml = await res.text();
requireOk(greenHtml.includes('id="stageVideo"') && greenHtml.includes('maskScreenHole'), 'Green uses one Stage decoder + stage aperture mask');
requireOk(!greenHtml.includes('class="stage-panel-top"'), 'Legacy Green multi-slice Stage compositor is absent');

// 5. Optional staging mutation test. Explicit opt-in only.
if (!RUN_MUTATING) {
  console.log('\nℹ Skipping layout/renderer mutation test. Set AT140_RUN_STAGING_MUTATION_TESTS=1 to run it intentionally.');
} else {
  console.log('\nRunning explicit staging mutation test...');
  const stamp = Date.now();
  const testLayout = {
    schemaVersion: 2,
    revision: `test-${stamp}`,
    layoutId: `layout-test-${stamp}`,
    layoutHash: `hash-${stamp}`,
    previewMode: true,
    productionLocked: true,
    previewVisual: {
      assetId: 'known-good-fallback',
      url: 'https://allthings140radio.online/assets/visuals-phone.mp4?v=1.1.0',
      fit: 'cover'
    },
    screenOpening: { x: 23, y: 33.5, width: 53.6, height: 48.5, rx: 1.5, enabled: true },
    layers: [
      { id: 'visual-content', role: 'visual', z: 10, x: 0, y: 0, width: 100, height: 100, scale: 1, opacity: 1, fit: 'cover', visible: true },
      { id: 'stage-content', role: 'stage', z: 20, x: 0, y: 0, width: 100, height: 100, scale: 1, opacity: 1, fit: 'cover', visible: true }
    ]
  };
  res = await fetchTimeout(`${base}/admin/layout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${cfg.adminToken}` },
    body: JSON.stringify(testLayout)
  });
  requireOk(res.ok, `Authenticated staging layout publish accepted (HTTP ${res.status})`);
  console.log('  WARNING: this opt-in test intentionally changed the active Green staging layout.');
}

console.log('\n✓ v0.1.38 target-workstation verification completed');
