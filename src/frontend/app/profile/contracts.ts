import { ContractError, record } from '../../api/contracts';

export interface TravelPreferences {
  hotel_stars: number | null;
  duration_days: number | null;
  shopping: 'any' | 'few';
  prefer_lower_listed_price: boolean;
  levels: Record<'cost' | 'comfort' | 'pace' | 'culture', number>;
}
export interface TravelTemplate {
  name: string;
  values: {
    departure_origin: string | null;
    destinations: string[];
    adults: number | null;
    child_count: number;
    preferences: TravelPreferences;
  };
}
export interface SavedTour {
  title: string;
  supplier: string | null;
  url: string;
  comparison_id: string;
  column_id: string;
  offer_snapshot_id: string | null;
  departure_date: string | null;
  price_label: string | null;
  evaluated_at: string;
  saved_at: string;
  status_at_save: 'recommended' | 'needs_verification' | 'reference';
  note: string;
  collection: string;
}
export type HubKind = 'preferences' | 'template' | 'saved_tour';
export interface HubItem<T> {
  id: string;
  kind: HubKind;
  version: number;
  updated_at: string;
  value: T;
}
export interface HubState {
  schema_version: '1';
  preferences: HubItem<TravelPreferences> | null;
  preferences_version: number;
  templates: HubItem<TravelTemplate>[];
  saved_tours: HubItem<SavedTour>[];
}
export type HubMutation =
  | { deleted: true; id: string; version: number }
  | { deleted: false; item: HubItem<TravelPreferences | TravelTemplate | SavedTour> };
export const defaultPreferences: TravelPreferences = {
  hotel_stars: null,
  duration_days: null,
  shopping: 'any',
  prefer_lower_listed_price: false,
  levels: { cost: 3, comfort: 3, pace: 3, culture: 3 },
};
const fail = (): never => {
  throw new ContractError('profile_hub');
};
const text = (v: unknown, max: number, min = 0): v is string =>
  typeof v === 'string' && v.length >= min && v.length <= max;
const integer = (v: unknown, min: number, max: number): v is number =>
  typeof v === 'number' && Number.isInteger(v) && v >= min && v <= max;
function preferences(v: unknown): void {
  const p = record(v);
  const l = record(p.levels);
  if (
    !(p.hotel_stars === null || integer(p.hotel_stars, 1, 5)) ||
    !(p.duration_days === null || integer(p.duration_days, 1, 90)) ||
    !['any', 'few'].includes(p.shopping as string) ||
    typeof p.prefer_lower_listed_price !== 'boolean' ||
    !['cost', 'comfort', 'pace', 'culture'].every((k) => integer(l[k], 1, 5))
  )
    fail();
}
function template(v: unknown): void {
  const p = record(v);
  const x = record(p.values);
  if (
    !text(p.name, 80, 1) ||
    !(x.departure_origin === null || text(x.departure_origin, 128, 1)) ||
    !Array.isArray(x.destinations) ||
    x.destinations.length > 10 ||
    !x.destinations.every((x) => text(x, 128, 1)) ||
    !(x.adults === null || integer(x.adults, 1, 100)) ||
    !integer(x.child_count, 0, 20)
  )
    fail();
  preferences(x.preferences);
}
function saved(v: unknown): void {
  const p = record(v);
  if (
    !text(p.title, 500, 1) ||
    !text(p.url, 2048, 1) ||
    !text(p.comparison_id, 128, 1) ||
    !text(p.column_id, 128, 1) ||
    !text(p.note, 1000) ||
    !text(p.collection, 80) ||
    !['recommended', 'needs_verification', 'reference'].includes(p.status_at_save as string)
  )
    fail();
  for (const k of ['supplier', 'departure_date', 'price_label', 'offer_snapshot_id'])
    if (p[k] !== null && !text(p[k], 500)) fail();
  for (const k of ['saved_at', 'evaluated_at'])
    if (typeof p[k] !== 'string' || !Number.isFinite(Date.parse(p[k]))) fail();
  try {
    const url = new URL(p.url as string);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) fail();
  } catch {
    fail();
  }
}
function item(v: unknown, kind?: HubKind): void {
  const p = record(v);
  if (
    !text(p.id, 128, 1) ||
    !integer(p.version, 1, Number.MAX_SAFE_INTEGER) ||
    typeof p.updated_at !== 'string' ||
    !Number.isFinite(Date.parse(p.updated_at)) ||
    (kind && p.kind !== kind)
  )
    fail();
  if (p.kind === 'preferences') preferences(p.value);
  else if (p.kind === 'template') template(p.value);
  else if (p.kind === 'saved_tour') saved(p.value);
  else fail();
}
export function validateHub(v: unknown): void {
  const p = record(v);
  if (p.schema_version !== '1' || !integer(p.preferences_version, 0, Number.MAX_SAFE_INTEGER))
    fail();
  if (p.preferences !== null) item(p.preferences, 'preferences');
  if (
    !Array.isArray(p.templates) ||
    p.templates.length > 20 ||
    !Array.isArray(p.saved_tours) ||
    p.saved_tours.length > 40
  )
    fail();
  (p.templates as unknown[]).forEach((x) => item(x, 'template'));
  (p.saved_tours as unknown[]).forEach((x) => item(x, 'saved_tour'));
}
export function validateHubMutation(v: unknown): void {
  const p = record(v);
  if (p.deleted === true) {
    if (!text(p.id, 128, 1) || !integer(p.version, 1, Number.MAX_SAFE_INTEGER)) fail();
  } else if (p.deleted === false) item(p.item);
  else fail();
}
