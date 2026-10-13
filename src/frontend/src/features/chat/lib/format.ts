import type { CurrentComparison, CurrentCondition, CurrentEvaluation } from '../../../shared/api';

export function display(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return value.toLocaleString('vi-VN');
  if (Array.isArray(value)) return value.map((item) => display(item)).join(', ');
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export interface OfferEvaluation {
  evaluation: CurrentEvaluation;
  condition: CurrentCondition | null;
}

export function evaluationsForOffer(
  comparison: CurrentComparison,
  offerId: string,
): OfferEvaluation[] {
  const conditions = new Map(comparison.requirement.conditions.map((item) => [item.id, item]));
  return comparison.evaluations
    .filter((item) => item.offer_id === offerId)
    .map((evaluation) => ({
      evaluation,
      condition: conditions.get(evaluation.condition_id) ?? null,
    }));
}

/** Hard-failed evaluations for an offer, joined with their conditions. */
export function failedDetailsForOffer(
  comparison: CurrentComparison,
  offerId: string,
): OfferEvaluation[] {
  return evaluationsForOffer(comparison, offerId).filter(
    ({ evaluation }) => evaluation.state === 'fail',
  );
}

/** The hard condition field failed by the most offers, for one-tap relax. */
export function mostFailedField(
  comparison: CurrentComparison,
): { field: string; count: number } | null {
  const counts = new Map<string, number>();
  const hardConditions = comparison.requirement.conditions.filter(
    (item) => item.strength === 'hard',
  );
  const hardIds = new Set(hardConditions.map((item) => item.id));
  const fieldOf = new Map(hardConditions.map((item) => [item.id, item.field]));
  for (const evaluation of comparison.evaluations) {
    if (evaluation.state !== 'fail' || !hardIds.has(evaluation.condition_id)) continue;
    const field = fieldOf.get(evaluation.condition_id);
    if (!field) continue;
    counts.set(field, (counts.get(field) ?? 0) + 1);
  }
  let best: { field: string; count: number } | null = null;
  for (const [field, count] of counts) {
    if (!best || count > best.count) best = { field, count };
  }
  return best;
}

export function conditionState(comparison: CurrentComparison, offerId: string) {
  const hardIds = comparison.requirement.conditions
    .filter((condition) => condition.strength === 'hard')
    .map((condition) => condition.id);
  if (!hardIds.length) return 'pass';
  const states = new Map(
    comparison.evaluations
      .filter((item) => item.offer_id === offerId && hardIds.includes(item.condition_id))
      .map((item) => [item.condition_id, item.state]),
  );
  if (hardIds.some((id) => states.get(id) === 'fail')) return 'fail';
  if (hardIds.some((id) => states.get(id) !== 'pass')) return 'unknown';
  return 'pass';
}

/* Operators come from LLM extraction (`operator = str(item.get("operator", "eq"))`
 * in src/backend/input/pipeline.py) and are NOT validated server-side, so this
 * set is deliberately open: known codes map to language, anything else falls
 * back to the raw code instead of crashing. */
const OPERATOR_LABEL: Record<string, [string, string]> = {
  eq: ['là', 'is'],
  contains: ['gồm', 'includes'],
  lte: ['tối đa', 'at most'],
  gte: ['tối thiểu', 'at least'],
  gt: ['trên', 'over'],
  lt: ['dưới', 'under'],
  ne: ['khác', 'is not'],
  any: ['bất kỳ', 'any'],
  in: ['trong', 'in'],
  between: ['từ', 'between'],
};

/** Backend operator codes are data, not copy — map them to language. */
export function operatorLabel(operator: string, t: (vi: string, en: string) => string): string {
  const label = OPERATOR_LABEL[operator];
  return label ? t(...label) : t(operator, operator);
}

/**
 * Full condition text for display. Equality needs no word — the label/value
 * layout already says "is". Words stay only where they add meaning
 * ("gồm", "tối đa", ...).
 */
export function conditionText(
  operator: string,
  value: unknown,
  t: (vi: string, en: string) => string,
): string {
  const shown = display(value);
  if (operator === 'eq') return shown;
  return `${operatorLabel(operator, t)} ${shown}`;
}

/* Hard fields mirror `_HARD_FIELDS` in src/backend/input/pipeline.py;
 * soft criteria always arrive as field="preference". Keep in sync when the
 * backend adds a field — unknown fields fall back to readable snake_case. */
const FIELD_LABEL: Record<string, [string, string]> = {
  destination: ['điểm đến', 'destination'],
  departure_city: ['nơi đi', 'departure city'],
  date_from: ['ngày đi', 'departure date'],
  date_to: ['ngày về', 'return date'],
  budget_max: ['ngân sách', 'budget'],
  duration_days: ['thời lượng', 'duration'],
  transport: ['phương tiện', 'transport'],
  accommodation: ['lưu trú', 'accommodation'],
  preference: ['sở thích', 'preference'],
};

/** Backend field names are data, not copy — map them to language. */
export function fieldLabel(field: string, t: (vi: string, en: string) => string): string {
  const label = FIELD_LABEL[field];
  return label ? t(...label) : t(field.replaceAll('_', ' '), field.replaceAll('_', ' '));
}
