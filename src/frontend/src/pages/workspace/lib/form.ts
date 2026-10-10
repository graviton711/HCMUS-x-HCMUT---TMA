import type { SearchDraft } from '../../../entities/search-draft';
import type { CurrentCatalog } from '../../../shared/api';

/** Maps a search draft onto the fields the current backend accepts. Throws on unsupported criteria. */
export function currentForm(draft: SearchDraft, catalog: CurrentCatalog): Record<string, unknown> {
  const unsupported: string[] = [];
  if (draft.mode === 'urls' || draft.referenceUrls.length) unsupported.push('URL tours');
  if (draft.returnDate || draft.departureMonths.length)
    unsupported.push('return dates/month ranges');
  if (draft.budgetMin) unsupported.push('budget ranges');
  if (draft.budget && draft.budgetBasis !== 'per_adult') unsupported.push('non-adult budget basis');
  if (draft.childAges.length) unsupported.push('child-age pricing');
  if (draft.hotelStars) unsupported.push('hotel rating');
  if (draft.shopping !== 'any') unsupported.push('shopping preference');
  if (draft.transport.length > 1) unsupported.push('multiple transport choices');
  if (draft.includedServices.length) unsupported.push('included services');
  if (draft.notes.trim()) unsupported.push('additional notes');
  if (Object.values(draft.preferenceLevels).some((level) => level !== 3))
    unsupported.push('soft ranking preferences');
  if (unsupported.length)
    throw new Error(
      `These criteria are not supported by the current backend and were not sent: ${unsupported.join(', ')}.`,
    );

  for (const [label, value] of [
    ['budget', draft.budget],
    ['duration', draft.durationDays],
  ] as const) {
    if (
      value &&
      (!/^\d+$/u.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) <= 0)
    )
      throw new Error(`${label} must be a positive whole number.`);
  }
  if (draft.budget && Number(draft.budget) > 10 ** 15)
    throw new Error('Budget is above the supported numeric range.');
  if (!validAdults(draft.adults))
    throw new Error('Adult count must be a whole number from 0 to 100.');
  if (draft.departureDate) {
    const parsed = new Date(`${draft.departureDate}T00:00:00Z`);
    if (
      !/^\d{4}-\d{2}-\d{2}$/u.test(draft.departureDate) ||
      Number.isNaN(parsed.getTime()) ||
      parsed.toISOString().slice(0, 10) !== draft.departureDate
    )
      throw new Error('Departure date is invalid.');
  }

  const destination = draft.destinations[0]?.trim();
  if (destination && !catalog.destinations.includes(destination))
    throw new Error('Choose a destination from the backend catalog, or describe it in your text.');
  const form: Record<string, unknown> = {};
  if (draft.destinations.length) form.destinations = draft.destinations;
  if (draft.departureOrigin.trim()) form.departure_city = draft.departureOrigin.trim();
  if (draft.departureDate) form.date_from = draft.departureDate;
  if (draft.budget) form.budget_max = Number(draft.budget);
  if (draft.durationDays) form.duration_days = Number(draft.durationDays);
  if (draft.transport.length === 1) form.transport = draft.transport[0];
  if (draft.adults > 0) form.travelers = draft.adults;
  return form;
}

/** Validates the adult count. Zero means unspecified and is accepted. */
export function validAdults(adults: number): boolean {
  return Number.isInteger(adults) && adults >= 0 && adults <= 100;
}
