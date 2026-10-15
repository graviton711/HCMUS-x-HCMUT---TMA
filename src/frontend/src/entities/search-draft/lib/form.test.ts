import { describe, expect, it } from 'vitest';
import type { CurrentCatalog } from '../../../shared/api';
import { emptySearchDraft } from '../model/defaults';
import { currentForm } from './form';

const catalog: CurrentCatalog = { destinations: [] };

describe('currentForm date contract', () => {
  it('does not map a return date to the departure-date upper bound', () => {
    const draft = { ...emptySearchDraft, departureDate: '2026-11-21' };

    expect(currentForm(draft, catalog)).toMatchObject({ date_from: '2026-11-21' });
    expect(currentForm(draft, catalog)).not.toHaveProperty('date_to');
  });

  it('rejects legacy return-date input instead of filtering the wrong date', () => {
    const draft = { ...emptySearchDraft, returnDate: '2026-11-30' };

    expect(() => currentForm(draft, catalog)).toThrow(/date_to field means latest departure date/u);
  });
});
