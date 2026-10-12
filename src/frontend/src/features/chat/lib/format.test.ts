import { describe, expect, it } from 'vitest';
import type { CurrentComparison } from '../../../shared/api';
import {
  conditionText,
  display,
  failedDetailsForOffer,
  fieldLabel,
  mostFailedField,
  operatorLabel,
} from './format';

function comparison(): CurrentComparison {
  return {
    id: 'cmp_test',
    requirement: {
      id: 'req_test',
      conditions: [
        { id: 'h1', field: 'destination', operator: 'contains', value: 'Đà Lạt', strength: 'hard', quote: '' },
        { id: 'h2', field: 'budget_max', operator: 'lte', value: 8000000, strength: 'hard', quote: '' },
      ],
      missing: [],
      raw_text: 'Đà Lạt',
      travelers: 1,
    },
    ranked: [{ tour_id: 'tour_a', offer_id: 'offer_a', score: 0 }],
    near_miss: [{ tour_id: 'tour_b', offer_id: 'offer_b', score: 0.5 }],
    tour_snapshots: [],
    evaluations: [
      { offer_id: 'offer_b', condition_id: 'h1', state: 'pass', quote: '', reason: '', reason_code: '' },
      { offer_id: 'offer_b', condition_id: 'h2', state: 'fail', quote: '', reason: '', reason_code: 'PRICE_OVER_BUDGET' },
      { offer_id: 'offer_c', condition_id: 'h1', state: 'fail', quote: '', reason: '', reason_code: 'DESTINATION_MISMATCH' },
      { offer_id: 'offer_c', condition_id: 'h2', state: 'fail', quote: '', reason: '', reason_code: 'PRICE_OVER_BUDGET' },
    ],
    analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
    candidates_considered: 3,
  };
}

describe('chat evaluation helpers', () => {
  it('counts the most failed hard condition for one-tap relax', () => {
    expect(mostFailedField(comparison())).toEqual({ field: 'budget_max', count: 2 });
  });

  it('returns null when nothing failed', () => {
    const clean = comparison();
    clean.evaluations = clean.evaluations.filter((item) => item.state !== 'fail');
    expect(mostFailedField(clean)).toBeNull();
  });

  it('joins failed evaluations with their conditions', () => {
    const failed = failedDetailsForOffer(comparison(), 'offer_b');
    expect(failed).toHaveLength(1);
    expect(failed[0].condition?.field).toBe('budget_max');
    expect(failed[0].evaluation.reason_code).toBe('PRICE_OVER_BUDGET');
  });

  it('maps backend codes to language instead of leaking them', () => {
    const t = (vi: string, en: string) => `${vi}|${en}`;
    expect(fieldLabel('destination', t)).toBe('điểm đến|destination');
    expect(fieldLabel('budget_max', t)).toBe('ngân sách|budget');
    expect(fieldLabel('preference', t)).toBe('sở thích|preference');
    expect(fieldLabel('mystery_field', t)).toBe('mystery field|mystery field');
    expect(operatorLabel('eq', t)).toBe('là|is');
    expect(operatorLabel('lte', t)).toBe('tối đa|at most');
    expect(operatorLabel('mystery_op', t)).toBe('mystery_op|mystery_op');
  });

  it('drops the equality word and formats numbers for display', () => {
    const t = (vi: string) => vi;
    expect(conditionText('eq', 'Ai Cập', t)).toBe('Ai Cập');
    expect(conditionText('contains', 'Ai Cập', t)).toBe('gồm Ai Cập');
    expect(conditionText('lte', 100000000, t)).toBe('tối đa 100.000.000');
    expect(display(['Hà Nội', 'Huế'])).toBe('Hà Nội, Huế');
  });
});
