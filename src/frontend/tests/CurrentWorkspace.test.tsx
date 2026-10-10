// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CurrentWorkspace } from '../features/workspace/CurrentWorkspace';
import { PreferencesProvider } from '../app/preferences';
import { newSession, type LocalSession } from '../app/storage';

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeBackend() {
  return vi.fn<typeof fetch>(async (input, init) => {
    const path = new URL(String(input), 'http://local').pathname;
    const method = init?.method ?? 'GET';
    if (path === '/sessions' && method === 'POST')
      return response(
        {
          id: 'ses_guest',
          session_id: 'ses_guest',
          token: 'guest-secret',
          token_type: 'Bearer',
          expires_at: '2030-01-01T00:00:00+00:00',
        },
        201,
      );
    if (path === '/catalog') return response({ destinations: ['Đà Lạt'] });
    if (path === '/health') return response({ status: 'ok', version: 'test' });
    if (path === '/requirements' && method === 'POST')
      return response({
        requirement: {
          id: 'req_guest',
          conditions: [
            {
              id: 'h1',
              field: 'destination',
              operator: 'contains',
              value: 'Đà Lạt',
              strength: 'hard',
              quote: '',
            },
          ],
          missing: [],
          raw_text: 'Đà Lạt',
          travelers: 1,
        },
      });
    if (path === '/comparisons' && method === 'POST')
      return response({
        comparison: {
          id: 'cmp_guest',
          requirement: {
            id: 'req_guest',
            conditions: [],
            missing: [],
            raw_text: 'Đà Lạt',
            travelers: 1,
          },
          ranked: [{ tour_id: 'tour_guest', offer_id: 'offer_guest', score: 0 }],
          tour_snapshots: [
            {
              id: 'tour_guest',
              supplier: 'Local Tours',
              name: 'Đà Lạt cuối tuần',
              url: 'https://example.test/tours/da-lat',
              destinations: ['Đà Lạt'],
              raw_destinations: ['Đà Lạt'],
              route: [],
              destination_countries: ['vn'],
              destination_country_complete: true,
              departure_city: 'TP.HCM',
              duration_days: 3,
              transport: 'bus',
              accommodation: 'Hotel',
              itinerary: '',
              inclusions: 'Xe đưa đón',
              exclusions: '',
              cancellation_policy: '',
              surcharges: '',
              child_policy: '',
              evidence: {
                url: 'https://example.test/tours/da-lat',
                method: 'database_record',
                observed_at: '',
                record_ref: '',
              },
              observed_at: '',
              verification: 'provider_claimed',
              offers: [
                {
                  id: 'offer_guest',
                  tour_id: 'tour_guest',
                  departure_date: '2026-12-01',
                  price: 5000000,
                  currency: 'VND',
                  price_basis: 'exact',
                  price_trusted: true,
                  price_freshness: 'fresh',
                  departure_freshness: 'fresh',
                  pricing_metadata_state: 'validated',
                  availability: 'unknown',
                  conditions: '',
                  evidence: {
                    url: 'https://example.test/tours/da-lat',
                    method: 'database_record',
                    observed_at: '',
                    record_ref: '',
                  },
                },
              ],
            },
          ],
          evaluations: [
            {
              offer_id: 'offer_guest',
              condition_id: 'h1',
              state: 'pass',
              quote: '',
              reason_code: '',
            },
          ],
          analysis: { hidden_costs: [], conditions: [], risks: [], benefits: [] },
          candidates_considered: 1,
        },
      });
    return response({ error: { code: 'NOT_FOUND', message: 'not found' } }, 404);
  });
}

function Harness({ initial }: { initial: LocalSession }) {
  const [session, setSession] = useState(initial);
  return (
    <PreferencesProvider>
      <CurrentWorkspace
        session={session}
        onChangeSession={(changes) => setSession((current) => ({ ...current, ...changes }))}
      />
    </PreferencesProvider>
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('CurrentWorkspace guest flow', () => {
  it('interprets, searches and renders a persisted current-backend snapshot', async () => {
    const fetcher = makeBackend();
    vi.stubGlobal('fetch', fetcher);
    const initial = newSession();
    render(<Harness initial={initial} />);

    const description = await screen.findByLabelText('Mô tả chuyến đi');
    fireEvent.change(description, { target: { value: 'Đà Lạt' } });
    fireEvent.change(screen.getByLabelText('Điểm đến trong catalog'), {
      target: { value: 'Đà Lạt' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Diễn giải nhu cầu' }));

    expect(await screen.findByText('destination')).toBeTruthy();
    expect(fetcher).toHaveBeenCalledWith(
      '/requirements',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer guest-secret' }),
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Tìm và so sánh tour' }));
    expect(await screen.findByText('Đà Lạt cuối tuần')).toBeTruthy();
    expect(screen.getByText(/5,000,000 VND/)).toBeTruthy();
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/comparisons', expect.anything()));
  });

  it('blocks unsupported draft criteria instead of silently dropping them', async () => {
    const fetcher = makeBackend();
    vi.stubGlobal('fetch', fetcher);
    const initial = newSession();
    initial.draft.text = 'Đà Lạt';
    initial.draft.budgetMin = '3000000';
    render(<Harness initial={initial} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Diễn giải nhu cầu' }));
    expect((await screen.findByRole('alert')).textContent).toContain('budget ranges');
    expect(fetcher).not.toHaveBeenCalledWith('/requirements', expect.anything());
  });
});
