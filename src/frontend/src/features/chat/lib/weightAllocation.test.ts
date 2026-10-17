import { describe, expect, it } from 'vitest';
import { allocateByPriority, normalizeWeights, reallocateWeight } from './weightAllocation';

describe('reallocateWeight', () => {
  it('redistributes equally when current weights are equal', () => {
    const result = reallocateWeight([
      { id: 'a', weight_percent: 25 },
      { id: 'b', weight_percent: 25 },
      { id: 'c', weight_percent: 25 },
      { id: 'd', weight_percent: 25 },
    ], 'a', 40);
    expect([...result!.values()]).toEqual([40, 20, 20, 20]);
  });

  it('preserves the prior ratio and uses stable largest-remainder ties', () => {
    const result = reallocateWeight([
      { id: 'a', weight_percent: 50 },
      { id: 'b', weight_percent: 30 },
      { id: 'c', weight_percent: 20 },
    ], 'a', 60);
    expect([...result!.values()]).toEqual([60, 24, 16]);

    const rounded = reallocateWeight([
      { id: 'a', weight_percent: 25 },
      { id: 'b', weight_percent: 25 },
      { id: 'c', weight_percent: 25 },
      { id: 'd', weight_percent: 25 },
    ], 'a', 99);
    expect([...rounded!.values()]).toEqual([99, 1, 0, 0]);
  });

  it('handles zero, one, 100, and invalid values', () => {
    const items = [{ id: 'a', weight_percent: 0 }, { id: 'b', weight_percent: 0 }];
    expect([...reallocateWeight(items, 'a', 0)!.values()]).toEqual([0, 100]);
    expect([...reallocateWeight(items, 'a', 100)!.values()]).toEqual([100, 0]);
    expect(reallocateWeight(items, 'a', 101)).toBeNull();
    expect([...reallocateWeight([{ id: 'only', weight_percent: 0 }], 'only', 15)!.values()])
      .toEqual([100]);
  });

  it('renormalizes after an item is removed and divides zero weights evenly', () => {
    expect([...normalizeWeights([
      { id: 'b', weight_percent: 30 },
      { id: 'c', weight_percent: 20 },
    ]).values()]).toEqual([60, 40]);
    expect([...normalizeWeights([{ id: 'a' }, { id: 'b' }, { id: 'c' }]).values()])
      .toEqual([34, 33, 33]);
  });
});

describe('allocateByPriority', () => {
  it('materializes the 1:3:9 ladder for one item per level', () => {
    const result = allocateByPriority([
      { id: 'a', priority: 'high' },
      { id: 'b', priority: 'medium' },
      { id: 'c', priority: 'low' },
    ]);
    expect([...result.values()]).toEqual([69, 23, 8]);
  });

  it('keeps group totals monotone and members equal within +/-1', () => {
    const result = allocateByPriority([
      { id: 'h1', priority: 'high' },
      { id: 'h2', priority: 'high' },
      { id: 'l1', priority: 'low' },
      { id: 'l2', priority: 'low' },
      { id: 'l3', priority: 'low' },
    ]);
    const values = [...result.values()];
    expect(values.reduce((sum, value) => sum + value, 0)).toBe(100);
    const highTotal = (result.get('h1') ?? 0) + (result.get('h2') ?? 0);
    const lowTotal = (result.get('l1') ?? 0) + (result.get('l2') ?? 0) + (result.get('l3') ?? 0);
    expect(highTotal).toBeGreaterThan(lowTotal);
    expect(Math.abs(result.get('h1')! - result.get('h2')!)).toBeLessThanOrEqual(1);
    expect(Math.abs(result.get('l1')! - result.get('l2')!)).toBeLessThanOrEqual(1);
  });

  it('defaults missing priorities to medium and handles degenerate lists', () => {
    // missing level defaults to medium: 9 vs 3 -> 75/25
    expect([...allocateByPriority([
      { id: 'a', priority: 'high' },
      { id: 'b' },
    ]).values()]).toEqual([75, 25]);
    expect([...allocateByPriority([{ id: 'single', priority: 'low' }]).values()])
      .toEqual([100]);
    // same level everywhere -> equal split (legacy behavior)
    expect([...allocateByPriority([
      { id: 'a', priority: 'medium' },
      { id: 'b', priority: 'medium' },
    ]).values()]).toEqual([50, 50]);
    // no priorities at all -> empty map (weight-based allocation rule applies)
    expect(allocateByPriority([{ id: 'a' }, { id: 'b' }]).size).toBe(0);
  });
});
