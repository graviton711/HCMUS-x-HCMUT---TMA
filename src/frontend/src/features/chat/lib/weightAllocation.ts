export interface WeightedItem {
  id: string;
  weight_percent?: number | null;
}

export type PriorityLevel = 'low' | 'medium' | 'high';

export interface PriorityItem {
  id: string;
  priority?: PriorityLevel | null;
}

const PRIORITY_BASIS: Record<PriorityLevel, number> = { low: 1, medium: 3, high: 9 };
const LEVEL_ORDER: PriorityLevel[] = ['high', 'medium', 'low'];
const DEFAULT_LEVEL: PriorityLevel = 'medium';

/** Largest-remainder integer apportionment of `total` proportional to `basis`. */
function largestRemainder(total: number, basis: number[]): number[] {
  const basisTotal = basis.reduce((sum, value) => sum + value, 0);
  const exact = basis.map((value) =>
    basisTotal > 0 ? value * total / basisTotal : total / basis.length,
  );
  const allocated = exact.map((value) => Math.floor(value));
  let remainder = total - allocated.reduce((sum, value) => sum + value, 0);
  const order = exact
    .map((value, index) => ({ index, fraction: value - allocated[index] }))
    .sort((left, right) => right.fraction - left.fraction || left.index - right.index);
  for (const { index } of order) {
    if (remainder <= 0) break;
    allocated[index] += 1;
    remainder -= 1;
  }
  return allocated;
}

/**
 * Priority levels -> integer weights summing to 100 (1:3:9 ladder, one of each
 * level materializes to 69/23/8). Missing levels default to medium. Group
 * totals are apportioned first (ties favor higher levels, kept monotone), then
 * each group splits equally inside (+/-1 between members). Empty result means
 * no item carried a priority and weight-based allocation applies.
 */
export function allocateByPriority(items: PriorityItem[]): Map<string, number> {
  if (items.length === 0) return new Map();
  if (!items.some((item) => item.priority)) return new Map();
  if (items.length === 1) return new Map([[items[0].id, 100]]);
  const weights = new Map<string, number>();
  const groups = new Map<PriorityLevel, string[]>();
  for (const level of LEVEL_ORDER) groups.set(level, []);
  for (const item of items) groups.get(item.priority ?? DEFAULT_LEVEL)!.push(item.id);
  const active = LEVEL_ORDER.filter((level) => groups.get(level)!.length > 0);
  const totals = largestRemainder(
    100,
    active.map((level) => groups.get(level)!.length * PRIORITY_BASIS[level]),
  );
  for (let index = 0; index < active.length - 1; index += 1) {
    while (totals[index + 1] > totals[index] && totals[index + 1] > 0) {
      totals[index + 1] -= 1;
      totals[index] += 1;
    }
  }
  active.forEach((level, index) => {
    const members = groups.get(level)!;
    largestRemainder(totals[index], members.map(() => PRIORITY_BASIS[level])).forEach(
      (weight, position) => weights.set(members[position], weight),
    );
  });
  return weights;
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
