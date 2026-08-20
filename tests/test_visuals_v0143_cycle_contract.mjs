import assert from 'node:assert/strict';
import { buildOrderedCycle, mediaIdentity } from '../visuals-app/src/cycle-contract.js';

let passed = 0;
const test = (name, fn) => { fn(); passed++; console.log(`✓ ${name}`); };
const compact = item => ({ id: mediaIdentity(item), name: item.name, enabled: item.enabled !== false });

test('complete enabled Visual list survives cycle serialization', () => {
  const items = Array.from({ length: 57 }, (_, i) => ({ routeId: `visual-${i}`, name: `${i}.mp4`, enabled: true }));
  assert.equal(buildOrderedCycle(items, '', compact).length, 57);
});

test('disabled and malformed entries do not enter the cycle', () => {
  const result = buildOrderedCycle([null, { id: 'a', enabled: false }, { id: 'b', enabled: true }], '', compact);
  assert.deepEqual(result.map(x => x.id), ['b']);
});

test('selected visual becomes deterministic first item without losing peers', () => {
  const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
  assert.deepEqual(buildOrderedCycle(items, 'b', compact).map(x => x.id), ['b', 'a', 'c']);
});

test('identity remains independent from duplicate filenames', () => {
  const items = [{ routeId: 'path-a', name: 'same.mp4' }, { routeId: 'path-b', name: 'same.mp4' }];
  assert.deepEqual(buildOrderedCycle(items, '', compact).map(x => x.id), ['path-a', 'path-b']);
});

console.log(`${passed}/${passed} v0.1.43 cycle-contract checks passed`);
