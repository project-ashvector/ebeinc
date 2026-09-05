export function mediaIdentity(item) {
  return item?.assetId || item?.routeId || item?.id || item?.fingerprint || '';
}

export function buildOrderedCycle(items, selectedId, compact) {
  const enabled = (Array.isArray(items) ? items : [])
    .filter(item => item && item.enabled !== false)
    .map(compact);
  if (!selectedId) return enabled;
  return [
    ...enabled.filter(item => mediaIdentity(item) === selectedId),
    ...enabled.filter(item => mediaIdentity(item) !== selectedId)
  ];
}

export function buildShuffleBag(items, previousId = '', random = Math.random) {
  const bag = [...(Array.isArray(items) ? items : [])];
  for (let i = bag.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [bag[i], bag[j]] = [bag[j], bag[i]];
  }
  if (bag.length > 1 && mediaIdentity(bag[0]) === previousId) [bag[0], bag[1]] = [bag[1], bag[0]];
  return bag;
}
