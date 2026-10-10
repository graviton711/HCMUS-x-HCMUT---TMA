import { emptyForm, type FormValues } from '../../api/form';
import { defaultPreferences, type TravelPreferences, type TravelTemplate } from './contracts';

export function preferenceDraft(p: TravelPreferences): FormValues {
  const d = structuredClone(emptyForm);
  d.hotelStars = p.hotel_stars === null ? '' : String(p.hotel_stars);
  d.durationDays = p.duration_days === null ? '' : String(p.duration_days);
  d.shopping = p.shopping;
  d.preferLowerListedPrice = p.prefer_lower_listed_price;
  d.preferenceLevels = { ...p.levels };
  d.preferenceOrigins = { cost: 'user', comfort: 'user', pace: 'user', culture: 'user' };
  d.strengths = { hotel_stars_min: 'soft', duration_days: 'soft', shopping_stops: 'soft' };
  return d;
}
export function templateDraft(t: TravelTemplate): FormValues {
  const d = preferenceDraft(t.values.preferences);
  d.departureOrigin = t.values.departure_origin ?? '';
  d.destinations = [...t.values.destinations];
  d.adults = t.values.adults ?? 0;
  d.childAges = Array.from({ length: t.values.child_count }, () => null);
  return d;
}
export function preferencesFromDraft(d: FormValues): TravelPreferences {
  return {
    ...structuredClone(defaultPreferences),
    hotel_stars: d.hotelStars ? Number(d.hotelStars) : null,
    duration_days: d.durationDays ? Number(d.durationDays) : null,
    shopping: d.shopping === 'any' ? 'any' : 'few',
    prefer_lower_listed_price: d.preferLowerListedPrice ?? false,
    levels: { ...d.preferenceLevels },
  };
}
export function templateFromDraft(d: FormValues, name: string): TravelTemplate {
  return {
    name: name.trim(),
    values: {
      departure_origin: d.departureOrigin || null,
      destinations: [...d.destinations],
      adults: d.adults || null,
      child_count: d.childAges.length,
      preferences: preferencesFromDraft(d),
    },
  };
}
