import type { SavedTour } from './types';

const storagePrefix = 'di-cung:saved-tours:v1';

export function savedToursStorageKey(ownerId?: string) {
  return ownerId ? `${storagePrefix}:user:${encodeURIComponent(ownerId)}` : storagePrefix;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function isSavedTour(value: unknown): value is SavedTour {
  if (!isRecord(value)) return false;
  if (
    ![
      'id',
      'savedAt',
      'tourId',
      'offerId',
      'name',
      'supplier',
      'departureCity',
      'transport',
      'departureDate',
      'currency',
      'availability',
      'conditions',
      'sourceUrl',
      'observedAt',
    ].every((key) => typeof value[key] === 'string')
  )
    return false;
  if (
    !isStringList(value.destinations) ||
    !isStringList(value.route) ||
    !Array.isArray(value.evaluations) ||
    !(value.durationDays === null || typeof value.durationDays === 'number') ||
    !(value.price === null || typeof value.price === 'number') ||
    !['exact', 'from', 'contact'].includes(String(value.priceBasis))
  )
    return false;
  return value.evaluations.every((item) => {
    if (!isRecord(item) || !isRecord(item.condition)) return false;
    return (
      typeof item.condition.id === 'string' &&
      typeof item.condition.field === 'string' &&
      typeof item.condition.operator === 'string' &&
      ['hard', 'soft'].includes(String(item.condition.strength)) &&
      ['pass', 'fail', 'unknown'].includes(String(item.state)) &&
      typeof item.quote === 'string' &&
      typeof item.reasonCode === 'string' &&
      typeof item.reason === 'string'
    );
  });
}

export function loadSavedTours(ownerId?: string): SavedTour[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(savedToursStorageKey(ownerId)) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter(isSavedTour) : [];
  } catch {
    return [];
  }
}

export function saveSavedTours(tours: SavedTour[], ownerId?: string) {
  try {
    localStorage.setItem(savedToursStorageKey(ownerId), JSON.stringify(tours));
    return true;
  } catch {
    return false;
  }
}
