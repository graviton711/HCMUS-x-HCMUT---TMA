// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  CurrentBackendClient,
  CurrentComparison,
  CurrentEliminatedPage,
} from '../../../shared/api';
import { PreferencesProvider } from '../../../shared/preferences';
import { DecisionTracePanel } from './DecisionWorkspace';

const comparison = {
  id: 'cmp-trace',
  requirement: { conditions: [], missing: [], raw_text: '', travelers: 1 },
  decision_trace: {
    scanned_tours: 10,
    scanned_offers: 10,
    eligible_tours: 2,
    eligible_offers: 2,
    excluded_offers: 8,
    condition_counts: [],
    sequential_funnel: [],
    first_blockers: [],
    alternative_counts: [],
    snapshot_available: true,
  },
} as unknown as CurrentComparison;

function page(): CurrentEliminatedPage {
  return {
    comparison_id: comparison.id,
    items: [],
    limit: 20,
    next_cursor: null,
    total: 8,
  };
}

function renderPanel(client: CurrentBackendClient) {
  return render(
    <PreferencesProvider>
      <DecisionTracePanel comparison={comparison} client={client} />
    </PreferencesProvider>,
  );
}

function openExclusions() {
  fireEvent.click(screen.getByText(/lọc|filter/i));
  fireEvent.click(screen.getByRole('button', { name: /offer/i }));
}

afterEach(cleanup);

describe('DecisionTracePanel excluded list', () => {
  it('can collapse during loading and reloads the first page when reopened', async () => {
    const resolvers: ((value: CurrentEliminatedPage) => void)[] = [];
    const eliminatedOffers = vi.fn<CurrentBackendClient['eliminatedOffers']>(
      () => new Promise<CurrentEliminatedPage>((resolve) => resolvers.push(resolve)),
    );
    renderPanel({ eliminatedOffers } as unknown as CurrentBackendClient);

    openExclusions();
    expect(screen.getByRole('status').textContent).toMatch(/loading|tải/i);
    fireEvent.click(screen.getByRole('button', { name: /thu gọn|collapse/i }));
    expect(screen.queryByRole('button', { name: /thu gọn|collapse/i })).toBeNull();
    expect(screen.getByText(/lọc|filter/i).closest('details')?.open).toBe(true);

    openExclusions();
    expect(eliminatedOffers).toHaveBeenCalledTimes(2);
    expect(eliminatedOffers.mock.calls[1]?.[1]).toBeUndefined();
    await act(async () => {
      resolvers.forEach((resolve) => resolve(page()));
    });
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
    expect(screen.getByRole('button', { name: /thu gọn|collapse/i })).toBeTruthy();
  });

  it('keeps a collapse control available after an error and allows a retry', async () => {
    const eliminatedOffers = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(page());
    renderPanel({ eliminatedOffers } as unknown as CurrentBackendClient);

    openExclusions();
    expect(await screen.findByRole('status')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /thu gọn|collapse/i }));
    expect(screen.queryByRole('status')).toBeNull();

    openExclusions();
    await waitFor(() => expect(eliminatedOffers).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('button', { name: /thu gọn|collapse/i })).toBeTruthy();
  });
});
