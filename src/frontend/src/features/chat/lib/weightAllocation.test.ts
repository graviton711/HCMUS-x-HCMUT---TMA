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
      .toEqual([15]);
  });

  it('renormalizes after an item is removed and divides zero weights evenly', () => {
    expect([...normalizeWeights([
      { id: 'b', weight_percent: 30 },
      { id: 'c', weight_percent: 20 },
    ]).values()]).toEqual([60, 40]);
    expect([...normalizeWeights([{ id: 'a' }, { id: 'b' }, { id: 'c' }]).values()])
      .toEqual([34, 33, 33]);
  });

  it('preserves confirmed values across edits and still accepts edits to confirmed items', () => {
    const items = [
      { id: 'a', weight_percent: 50 },
      { id: 'b', weight_percent: 30 },
      { id: 'c', weight_percent: 20 },
    ];
    const first = reallocateWeight(items, 'a', 40)!;
    const updated = items.map((item) => ({ ...item, weight_percent: first.get(item.id) }));
    const second = reallocateWeight(updated, 'b', 35, new Set(['a']))!;
    expect([...second.values()]).toEqual([40, 35, 25]);
    const final = reallocateWeight(
      items.map((item) => ({ ...item, weight_percent: second.get(item.id) })),
      'a', 20, new Set(['a', 'b']),
    )!;
    expect([...final.values()]).toEqual([20, 35, 45]);
  });

  it('keeps under- and over-allocated drafts once every item is confirmed', () => {
    const items = [{ id: 'a', weight_percent: 60 }, { id: 'b', weight_percent: 40 }];
    const confirmed = new Set(['a', 'b']);
    expect([...reallocateWeight(items, 'b', 30, confirmed)!.values()]).toEqual([60, 30]);
    expect([...reallocateWeight(items, 'b', 50, confirmed)!.values()]).toEqual([60, 50]);
    expect([...confirmed]).toEqual(['a', 'b']);
    expect(items.map((item) => item.weight_percent)).toEqual([60, 40]);
  });

  it('never allocates negative weights when confirmed values exceed the budget', () => {
    const result = reallocateWeight([
      { id: 'a', weight_percent: 70 },
      { id: 'b', weight_percent: 20 },
      { id: 'c', weight_percent: 10 },
    ], 'b', 40, new Set(['a']))!;
    expect([...result.values()]).toEqual([70, 40, 10]);
  });

  it('normalizes only automatic items after removal and handles zero remaining budget', () => {
    const items = [
      { id: 'a', weight_percent: 40 },
      { id: 'b', weight_percent: 20 },
      { id: 'c', weight_percent: 10 },
    ];
    expect([...normalizeWeights(items, new Set(['a', 'removed'])).values()]).toEqual([40, 40, 20]);
    expect([...normalizeWeights(items.slice(0, 1), new Set(['a'])).values()]).toEqual([40]);
    expect([...normalizeWeights([
      { id: 'a', weight_percent: 100 },
      { id: 'b', weight_percent: 30 },
    ], new Set(['a'])).values()]).toEqual([100, 0]);
    expect([...normalizeWeights([
      { id: 'a', weight_percent: 41 },
      { id: 'b', weight_percent: 0 },
      { id: 'c', weight_percent: 0 },
    ], new Set(['a'])).values()]).toEqual([41, 30, 29]);
  });
});
