import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'src/main.js'), 'utf8');
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));

test('T1: CONNECTION LOST path resyncs dashboard (no button-only patch)', () => {
  assert.match(src, /phase = 'CONNECTION LOST'/);
  const lostIdx = src.indexOf("phase = 'CONNECTION LOST'");
  const after = src.slice(lostIdx, lostIdx + 800);
  assert.match(after, /syncLiveDashboard\(\)/);
  assert.doesNotMatch(after.split('scheduleLiveAutoRecover')[0], /renderLiveButtonState\(\);\s*\n\s*\}/);
});

test('T1b: reconnect button label present', () => {
  assert.match(src, /RECONNECT ● LIVE/);
  assert.match(src, /function syncLiveDashboard/);
});

test('T2/T4 helpers: recover without routing KV', () => {
  assert.match(src, /async function recoverWorkstationLive/);
  const start = src.indexOf('async function recoverWorkstationLive');
  const end = src.indexOf('async function startWorkstationLive', start);
  const body = src.slice(start, end);
  assert.doesNotMatch(body, /set_visual_routing/);
  assert.match(body, /set_workstation_live/);
  assert.match(body, /action: 'start'/);
});

test('T3: manual STOP clears wantLive and recover timer', () => {
  const start = src.indexOf('async function stopWorkstationLive');
  const end = src.indexOf('function buildAppShell', start);
  const body = src.slice(start, end);
  assert.match(body, /persistWantLive\(false\)/);
  assert.match(body, /clearLiveRecoverTimer/);
  assert.match(body, /set_workstation_live/);
});

test('T5: auto-recover gated on wantLive + healthy WS', () => {
  assert.match(src, /function scheduleLiveAutoRecover/);
  assert.match(src, /LIVE_RECOVER_MAX_ATTEMPTS/);
  assert.match(src, /metrics\.ws !== 'LIVE'/);
  assert.match(src, /adoptOrRecoverLiveSession/);
});

test('package version is 0.2.2', () => {
  assert.equal(pkg.version, '0.2.2');
  assert.match(src, /appVersion = '0\.2\.2'/);
});
