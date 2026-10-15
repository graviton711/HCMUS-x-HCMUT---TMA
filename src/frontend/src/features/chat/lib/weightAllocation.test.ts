import { describe, expect, it } from 'vitest';
import { normalizeWeights, reallocateWeight } from './weightAllocation';

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
