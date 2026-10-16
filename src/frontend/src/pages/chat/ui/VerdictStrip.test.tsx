// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CurrentComparison } from '../../../shared/api';
import { PreferencesProvider } from '../../../shared/preferences';
import { VerdictStrip } from './VerdictStrip';

afterEach(cleanup);

const evidence = { url: '', method: '', observed_at: '', record_ref: '' };

function tour(id: string) {
  return {
    id,
    supplier: 'Example Travel',
    name: `Tour ${id}`,
    url: '',
    destinations: ['Cần Thơ'],
    raw_destinations: ['Cần Thơ'],
    route: [],
    departure_city: 'Hồ Chí Minh',
    duration_days: 2,
    transport: 'bus',
    accommodation: '',
    itinerary: '',
    inclusions: '',
    exclusions: '',
    cancellation_policy: '',
    surcharges: '',
    child_policy: '',
    evidence,
    observed_at: '',
    verification: 'provider_claimed',
    offers: [
      {
        id: `${id}-offer`,
        tour_id: id,
        departure_date: '2026-10-19',
        price: 1650000,
        currency: 'VND',
        price_basis: 'exact' as const,
        departure_freshness: 'unknown' as const,
        availability: 'unknown',
        conditions: '',
        evidence,
      },
    ],
  };
}

function comparison(): CurrentComparison {
  return {
    id: 'cmp_1',
    requirement: {
      id: 'req_1',
      raw_text: 'Đi Cần Thơ',
      travelers: 5,
      missing: [],
      conditions: [
        { id: 'h1', field: 'departure_city', operator: 'contains', value: 'Hồ Chí Minh', strength: 'hard', quote: 'TP.HCM' },
        { id: 'h2', field: 'budget_max', operator: 'lte', value: 2000000, strength: 'hard', quote: '2 triệu' },
      ],
    },
    ranked: [{ tour_id: 't1', offer_id: 't1-offer', score: 1 }],
    near_miss: [],
    tour_snapshots: [tour('t1'), tour('t2'), tour('t3')],
    evaluations: [],
    analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
    candidates_considered: 1210,
    decision_options: [
      {
        tour_id: 't1',
        offer_id: 't1-offer',
        objective: 'cheapest',
        title: 'Rẻ nhất trong scan',
        reason: 'Đáp ứng cả 2 điều kiện cứng.',
        tradeoffs: ['Đánh đổi: rẻ nhất nhóm.'],
        metric_comparisons: [
          {
            key: 'group_total',
            value: 8250000,
            reference_median: 15000000,
            unit: 'VND',
            currency: 'VND',
            scope: '',
            state: 'observed',
            relation: 'favorable',
            higher_is_better: false,
            evidence: [],
          },
        ],
      },
    ],
    relaxation_options: [
      {
        condition_id: 'h2',
        gained_offers: 4,
        gained_tours: 2,
        examples: [
          { tour_id: 't2', offer_id: 't2-offer', tour_name: 'Tour t2', price: 2500000, currency: 'VND', departure_date: '2026-10-19' },
          { tour_id: 't3', offer_id: 't3-offer', tour_name: 'Tour t3', price: 3100000, currency: 'VND', departure_date: '2026-10-20' },
        ],
      },
    ],
  } as unknown as CurrentComparison;
}

describe('VerdictStrip', () => {
  it('renders strict slots plus labeled relaxation slots with a honesty banner', () => {
    render(
      <PreferencesProvider>
        <VerdictStrip comparison={comparison()} client={null} agentSessionId={null} onOpenDecision={() => {}} />
      </PreferencesProvider>,
    );
    expect(screen.getByText(/Chưa đủ 3 tour đạt đủ điều kiện/)).toBeDefined();
    expect(screen.getByText('Đáp ứng cả 2 điều kiện cứng.')).toBeDefined();
    expect(screen.getByText(/Được:/)).toBeDefined();
    expect(screen.getByText(/Tổng nhóm/)).toBeDefined();
    expect(screen.getByText(/Nới.*ngân sách/)).toBeDefined();
    expect(screen.getByText(/mở thêm 2 tour/)).toBeDefined();
  });

  it('runs the relaxation scenario without the dropped condition', async () => {
    const criteriaScenario = vi.fn(async () => ({
      comparison: {
        decision_trace: { eligible_tours: 2, eligible_offers: 4 },
        tour_snapshots: [{ name: 'Tour t2' }, { name: 'Tour t3' }],
      },
    }));
    const client = { criteriaScenario } as never;
    render(
      <PreferencesProvider>
        <VerdictStrip comparison={comparison()} client={client} agentSessionId="agt_1" onOpenDecision={() => {}} />
      </PreferencesProvider>,
    );
    fireEvent.click(screen.getByText('Thử nới này'));
    await screen.findByText(/Có 2 tour đạt/);
    expect(criteriaScenario).toHaveBeenCalledOnce();
    const [, , sent] = criteriaScenario.mock.calls[0] as unknown as [
      string,
      string,
      { conditions: { id: string }[] },
    ];
    expect(sent.conditions.map((c) => c.id)).toEqual(['h1']);
  });
});
