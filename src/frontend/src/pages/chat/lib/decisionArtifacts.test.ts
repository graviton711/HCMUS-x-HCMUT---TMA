import { describe, expect, it } from 'vitest';
import type { CurrentComparison, CurrentRequirement } from '../../../shared/api';
import type { ChatMsg } from '../../../features/chat';
import { draftForComparison, hasDecisionMetrics, latestDecisionArtifact, sameDecision } from './decisionArtifacts';

const requirement: CurrentRequirement = {
  id: 'req-a',
  conditions: [
    {
      id: 'cond-a',
      field: 'destination',
      operator: 'equals',
      value: 'Đà Lạt',
      strength: 'hard',
      quote: 'Đà Lạt',
    },
    {
      id: 'cond-b',
      field: 'price',
      operator: 'max',
      value: 5000000,
      strength: 'soft',
      quote: '5 triệu',
      weight_percent: 100,
    },
  ],
  missing: [],
  raw_text: 'Đà Lạt dưới 5 triệu',
  travelers: 1,
  traveler_mix: { adult: 1 },
  ranking: { order_by: [{ field: 'price', direction: 'asc' }] },
};

const comparison: CurrentComparison = {
  id: 'cmp-a',
  requirement,
  ranked: [],
  near_miss: [],
  tour_snapshots: [],
  evaluations: [],
  analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
  candidates_considered: 10,
  decision_views: [
    { kind: 'cheapest', candidates: [], currencies: ['VND'], note: '' },
    { kind: 'best_fit', candidates: [], currencies: ['VND'], note: '' },
    { kind: 'balanced', candidates: [], currencies: ['VND'], note: '' },
  ],
  metric_profiles: [],
  decision_options: [],
};

describe('decision artifact selection', () => {
  it('matches requirement content despite a different requirement ID', () => {
    expect(sameDecision(requirement, { ...requirement, id: 'req-b' })).toBe(true);
    expect(sameDecision(requirement, {
      ...requirement,
      conditions: requirement.conditions.map((condition) =>
        condition.id === 'cond-b' ? { ...condition, weight_percent: 80 } : condition,
      ),
    })).toBe(false);
  });

  it('selects the latest structured artifact, never assistant prose', () => {
    const messages: ChatMsg[] = [
      { id: 'text', kind: 'assistant', text: 'Tôi đã chuẩn bị xong bản yêu cầu.' },
      { id: 'brief', kind: 'decision_draft', requirement, status: 'draft' },
      { id: 'result', kind: 'comparison', comparison },
    ];
    expect(latestDecisionArtifact(messages)?.id).toBe('result');
    expect(draftForComparison(messages, comparison)?.id).toBe('brief');
    expect(latestDecisionArtifact([{ id: 'text', kind: 'assistant', text: 'Đã xong.' }])).toBeNull();
  });

  it('recognizes old comparisons without the metric contract', () => {
    expect(hasDecisionMetrics(comparison)).toBe(true);
    expect(hasDecisionMetrics({ ...comparison, decision_views: [] })).toBe(false);
    expect(hasDecisionMetrics({ ...comparison, metric_profiles: undefined })).toBe(false);
  });
});
