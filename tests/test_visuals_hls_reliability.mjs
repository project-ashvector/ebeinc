import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const adaptive = readFileSync(new URL('../radio/visuals/adaptive.html', import.meta.url), 'utf8');
const index = readFileSync(new URL('../radio/visuals/index.html', import.meta.url), 'utf8');
const legacy = readFileSync(new URL('../radio/visuals/legacy.html', import.meta.url), 'utf8');
const player = readFileSync(new URL('../radio/visuals/hls-fallback-player.js', import.meta.url), 'utf8');
const stage = readFileSync(new URL('../radio/room/workstation-stage.js', import.meta.url), 'utf8');
const master = readFileSync(new URL('../radio/assets/visuals-desktop-abr/index.m3u8', import.meta.url), 'utf8');
const v10 = readFileSync(new URL('../radio/assets/visuals-desktop-v10/index.m3u8', import.meta.url), 'utf8');

let passed = 0;
const test = (name, fn) => { fn(); passed += 1; console.log(`✓ ${name}`); };

test('HLS starts from the page player, not workstation', () => {
  assert.match(adaptive, /AT140HlsFallback\.start\(video\)/);
  assert.match(adaptive, /initVideo\(\);/);
  const initAt = adaptive.indexOf('initVideo();');
  const stageAt = adaptive.indexOf('workstation-stage.js');
  assert.ok(initAt > 0 && stageAt > initAt, 'HLS init runs before compositor script');
});

test('player never pauses on document.hidden', () => {
  assert.match(player, /visibilitychange/);
  assert.doesNotMatch(player, /if \(document\.hidden\) \{\s*video\.pause/);
  assert.match(player, /add\(document, 'visibilitychange', \(\) => \{ play\(\); \}\)/);
  assert.doesNotMatch(legacy, /if \(document\.hidden\) \{\s*video\.pause/);
});

test('player recovers and destroys', () => {
  assert.match(player, /recover\('network'\)/);
  assert.match(player, /recover\('media'\)/);
  assert.match(player, /recover\('stall'\)/);
  assert.match(player, /recover\('online'\)/);
  assert.match(player, /add\(window, 'pagehide', \(\) => destroy\(\)\)/);
  assert.match(player, /hls\.destroy/);
  assert.match(stage, /pagehide/);
});

test('live wait for decoded frame; HLS stays running underneath', () => {
  assert.match(stage, /live-pending/);
  assert.match(stage, /live_first_frame_missing/);
  assert.doesNotMatch(stage, /fallbackVideo\.pause\(\)/);
  assert.match(stage, /hls_not_ready_before_live_fade/);
});

test('ABR ladder keeps v10 as the highest rung', () => {
  assert.match(master, /visuals-desktop-v10-720p\/index\.m3u8/);
  assert.match(master, /visuals-desktop-v9\/index\.m3u8/);
  assert.match(master, /visuals-desktop-v10\/index\.m3u8/);
  const v10At = master.lastIndexOf('visuals-desktop-v10/index.m3u8');
  const v720At = master.indexOf('visuals-desktop-v10-720p/index.m3u8');
  assert.ok(v10At > v720At);
  assert.match(master, /BANDWIDTH=18100000/);
  assert.match(v10, /#EXT-X-PLAYLIST-TYPE:VOD/);
  assert.ok(existsSync(new URL('../radio/assets/visuals-desktop-v10/segment-0000.ts', import.meta.url)));
});

test('all visuals documents share the singleton player', () => {
  for (const doc of [adaptive, index, legacy]) {
    assert.match(doc, /hls-fallback-player\.js/);
    assert.match(doc, /visuals-desktop-abr\/index\.m3u8/);
  }
});

console.log(`${passed}/${passed} visuals HLS reliability contract checks passed`);
