// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { CurrentComparison } from '../../../shared/api';
import { PreferencesProvider } from '../../../shared/preferences';
import { ResultCards } from './ResultCards';

const evidence = { url: '', method: '', observed_at: '', record_ref: '' };
const comparison = {
  id: 'cmp_test',
  requirement: { id: 'req_test', conditions: [], missing: [], raw_text: 'Mộc Châu', travelers: 1 },
  ranked: [
    { tour_id: 'tour-a', offer_id: 'offer-a-1', score: 1 },
    { tour_id: 'tour-a', offer_id: 'offer-a-2', score: 1 },
  ],
  near_miss: [],
  tour_snapshots: [
    {
      id: 'tour-a',
      supplier: 'Example Travel',
      name: 'Tour Mộc Châu',
      url: '',
      destinations: ['Mộc Châu'],
      raw_destinations: ['Mộc Châu'],
      route: [],
      departure_city: 'Hà Nội',
      duration_days: 3,
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
      offers: ['offer-a-1', 'offer-a-2'].map((id, index) => ({
        id,
        tour_id: 'tour-a',
        departure_date: index === 0 ? '2026-11-11' : '2026-11-25',
        price: 5_000_000,
        currency: 'VND',
        price_basis: 'exact' as const,
        departure_freshness: 'unknown' as const,
        availability: 'unknown',
        conditions: '',
        evidence,
      })),
    },
  ],
  evaluations: [],
  analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
  candidates_considered: 1,
} satisfies CurrentComparison;

afterEach(cleanup);

describe('ResultCards', () => {
  it('renders one card and counts one tour when ranked offers share a tour ID', () => {
    render(
      <PreferencesProvider>
        <ResultCards comparison={comparison} busy={false} onRelax={() => {}} />
      </PreferencesProvider>,
    );

    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(screen.getByRole('status').textContent).toContain('1 tour đạt đủ');
  });
});
