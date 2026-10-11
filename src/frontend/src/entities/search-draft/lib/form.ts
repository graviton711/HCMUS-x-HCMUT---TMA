import type { CurrentCatalog } from '../../../shared/api';
import type { SearchDraft } from '../model/types';

const isoDate = /^\d{4}-\d{2}-\d{2}$/u;

function checkDate(label: string, value: string) {
  const parsed = new Date(`${value}T00:00:00Z`);
  if (
    !isoDate.test(value) ||
    Number.isNaN(parsed.getTime()) ||
    parsed.toISOString().slice(0, 10) !== value
  )
    throw new Error(`${label} is invalid. Use YYYY-MM-DD.`);
}

/** Maps a search draft onto the fields the current backend accepts. */
export function currentForm(draft: SearchDraft, catalog: CurrentCatalog): Record<string, unknown> {
  if (draft.transport.length > 1)
    throw new Error('The current backend compares a single transport choice; keep only one.');

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
  if (draft.departureDate) checkDate('Departure date', draft.departureDate);
  if (draft.returnDate) checkDate('Return date', draft.returnDate);
  if (draft.departureDate && draft.returnDate && draft.returnDate < draft.departureDate)
    throw new Error('Return date must be on or after the departure date.');

  const destination = draft.destinations[0]?.trim();
  if (destination && !catalog.destinations.includes(destination))
    throw new Error('Choose a destination from the backend catalog, or describe it in your text.');
  const form: Record<string, unknown> = {};
  if (draft.destinations.length) form.destinations = draft.destinations;
  if (draft.departureOrigin.trim()) form.departure_city = draft.departureOrigin.trim();
  if (draft.departureDate) form.date_from = draft.departureDate;
  if (draft.returnDate) form.date_to = draft.returnDate;
  if (draft.budget) form.budget_max = Number(draft.budget);
  if (draft.durationDays) form.duration_days = Number(draft.durationDays);
  if (draft.transport.length === 1) form.transport = draft.transport[0];
  if (draft.accommodation.trim()) form.accommodation = draft.accommodation.trim();
  if (draft.adults > 0) form.travelers = draft.adults;
  return form;
}

/** Validates the adult count. Zero means unspecified and is accepted. */
export function validAdults(adults: number): boolean {
  return Number.isInteger(adults) && adults >= 0 && adults <= 100;
}
