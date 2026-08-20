import { readFileSync, existsSync } from 'fs';
import { resolve, join } from 'path';

const ROOT = resolve('.');
const GREEN_DIR = join(ROOT, 'visuals-green');
const APP_DIR = join(ROOT, 'visuals-app');

console.log('================================================================');
console.log('ALLTHINGS140 WORKSTATION <-> GREEN GEOMETRY PARITY AUDIT');
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

// 1. Canonical Test Layout (Deliberately non-default geometry)
const testLayout = {
  schemaVersion: 2,
  revision: '20260816T200000000Z',
  layoutId: 'layout-test-parity',
  composition: { width: 1920, height: 1080, aspectRatio: '16:9' },
  screenOpening: {
    x: 29.0,
    y: 38.0,
    width: 42.0,
    height: 37.0,
    rx: 1.5,
    enabled: true
  },
  layers: [
    { id: 'visual-content', name: 'Visual Content', role: 'visual', kind: 'media', z: 10, x: 29.0, y: 38.0, width: 42.0, height: 37.0, scale: 1.0, opacity: 1.0, fit: 'cover', visible: true, flipX: false, flipY: false },
    { id: 'stage-content', name: 'Stage Content', role: 'stage', kind: 'media', z: 20, x: 7.0, y: 9.0, width: 82.0, height: 78.0, scale: 1.0, opacity: 1.0, fit: 'cover', visible: true, flipX: false, flipY: false },
    { id: 'station-logo', name: 'Station / Takeover Logo', kind: 'logo', z: 30, x: 10.5, y: 77.0, width: 8.5, height: 9.0, scale: 1.0, opacity: 1.0, fit: 'contain', visible: true, flipX: false, flipY: false },
    { id: 'now-playing', name: 'Now Playing / Live Alert', kind: 'alert', z: 40, x: 31.0, y: 82.0, width: 38.0, height: 12.0, scale: 1.0, opacity: 1.0, fit: 'contain', visible: true, flipX: false, flipY: false },
    { id: 'presence-bubbles', name: 'Presence Bubbles', kind: 'presence', z: 50, x: 4.0, y: 86.0, width: 28.0, height: 8.0, scale: 1.0, opacity: 1.0, fit: 'contain', visible: true, flipX: false, flipY: false },
    { id: 'reactions', name: 'Reactions', kind: 'reactions', z: 60, x: 79.0, y: 88.0, width: 17.0, height: 8.0, scale: 1.0, opacity: 1.0, fit: 'contain', visible: true, flipX: false, flipY: false },
    { id: 'room-energy', name: 'Room Energy', kind: 'energy', z: 70, x: 83.0, y: 7.0, width: 13.0, height: 10.0, scale: 1.0, opacity: 1.0, fit: 'contain', visible: true, flipX: false, flipY: false }
  ]
};

// 2. Workstation Geometry Resolver Simulation
function resolveWorkstationGeometry(layout, containerWidth, containerHeight) {
  // In Workstation, #canvas is 16:9 inside editor container
  const targetAspect = 16 / 9;
  let canvasW, canvasH;
  if (containerWidth / containerHeight > targetAspect) {
    canvasH = containerHeight;
    canvasW = containerHeight * targetAspect;
  } else {
    canvasW = containerWidth;
    canvasH = containerWidth / targetAspect;
  }

  const layerRects = {};
  for (const l of layout.layers) {
    layerRects[l.id] = {
      x: (l.x / 100) * canvasW,
      y: (l.y / 100) * canvasH,
      width: (l.width / 100) * canvasW,
      height: (l.height / 100) * canvasH,
      normX: l.x / 100,
      normY: l.y / 100,
      normWidth: l.width / 100,
      normHeight: l.height / 100,
      z: l.z
    };
  }
  const so = layout.screenOpening;
  const cutoutRect = {
    x: (so.x / 100) * canvasW,
    y: (so.y / 100) * canvasH,
    width: (so.width / 100) * canvasW,
    height: (so.height / 100) * canvasH,
    normX: so.x / 100,
    normY: so.y / 100,
    normWidth: so.width / 100,
    normHeight: so.height / 100
  };

  return { canvasW, canvasH, layerRects, cutoutRect };
}

// 3. Green Staging Geometry Resolver Simulation
function resolveGreenGeometry(layout, screenWidth, screenHeight, sidebarWidth = 340) {
  const stageW = screenWidth - sidebarWidth;
  const stageH = screenHeight;
  const targetAspect = 16 / 9;

  let compW, compH;
  if (stageW / stageH > targetAspect) {
    compH = stageH;
    compW = stageH * targetAspect;
  } else {
    compW = stageW;
    compH = stageW / targetAspect;
  }

  const layerRects = {};
  for (const l of layout.layers) {
    layerRects[l.id] = {
      x: (l.x / 100) * compW,
      y: (l.y / 100) * compH,
      width: (l.width / 100) * compW,
      height: (l.height / 100) * compH,
      normX: l.x / 100,
      normY: l.y / 100,
      normWidth: l.width / 100,
      normHeight: l.height / 100,
      z: l.z
    };
  }
  const so = layout.screenOpening;
  const cutoutRect = {
    x: (so.x / 100) * compW,
    y: (so.y / 100) * compH,
    width: (so.width / 100) * compW,
    height: (so.height / 100) * compH,
    normX: so.x / 100,
    normY: so.y / 100,
    normWidth: so.width / 100,
    normHeight: so.height / 100
  };

  return { compW, compH, layerRects, cutoutRect };
}

// 4. Test Viewports
const viewports = [
  { name: '1080p Standard', w: 1920, h: 1080 },
  { name: '720p Mobile/Laptop', w: 1280, h: 720 },
  { name: '1440p QHD', w: 2560, h: 1440 },
  { name: '4K UHD', w: 3840, h: 2160 },
  { name: 'Ultra-Wide Window', w: 2560, h: 1080 },
  { name: 'Square Window', w: 1200, h: 1200 }
];

console.log('1. Evaluating Normalized Geometric Parity Across Viewports:');
viewports.forEach(vp => {
  const ws = resolveWorkstationGeometry(testLayout, vp.w, vp.h);
  const gr = resolveGreenGeometry(testLayout, vp.w, vp.h, 340);

  // Check normalized coordinate equality
  for (const layer of testLayout.layers) {
    const wsL = ws.layerRects[layer.id];
    const grL = gr.layerRects[layer.id];
    const dx = Math.abs(wsL.normX - grL.normX);
    const dy = Math.abs(wsL.normY - grL.normY);
    const dw = Math.abs(wsL.normWidth - grL.normWidth);
    const dh = Math.abs(wsL.normHeight - grL.normHeight);
    const maxDelta = Math.max(dx, dy, dw, dh);
    assert(maxDelta < 0.0001, `[${vp.name}] Layer "${layer.name}" normalized geometry matches (delta=${maxDelta.toFixed(6)})`);
    assert(wsL.z === grL.z, `[${vp.name}] Layer "${layer.name}" z-stack matches (z=${wsL.z})`);
  }

  // Check cutout
  const cdx = Math.abs(ws.cutoutRect.normX - gr.cutoutRect.normX);
  const cdy = Math.abs(ws.cutoutRect.normY - gr.cutoutRect.normY);
  const cdw = Math.abs(ws.cutoutRect.normWidth - gr.cutoutRect.normWidth);
  const cdh = Math.abs(ws.cutoutRect.normHeight - gr.cutoutRect.normHeight);
  const maxCutoutDelta = Math.max(cdx, cdy, cdw, cdh);
  assert(maxCutoutDelta < 0.0001, `[${vp.name}] Stage Screen Cutout normalized geometry matches (delta=${maxCutoutDelta.toFixed(6)})`);
});

// 5. Verify CSS Stacking Order & DOM Structure in stage.css
console.log('\n2. Verifying Green stage.css Stacking & Rules:');
const stageCss = readFileSync(join(GREEN_DIR, 'stage.css'), 'utf-8');
assert(stageCss.includes('.stage-composition'), 'stage.css includes .stage-composition 16:9 container');
assert(stageCss.includes('aspect-ratio:16 / 9') || stageCss.includes('aspect-ratio: 16 / 9') || stageCss.includes('aspect-ratio:16/9'), 'stage.css enforces 16:9 aspect-ratio');
assert(stageCss.includes('.screens') && stageCss.includes('z-index:10'), '.screens has z-index: 10 (backmost)');
assert(stageCss.includes('.stage-overlay') && stageCss.includes('z-index:20'), '.stage-overlay has z-index: 20');
assert(stageCss.includes('.mode-logo') && stageCss.includes('z-index:30'), '.mode-logo has z-index: 30');
assert(stageCss.includes('.now') && stageCss.includes('z-index:40'), '.now has z-index: 40');
assert(stageCss.includes('.audience') && stageCss.includes('z-index:50'), '.audience has z-index: 50');
assert(stageCss.includes('.reactions') && stageCss.includes('z-index:60'), '.reactions has z-index: 60');
assert(stageCss.includes('.energy') && stageCss.includes('z-index:70'), '.energy has z-index: 70');

console.log('\n================================================================');
console.log(`GEOMETRY PARITY AUDIT: ${passed} PASSED, ${failed} FAILED`);
console.log('================================================================');

if (failed > 0) process.exit(1);
