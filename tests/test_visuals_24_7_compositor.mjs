import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const stage = readFileSync(new URL('../radio/room/workstation-stage.js', import.meta.url), 'utf8');
const css = readFileSync(new URL('../radio/room/stage.css', import.meta.url), 'utf8');
const adaptive = readFileSync(new URL('../radio/visuals/adaptive.html', import.meta.url), 'utf8');
const config = readFileSync(new URL('../radio/visuals/config-live.js', import.meta.url), 'utf8');
const app = readFileSync(new URL('../visuals-app/src/main.js', import.meta.url), 'utf8');

let passed = 0;
const test = (name, fn) => { fn(); passed += 1; console.log(`✓ ${name}`); };

test('crossfade is 500-800ms', () => {
  assert.match(stage, /CROSSFADE_MS = Math\.max\(500, Math\.min\(800/);
  assert.match(css, /transition:opacity 0\.7s ease/);
});

test('live compositor stays pending until first frame', () => {
  assert.match(stage, /live-pending/);
  assert.match(stage, /live-armed/);
  assert.match(stage, /live_first_frame_missing/);
  assert.match(css, /#stageComposition\.live-pending/);
});

test('failed next visual does not clear current before first frame', () => {
  assert.match(stage, /handleVisualFailure\(item, 'first_frame_failed'\)/);
  assert.match(stage, /visualSwapGeneration/);
  assert.doesNotMatch(stage, /prevVideo\.pause\(\);\s*\n\s*\}, 400\)/);
});

test('public visuals tab uses only HQ HLS from master, never MP4 or phone fallbacks', () => {
  assert.match(adaptive, /visuals-desktop-v10\/index\.m3u8/);
  assert.match(adaptive, /desktopHls\.loadSource\(video\.dataset\.desktopSrc\)/);
  assert.doesNotMatch(adaptive, /visuals-desktop\.mp4/);
  assert.doesNotMatch(adaptive, /phone-visuals/);
  assert.doesNotMatch(adaptive, /desktopFallback/);
  assert.doesNotMatch(adaptive, /data-mobile-src/);
  assert.doesNotMatch(adaptive, /if \(document\.hidden\) \{\s*video\.pause/);
  assert.match(config, /legacyFallbackHls:"https:\/\/allthings140radio\.online\/assets\/visuals-desktop-v10\/index\.m3u8"/);
  assert.doesNotMatch(config, /legacyFallbackDesktop/);
  assert.doesNotMatch(config, /legacyFallbackMobile/);
  assert.match(stage, /visualsHlsOnly/);
});

test('workstation visual layer uses A\/B buffers', () => {
  assert.match(app, /visual-ab/);
  assert.match(app, /setVisualAbSource/);
  assert.match(app, /waitVisualFrame/);
});

console.log(`${passed}/${passed} visuals 24\/7 compositor contract checks passed`);
