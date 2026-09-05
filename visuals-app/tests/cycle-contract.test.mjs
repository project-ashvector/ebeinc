import test from 'node:test';
import assert from 'node:assert/strict';
import { buildShuffleBag, mediaIdentity } from '../src/cycle-contract.js';

test('two full 95-item shuffle-bag rounds contain every item exactly once', () => {
  const items = Array.from({ length: 95 }, (_, i) => ({ id: `visual-${i + 1}` }));
  let seed = 140;
  const random = () => ((seed = (seed * 48271) % 0x7fffffff) / 0x7fffffff);
  const first = buildShuffleBag(items, '', random);
  const second = buildShuffleBag(items, mediaIdentity(first.at(-1)), random);
  assert.equal(new Set(first.map(mediaIdentity)).size, 95);
  assert.equal(new Set(second.map(mediaIdentity)).size, 95);
  assert.deepEqual(new Set(first.map(mediaIdentity)), new Set(items.map(mediaIdentity)));
  assert.deepEqual(new Set(second.map(mediaIdentity)), new Set(items.map(mediaIdentity)));
  assert.notEqual(mediaIdentity(second[0]), mediaIdentity(first.at(-1)));
});

test('shuffle bag does not mutate the source library', () => {
  const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
  const before = JSON.stringify(items);
  buildShuffleBag(items, '', () => 0.25);
  assert.equal(JSON.stringify(items), before);
});
