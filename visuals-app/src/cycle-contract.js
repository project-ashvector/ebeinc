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
