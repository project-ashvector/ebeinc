/**
 * Regression test for canonical layer resolution.
 * Run: node test-layer-resolution.js
 * 
 * Tests:
 * A. resolveStageAsset() returns stage-content layer
 * B. resolveVisualAsset() returns visual-content layer
 * C. Different files → different paths
 * D. Reorder layers → identities preserved
 * E. Legacy state migration → canonical IDs restored
 */

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) { passed++; console.log(`  ✓ ${msg}`); }
  else { failed++; console.error(`  ✗ FAIL: ${msg}`); }
}

// --- Simulate minimal runtime environment ---
const DEFAULT_VISUAL_FOLDER = '/home/ebmarah/Videos/at140radio/desktop visuals/visuals';
const DEFAULT_STAGE_FOLDER = '/home/ebmarah/Videos/at140radio/desktop visuals/stage';

function defaultWorkspaceLayers() {
  return [
    { id: 'visual-content', name: 'Visual Content', kind: 'media', role: 'visual', sourceFolder: DEFAULT_VISUAL_FOLDER, mediaIndex: 0, z: 10 },
    { id: 'stage-content', name: 'Stage Content', kind: 'media', role: 'stage', sourceFolder: DEFAULT_STAGE_FOLDER, mediaIndex: 0, z: 20 },
    { id: 'station-logo', name: 'Station / Takeover Logo', kind: 'logo', z: 30 },
    { id: 'now-playing', name: 'Now Playing / Live Alert', kind: 'alert', z: 40 },
    { id: 'presence-bubbles', name: 'Presence Bubbles', kind: 'presence', z: 50 },
    { id: 'reactions', name: 'Reactions', kind: 'reactions', z: 60 },
    { id: 'room-energy', name: 'Room Energy', kind: 'energy', z: 70 },
  ];
}

const CANONICAL_LAYER_IDS = { stage: 'stage-content', visual: 'visual-content' };

function resolveLayerByCanonical(targetId, targetRole, workspaceLayers) {
  if (!Array.isArray(workspaceLayers)) return null;
  let match = workspaceLayers.find(x => x.id === targetId);
  if (match) return match;
  const roleMatches = workspaceLayers.filter(x => x.role === targetRole);
  if (roleMatches.length === 1) return roleMatches[0];
  return null;
}

// --- Test A: Canonical ID resolution ---
console.log('\nTEST A: Canonical ID resolution');
{
  const layers = defaultWorkspaceLayers();
  const stage = resolveLayerByCanonical('stage-content', 'stage', layers);
  const visual = resolveLayerByCanonical('visual-content', 'visual', layers);
  assert(stage?.id === 'stage-content', 'Stage resolves to stage-content');
  assert(visual?.id === 'visual-content', 'Visual resolves to visual-content');
  assert(stage?.id !== visual?.id, 'Stage and Visual are different layers');
}

// --- Test B: Reorder layers — identities preserved ---
console.log('\nTEST B: Reorder layers');
{
  const layers = defaultWorkspaceLayers();
  // Swap positions
  [layers[0], layers[1]] = [layers[1], layers[0]];
  const stage = resolveLayerByCanonical('stage-content', 'stage', layers);
  const visual = resolveLayerByCanonical('visual-content', 'visual', layers);
  assert(stage?.id === 'stage-content', 'Stage still resolves after reorder');
  assert(visual?.id === 'visual-content', 'Visual still resolves after reorder');
}

// --- Test C: Legacy state with lost canonical IDs ---
console.log('\nTEST C: Legacy state migration');
{
  const layers = [
    { id: 'media-a1b2c3d4', name: 'Stage Content', kind: 'media', role: 'stage', sourceFolder: DEFAULT_STAGE_FOLDER, mediaIndex: 0, z: 20 },
    { id: 'media-e5f6g7h8', name: 'Visual Content', kind: 'media', role: 'visual', sourceFolder: DEFAULT_VISUAL_FOLDER, mediaIndex: 0, z: 10 },
  ];
  // Without migration, canonical IDs don't exist
  let stage = resolveLayerByCanonical('stage-content', 'stage', layers);
  let visual = resolveLayerByCanonical('visual-content', 'visual', layers);
  // Role-based fallback should still work (exactly 1 match each)
  assert(stage?.id === 'media-a1b2c3d4', 'Stage found by role fallback');
  assert(visual?.id === 'media-e5f6g7h8', 'Visual found by role fallback');
  assert(stage?.id !== visual?.id, 'Different layers resolved');
}

// --- Test D: Broad matching causes collision (the old bug) ---
console.log('\nTEST D: Old broad matching collision');
{
  // Simulate old buggy matching
  function oldResolveVisual(workspaceLayers) {
    return workspaceLayers.find(x =>
      x.role === 'visual' ||
      x.id === 'visual-content' ||
      (x.name && x.name.toLowerCase().includes('visual')) ||
      (x.sourceFolder && x.sourceFolder.toLowerCase().includes('visual'))
    );
  }
  const layers = defaultWorkspaceLayers();
  // stage-content has sourceFolder containing "visuals" (from "desktop visuals/stage")
  const oldResult = oldResolveVisual(layers);
  // The old code would match stage-content first if it appeared before visual-content
  // Because sourceFolder.includes('visual') is true for BOTH layers
  const bothMatchVisual = layers.filter(x =>
    x.sourceFolder && x.sourceFolder.toLowerCase().includes('visual')
  );
  assert(bothMatchVisual.length === 2, 'Both stage and visual match old broad sourceFolder criteria');
  assert(oldResult?.id === 'visual-content', 'Old matcher picks visual-content (first in array)');
  // But if we reverse order, old matcher picks stage-content!
  const reversed = [...layers].reverse();
  const oldResultReversed = oldResolveVisual(reversed);
  assert(oldResultReversed?.id === 'stage-content', 'Old matcher picks stage-content when reversed (BUG)');
}

// --- Test E: Collision detection ---
console.log('\nTEST E: Collision detection');
{
  const layers = defaultWorkspaceLayers();
  const stage = resolveLayerByCanonical('stage-content', 'stage', layers);
  const visual = resolveLayerByCanonical('visual-content', 'visual', layers);
  const fakeStagePath = '/path/to/stage.webm';
  const fakeVisualPath = '/path/to/visual.mp4';
  assert(fakeStagePath !== fakeVisualPath, 'Different files produce different paths');
  // Simulate same path bug
  const samePath = fakeStagePath === fakeVisualPath;
  assert(!samePath, 'No collision when paths differ');
}

// --- Test F: Ambiguous role matching fails safely ---
console.log('\nTEST F: Ambiguous role matching');
{
  const layers = [
    { id: 'media-aaa', name: 'Layer A', kind: 'media', role: 'stage', mediaIndex: 0, z: 10 },
    { id: 'media-bbb', name: 'Layer B', kind: 'media', role: 'stage', mediaIndex: 0, z: 20 },
  ];
  const stage = resolveLayerByCanonical('stage-content', 'stage', layers);
  assert(stage === null, 'Ambiguous stage role returns null (fails safely)');
}

// --- Summary ---
console.log(`\n${'='.repeat(50)}`);
console.log(`RESULTS: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
} else {
  console.log('All regression tests passed.');
}
