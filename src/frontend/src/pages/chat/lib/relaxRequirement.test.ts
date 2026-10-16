import { describe, expect, it } from 'vitest';

import type { CurrentRequirement } from '../../../shared/api';
import { relaxRequirement } from './relaxRequirement';

const base: CurrentRequirement = {
  id: 'req_1',
  raw_text: 'Đi Đà Lạt',
  travelers: 2,
  missing: [],
  conditions: [
    { id: 'h1', field: 'destination', operator: 'contains', value: 'Đà Lạt', strength: 'hard', quote: 'Đà Lạt' },
    { id: 'h2', field: 'duration_days', operator: 'eq', value: 3, strength: 'hard', quote: '3 ngày' },
  ],
  alternatives: [
    {
      id: 'b1',
      label: 'Nhánh A',
      conditions: [
        { id: 'h3', field: 'date_from', operator: 'eq', value: '2026-10-19', strength: 'hard', quote: '19/10' },
      ],
    },
    {
      id: 'b2',
      label: 'Nhánh B',
      conditions: [
        { id: 'h2', field: 'duration_days', operator: 'eq', value: 3, strength: 'hard', quote: '3 ngày' },
        { id: 'h4', field: 'budget_max', operator: 'lte', value: 5000000, strength: 'hard', quote: '5 triệu' },
      ],
    },
  ],
  assumptions: [
    {
      id: 'a1',
      kind: 'date_window',
      label: 'Ngày đi',
      quote: '19/10',
      date_from: '2026-10-19',
      date_to: '2026-10-19',
      condition_ids: ['h3', 'h3b'],
      timezone: 'Asia/Ho_Chi_Minh',
    },
  ],
};

describe('relaxRequirement', () => {
  it('drops the condition everywhere and prunes dangling branches and assumptions', () => {
    const relaxed = relaxRequirement(base, 'h2');
    expect(relaxed.conditions.map((c) => c.id)).toEqual(['h1']);
    expect(relaxed.alternatives?.map((b) => b.id)).toEqual(['b1', 'b2']);
    expect(relaxed.alternatives?.find((b) => b.id === 'b2')?.conditions.map((c) => c.id)).toEqual([
      'h4',
    ]);
    // a1 links h3b, which is not among the survivors -> dropped.
    expect(relaxed.assumptions ?? []).toEqual([]);
  });

  it('drops branches left empty', () => {
    const relaxed = relaxRequirement(base, 'h3');
    expect(relaxed.alternatives?.map((b) => b.id)).toEqual(['b2']);
  });

  it('keeps intact assumptions that still link surviving pairs', () => {
    const withPair: CurrentRequirement = {
      ...base,
      assumptions: [
        {
          id: 'a2',
          kind: 'date_window',
          label: 'Ngày đi',
          quote: '19/10',
          date_from: '2026-10-19',
          date_to: '2026-10-19',
          condition_ids: ['h1', 'h2'],
          timezone: 'Asia/Ho_Chi_Minh',
        },
      ],
    };
    const relaxed = relaxRequirement(withPair, 'h4');
    expect(relaxed.assumptions?.map((a) => a.id)).toEqual(['a2']);
  });
});
