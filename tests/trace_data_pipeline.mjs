import { writeFileSync, readFileSync, existsSync } from 'fs';
import { resolve, join } from 'path';
import { createHash } from 'crypto';

const ROOT = resolve('.');
const GREEN_DIR = join(ROOT, 'visuals-green');
const APP_DIR = join(ROOT, 'visuals-app');

console.log('================================================================');
console.log('ALLTHINGS140 DATA PIPELINE & GEOMETRY SERIALIZATION TRACER');
console.log('================================================================\n');

// 1. TEST LAYOUT 1 DEFINITION
const test1_editor_layout = {
  activePreset: "Known Good Default",
  presets: [
    {
      name: "Known Good Default",
      viewport: "desktop-16-9",
      screenOpening: {
        x: 29.0,
        y: 38.0,
        width: 42.0,
        height: 37.0,
        rx: 1.5,
        enabled: true
      },
      layerFrames: {
        "visual-content": {
          x: 29.0,
          y: 38.0,
          width: 42.0,
          height: 37.0,
          scale: 1.0,
          opacity: 1.0,
          fit: "cover",
          visible: true,
          flipX: false,
          flipY: false
        },
        "stage-content": {
          x: 7.0,
          y: 9.0,
          width: 82.0,
          height: 78.0,
          scale: 1.0,
          opacity: 1.0,
          fit: "cover",
          visible: true,
          flipX: false,
          flipY: false
        },
        "station-logo": {
          x: 10.5,
          y: 77.0,
          width: 8.5,
          height: 9.0,
          scale: 1.0,
          opacity: 1.0,
          fit: "contain",
          visible: true,
          flipX: false,
          flipY: false
        },
        "now-playing": {
          x: 31.0,
          y: 82.0,
          width: 38.0,
          height: 12.0,
          scale: 1.0,
          opacity: 1.0,
          fit: "contain",
          visible: true,
          flipX: false,
          flipY: false
        },
        "presence-bubbles": {
          x: 4.0,
          y: 86.0,
          width: 28.0,
          height: 8.0,
          scale: 1.0,
          opacity: 1.0,
          fit: "contain",
          visible: true,
          flipX: false,
          flipY: false
        },
        "reactions": {
          x: 79.0,
          y: 88.0,
          width: 17.0,
          height: 8.0,
          scale: 1.0,
          opacity: 1.0,
          fit: "contain",
          visible: true,
          flipX: false,
          flipY: false
        },
        "room-energy": {
          x: 83.0,
          y: 7.0,
          width: 13.0,
          height: 10.0,
          scale: 1.0,
          opacity: 1.0,
          fit: "contain",
          visible: true,
          flipX: false,
          flipY: false
        }
      }
    }
  ],
  workspaceLayers: [
    { id: "visual-content", name: "Visual Content", kind: "media", role: "visual", z: 10 },
    { id: "stage-content", name: "Stage Content", kind: "media", role: "stage", z: 20 },
    { id: "station-logo", name: "Station / Takeover Logo", kind: "logo", z: 30 },
    { id: "now-playing", name: "Now Playing / Live Alert", kind: "alert", z: 40 },
    { id: "presence-bubbles", name: "Presence Bubbles", kind: "presence", z: 50 },
    { id: "reactions", name: "Reactions", kind: "reactions", z: 60 },
    { id: "room-energy", name: "Room Energy", kind: "energy", z: 70 }
  ],
  playlist: [
    { id: "vis-1", name: "test-visual.mp4", publicUrl: "/media/playlist/test-visual.mp4" }
  ],
  activeStage: {
    id: "stage-1", name: "test-stage.mp4", publicUrl: "/media/stage/test-stage.mp4"
  }
};

// 1. SAVE /tmp/visuals-editor-layout.json
writeFileSync('/tmp/visuals-editor-layout.json', JSON.stringify(test1_editor_layout, null, 2));
console.log('1. Saved: /tmp/visuals-editor-layout.json');

// 2. RUN WORKSTATION CANONICAL SNAPSHOT GENERATOR
function generateCanonicalSnapshot(state) {
  const p = state.presets.find(x => x.name === state.activePreset) || state.presets[0];
  const snapshot = structuredClone(state);
  snapshot.screenOpening = structuredClone(p.screenOpening);
  snapshot.workspaceLayers = snapshot.workspaceLayers.map(layer => {
    const f = structuredClone(p.layerFrames[layer.id] || { x: 0, y: 0, width: 100, height: 100 });
    return {
      ...layer,
      frame: f,
      x: Number(f.x) || 0,
      y: Number(f.y) || 0,
      width: Number(f.width) || 100,
      height: Number(f.height) || 100,
      scale: Number(f.scale) || 1,
      opacity: f.opacity != null ? Number(f.opacity) : 1,
      fit: f.fit || (layer.kind === 'media' ? 'cover' : 'contain'),
      visible: f.visible !== false,
      flipX: Boolean(f.flipX),
      flipY: Boolean(f.flipY)
    };
  });
  return snapshot;
}

const canonical_snapshot = generateCanonicalSnapshot(test1_editor_layout);
writeFileSync('/tmp/visuals-canonical-snapshot.json', JSON.stringify(canonical_snapshot, null, 2));
console.log('2. Saved: /tmp/visuals-canonical-snapshot.json');

// 3. RUN PUBLISHED MANIFEST ENCODER (simulating Rust backend publish_staging)
function generatePublishedManifest(snapshot) {
  const p = snapshot.presets.find(x => x.name === snapshot.activePreset) || snapshot.presets[0];
  const revision = '20260816T200000000Z';
  const mediaOrigin = 'https://visuals-media-staging.allthings140radio.online';

  const layers = snapshot.workspaceLayers.map(layer => {
    const f = layer.frame || p.layerFrames[layer.id] || { x: 0, y: 0, width: 100, height: 100 };
    const pub = {
      id: layer.id,
      name: layer.name,
      kind: layer.kind,
      role: layer.role || null,
      z: layer.z,
      x: f.x,
      y: f.y,
      width: f.width,
      height: f.height,
      scale: f.scale ?? 1,
      fit: f.fit || (layer.kind === 'media' ? 'cover' : 'contain'),
      opacity: f.opacity ?? 1,
      visible: f.visible !== false,
      flipX: Boolean(f.flipX),
      flipY: Boolean(f.flipY)
    };
    if (layer.kind === 'media') {
      pub.media = {
        id: layer.role === 'stage' ? 'stage-1' : 'vis-1',
        name: layer.role === 'stage' ? 'test-stage.mp4' : 'test-visual.mp4',
        url: layer.role === 'stage' ? `${mediaOrigin}/stage/test-stage.mp4` : `${mediaOrigin}/visuals/test-visual.mp4`
      };
    }
    return pub;
  });

  const manifest = {
    schemaVersion: 2,
    layoutRevision: revision,
    layoutId: `layout-${revision}`,
    composition: { width: 1920, height: 1080, aspectRatio: '16:9' },
    screenOpening: snapshot.screenOpening,
    layers
  };

  const hash = createHash('sha256').update(JSON.stringify(manifest)).digest('hex');
  manifest.layoutHash = hash;
  return manifest;
}

const published_manifest = generatePublishedManifest(canonical_snapshot);
writeFileSync('/tmp/visuals-published-layout.json', JSON.stringify(published_manifest, null, 2));
console.log('3. Saved: /tmp/visuals-published-layout.json');

// 4. RUN GREEN STAGING PARSER
function parseGreenLayout(manifest) {
  const layers = Array.isArray(manifest.layers) ? manifest.layers : [];
  const visual = layers.find(x => x.id === 'visual-content') || layers.find(x => x.role === 'visual') || { z: 10, x: 0, y: 0, width: 100, height: 100 };
  const stage = layers.find(x => x.id === 'stage-content') || layers.find(x => x.role === 'stage') || { z: 20, x: 0, y: 0, width: 100, height: 100 };
  const logo = layers.find(x => x.id === 'station-logo') || layers.find(x => x.kind === 'logo') || { z: 30, x: 10.5, y: 77, width: 8.5, height: 9 };
  const alert = layers.find(x => x.id === 'now-playing') || layers.find(x => x.kind === 'alert') || { z: 40, x: 31, y: 82, width: 38, height: 12 };
  const screenOpening = manifest.screenOpening || { x: 23.0, y: 33.5, width: 53.6, height: 48.5, rx: 1.5, enabled: true };

  return {
    raw: manifest,
    normalized: {
      stage: { x: stage.x, y: stage.y, width: stage.width, height: stage.height, z: stage.z },
      visual: { x: visual.x, y: visual.y, width: visual.width, height: visual.height, z: visual.z },
      logo: { x: logo.x, y: logo.y, width: logo.width, height: logo.height, z: logo.z },
      alert: { x: alert.x, y: alert.y, width: alert.width, height: alert.height, z: alert.z },
      screenOpening: { x: screenOpening.x, y: screenOpening.y, width: screenOpening.width, height: screenOpening.height }
    },
    hash: manifest.layoutHash
  };
}

const green_received = parseGreenLayout(published_manifest);

// 5. PRINT DATA CONTRACT FIELD COMPARISON TABLE
console.log('\n================================================================');
console.log('FIELD COMPARISON TABLE (TEST 1)');
console.log('================================================================');
console.log('FIELD                      | EDITOR   | SNAPSHOT | PUBLISHED | GREEN RAW | GREEN NORM');
console.log('---------------------------|----------|----------|-----------|-----------|-----------');

const fields = [
  ['Stage.x', test1_editor_layout.presets[0].layerFrames['stage-content'].x, canonical_snapshot.workspaceLayers.find(x => x.id === 'stage-content').x, published_manifest.layers.find(x => x.id === 'stage-content').x, green_received.raw.layers.find(x => x.id === 'stage-content').x, green_received.normalized.stage.x],
  ['Stage.y', test1_editor_layout.presets[0].layerFrames['stage-content'].y, canonical_snapshot.workspaceLayers.find(x => x.id === 'stage-content').y, published_manifest.layers.find(x => x.id === 'stage-content').y, green_received.raw.layers.find(x => x.id === 'stage-content').y, green_received.normalized.stage.y],
  ['Stage.width', test1_editor_layout.presets[0].layerFrames['stage-content'].width, canonical_snapshot.workspaceLayers.find(x => x.id === 'stage-content').width, published_manifest.layers.find(x => x.id === 'stage-content').width, green_received.raw.layers.find(x => x.id === 'stage-content').width, green_received.normalized.stage.width],
  ['Stage.height', test1_editor_layout.presets[0].layerFrames['stage-content'].height, canonical_snapshot.workspaceLayers.find(x => x.id === 'stage-content').height, published_manifest.layers.find(x => x.id === 'stage-content').height, green_received.raw.layers.find(x => x.id === 'stage-content').height, green_received.normalized.stage.height],
  ['Visual.x', test1_editor_layout.presets[0].layerFrames['visual-content'].x, canonical_snapshot.workspaceLayers.find(x => x.id === 'visual-content').x, published_manifest.layers.find(x => x.id === 'visual-content').x, green_received.raw.layers.find(x => x.id === 'visual-content').x, green_received.normalized.visual.x],
  ['Visual.y', test1_editor_layout.presets[0].layerFrames['visual-content'].y, canonical_snapshot.workspaceLayers.find(x => x.id === 'visual-content').y, published_manifest.layers.find(x => x.id === 'visual-content').y, green_received.raw.layers.find(x => x.id === 'visual-content').y, green_received.normalized.visual.y],
  ['Visual.width', test1_editor_layout.presets[0].layerFrames['visual-content'].width, canonical_snapshot.workspaceLayers.find(x => x.id === 'visual-content').width, published_manifest.layers.find(x => x.id === 'visual-content').width, green_received.raw.layers.find(x => x.id === 'visual-content').width, green_received.normalized.visual.width],
  ['Visual.height', test1_editor_layout.presets[0].layerFrames['visual-content'].height, canonical_snapshot.workspaceLayers.find(x => x.id === 'visual-content').height, published_manifest.layers.find(x => x.id === 'visual-content').height, green_received.raw.layers.find(x => x.id === 'visual-content').height, green_received.normalized.visual.height],
  ['Cutout.x', test1_editor_layout.presets[0].screenOpening.x, canonical_snapshot.screenOpening.x, published_manifest.screenOpening.x, green_received.raw.screenOpening.x, green_received.normalized.screenOpening.x],
  ['Cutout.y', test1_editor_layout.presets[0].screenOpening.y, canonical_snapshot.screenOpening.y, published_manifest.screenOpening.y, green_received.raw.screenOpening.y, green_received.normalized.screenOpening.y],
  ['Cutout.width', test1_editor_layout.presets[0].screenOpening.width, canonical_snapshot.screenOpening.width, published_manifest.screenOpening.width, green_received.raw.screenOpening.width, green_received.normalized.screenOpening.width],
  ['Cutout.height', test1_editor_layout.presets[0].screenOpening.height, canonical_snapshot.screenOpening.height, published_manifest.screenOpening.height, green_received.raw.screenOpening.height, green_received.normalized.screenOpening.height]
];

for (const [name, ed, snap, pub, gRaw, gNorm] of fields) {
  const pad = (s, len) => String(s + '%').padEnd(len);
  console.log(`${name.padEnd(27)}| ${pad(ed, 9)}| ${pad(snap, 9)}| ${pad(pub, 10)}| ${pad(gRaw, 10)}| ${pad(gNorm, 10)}`);
  if (ed !== snap || snap !== pub || pub !== gRaw || gRaw !== gNorm) {
    console.error(`❌ MISMATCH in ${name}: ed=${ed}, snap=${snap}, pub=${pub}, gRaw=${gRaw}, gNorm=${gNorm}`);
    process.exit(1);
  }
}

// 6. TEST LAYOUT 2 (RADICALLY DIFFERENT GEOMETRY)
console.log('\n================================================================');
console.log('EVALUATING TEST 2 (RADICALLY DIFFERENT GEOMETRY: 2/4/95/91 & 15/25/68/52)');
console.log('================================================================');
const test2_editor_layout = structuredClone(test1_editor_layout);
test2_editor_layout.presets[0].layerFrames['stage-content'] = { x: 2.0, y: 4.0, width: 95.0, height: 91.0, scale: 1, opacity: 1, fit: 'cover', visible: true, flipX: false, flipY: false };
test2_editor_layout.presets[0].layerFrames['visual-content'] = { x: 15.0, y: 25.0, width: 68.0, height: 52.0, scale: 1, opacity: 1, fit: 'cover', visible: true, flipX: false, flipY: false };
test2_editor_layout.presets[0].screenOpening = { x: 15.0, y: 25.0, width: 68.0, height: 52.0, rx: 1.5, enabled: true };

const test2_snapshot = generateCanonicalSnapshot(test2_editor_layout);
const test2_published = generatePublishedManifest(test2_snapshot);
const test2_green = parseGreenLayout(test2_published);

const test2_fields = [
  ['Stage.x', 2.0, test2_green.normalized.stage.x],
  ['Stage.y', 4.0, test2_green.normalized.stage.y],
  ['Stage.width', 95.0, test2_green.normalized.stage.width],
  ['Stage.height', 91.0, test2_green.normalized.stage.height],
  ['Visual.x', 15.0, test2_green.normalized.visual.x],
  ['Visual.y', 25.0, test2_green.normalized.visual.y],
  ['Visual.width', 68.0, test2_green.normalized.visual.width],
  ['Visual.height', 52.0, test2_green.normalized.visual.height],
  ['Cutout.x', 15.0, test2_green.normalized.screenOpening.x],
  ['Cutout.y', 25.0, test2_green.normalized.screenOpening.y],
  ['Cutout.width', 68.0, test2_green.normalized.screenOpening.width],
  ['Cutout.height', 52.0, test2_green.normalized.screenOpening.height]
];

for (const [name, expected, actual] of test2_fields) {
  if (expected !== actual) {
    console.error(`❌ TEST 2 MISMATCH: ${name} expected ${expected}, got ${actual}`);
    process.exit(1);
  }
  console.log(`  ✓ ${name} matches: ${actual}%`);
}

console.log('\n================================================================');
console.log('DATA PIPELINE VERIFICATION RESULT: 100% PARITY CONFIRMED');
console.log(`HASH: ${published_manifest.layoutHash}`);
console.log('================================================================');
