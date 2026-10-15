export interface WeightedItem {
  id: string;
  weight_percent?: number | null;
}

function distribute(
  items: WeightedItem[],
  total: number,
  basis: number[],
): Map<string, number> {
  const basisTotal = basis.reduce((sum, value) => sum + value, 0);
  const exact = basis.map((value) => basisTotal > 0
    ? total * value / basisTotal
    : total / items.length);
  const allocated = exact.map(Math.floor);
  let remainder = total - allocated.reduce((sum, value) => sum + value, 0);
  const order = exact.map((value, index) => ({ index, fraction: value - allocated[index] }))
    .sort((left, right) => right.fraction - left.fraction || left.index - right.index);
  for (const { index } of order) {
    if (remainder <= 0) break;
    allocated[index] += 1;
    remainder -= 1;
  }
  return new Map(items.map((item, index) => [item.id, allocated[index]]));
}

export function reallocateWeight(
  items: WeightedItem[],
  changedId: string,
  proposed: number,
  confirmedIds: ReadonlySet<string> = new Set(),
): Map<string, number> | null {
  if (!Number.isInteger(proposed) || proposed < 0 || proposed > 100) return null;
  if (items.length === 0 || !items.some((item) => item.id === changedId)) return null;
  return normalizeWeights(
    items.map((item) => item.id === changedId ? { ...item, weight_percent: proposed } : item),
    new Set([...confirmedIds, changedId]),
  );
}

export function normalizeWeights(
  items: WeightedItem[],
  confirmedIds: ReadonlySet<string> = new Set(),
): Map<string, number> {
  if (items.length === 0) return new Map();
  const current = new Map(items.map((item) => {
    const value = item.weight_percent;
    return [item.id, Number.isInteger(value) && (value ?? -1) >= 0 ? value as number : 0];
  }));
  const remaining = 100 - items.reduce((sum, item) =>
    sum + (confirmedIds.has(item.id) ? current.get(item.id)! : 0), 0);
  const automatic = items.filter((item) => !confirmedIds.has(item.id));
  // Invalid totals remain editable drafts; never adjust a confirmed value or allocate negatives.
  if (automatic.length === 0 || remaining < 0) return current;
  const allocated = distribute(automatic, remaining, automatic.map((item) => current.get(item.id)!));
  return new Map(items.map((item) => [item.id, allocated.get(item.id) ?? current.get(item.id)!]));
}
