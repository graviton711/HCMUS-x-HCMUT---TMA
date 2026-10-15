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
): Map<string, number> | null {
  if (!Number.isInteger(proposed) || proposed < 0 || proposed > 100) return null;
  if (items.length === 0 || !items.some((item) => item.id === changedId)) return null;
  if (items.length === 1) return new Map([[items[0].id, 100]]);

  const changedIndex = items.findIndex((item) => item.id === changedId);
  const others = items.filter((_, index) => index !== changedIndex);
  const current = others.map((item) => {
    const value = item.weight_percent;
    return Number.isInteger(value) && (value ?? -1) >= 0 ? value as number : 0;
  });
  const remainder = distribute(others, 100 - proposed, current);
  return new Map([[changedId, proposed], ...remainder.entries()]);
}

export function normalizeWeights(items: WeightedItem[]): Map<string, number> {
  if (items.length === 0) return new Map();
  if (items.length === 1) return new Map([[items[0].id, 100]]);
  const basis = items.map((item) => {
    const value = item.weight_percent;
    return Number.isInteger(value) && (value ?? -1) >= 0 ? value as number : 0;
  });
  return distribute(items, 100, basis);
}
