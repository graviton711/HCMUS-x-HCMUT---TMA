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
  const conditions = new Map(
    [
      ...comparison.requirement.conditions,
      ...(comparison.requirement.alternatives ?? []).flatMap(
        (alternative) => alternative.conditions,
      ),
    ].map((item) => [item.id, item]),
  );
  return comparison.evaluations
    .filter((item) => item.offer_id === offerId)
    .map((evaluation) => ({
      evaluation,
      condition: conditions.get(evaluation.condition_id) ?? null,
    }));
}

/** Blocking evaluations for an offer, using only shared criteria and its best OR branch. */
export function failedDetailsForOffer(
  comparison: CurrentComparison,
  offerId: string,
): OfferEvaluation[] {
  const details = evaluationsForOffer(comparison, offerId);
  const alternatives = comparison.requirement.alternatives ?? [];
  if (!alternatives.length) return details.filter(({ evaluation }) => evaluation.state === 'fail');

  const states = new Map(
    details.map(({ evaluation }) => [evaluation.condition_id, evaluation.state]),
  );
  const common = comparison.requirement.conditions.filter(
    (condition) => condition.strength === 'hard',
  );
  const commonBlockers = common.filter((condition) => states.get(condition.id) !== 'pass');
  if (commonBlockers.length) {
    return details.filter(({ evaluation }) =>
      commonBlockers.some((condition) => condition.id === evaluation.condition_id),
    );
  }

  const branchScores = alternatives
    .map((alternative) => {
      const branchStates = alternative.conditions.map(
        (condition) => states.get(condition.id) ?? 'unknown',
      );
      return {
        alternative,
        failed: branchStates.filter((state) => state === 'fail').length,
        unknown: branchStates.filter((state) => state === 'unknown').length,
        passed: branchStates.filter((state) => state === 'pass').length,
      };
    })
    .sort(
      (left, right) =>
        left.failed - right.failed ||
        left.unknown - right.unknown ||
        right.passed - left.passed ||
        left.alternative.id.localeCompare(right.alternative.id),
    );
  const best = branchScores[0];
  if (!best || (best.failed === 0 && best.unknown === 0)) return [];
  return details.filter(
    ({ evaluation }) =>
      best.alternative.conditions.some((condition) => condition.id === evaluation.condition_id) &&
      evaluation.state !== 'pass',
  );
}

/** The hard condition field failed by the most offers, for one-tap relax. */
export function mostFailedField(
  comparison: CurrentComparison,
): { field: string; count: number } | null {
  const alternatives = comparison.requirement.alternatives ?? [];
  if (alternatives.length) {
    const shared = comparison.requirement.conditions.filter((item) => item.strength === 'hard');
    const evaluationByOffer = new Map<string, Map<string, CurrentEvaluation>>();
    for (const evaluation of comparison.evaluations) {
      const perCondition =
        evaluationByOffer.get(evaluation.offer_id) ?? new Map<string, CurrentEvaluation>();
      perCondition.set(evaluation.condition_id, evaluation);
      evaluationByOffer.set(evaluation.offer_id, perCondition);
    }
    const counts = new Map<string, number>();
    const count = (condition: CurrentCondition) =>
      counts.set(condition.field, (counts.get(condition.field) ?? 0) + 1);
    for (const offer of comparison.tour_snapshots.flatMap((tour) => tour.offers)) {
      const states = evaluationByOffer.get(offer.id) ?? new Map<string, CurrentEvaluation>();
      const commonFail = shared.find((condition) => states.get(condition.id)?.state === 'fail');
      if (commonFail) {
        count(commonFail);
        continue;
      }
      if (shared.some((condition) => states.get(condition.id)?.state !== 'pass')) continue;
      const branches = alternatives.map((alternative) => {
        const branchStates = alternative.conditions.map(
          (condition) => states.get(condition.id)?.state ?? 'unknown',
        );
        return {
          alternative,
          states: branchStates,
          failed: branchStates.filter((state) => state === 'fail').length,
          unknown: branchStates.filter((state) => state === 'unknown').length,
          passed: branchStates.filter((state) => state === 'pass').length,
        };
      });
      if (branches.some((branch) => branch.failed === 0 && branch.unknown === 0)) continue;
      const best = branches.sort(
        (left, right) =>
          left.failed - right.failed ||
          left.unknown - right.unknown ||
          right.passed - left.passed ||
          left.alternative.id.localeCompare(right.alternative.id),
      )[0];
      const blocker = best?.alternative.conditions.find(
        (condition) => states.get(condition.id)?.state === 'fail',
      );
      if (blocker) count(blocker);
    }
    let best: { field: string; count: number } | null = null;
    for (const [field, count] of counts) {
      if (!best || count > best.count) best = { field, count };
    }
    return best;
  }

  const counts = new Map<string, number>();
  const hardConditions = comparison.requirement.conditions.filter(
    (item) => item.strength === 'hard',
  );
  const alternativeConditions = (comparison.requirement.alternatives ?? []).flatMap(
    (alternative) => alternative.conditions,
  );
  const conditions = hardConditions.length > 0 ? hardConditions : alternativeConditions;
  const hardIds = new Set(conditions.map((item) => item.id));
  const fieldOf = new Map(conditions.map((item) => [item.id, item.field]));
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
  const shared = comparison.requirement.conditions.filter(
    (condition) => condition.strength === 'hard',
  );
  const alternatives = comparison.requirement.alternatives ?? [];
  const allHard = [...shared, ...alternatives.flatMap((alternative) => alternative.conditions)];
  if (!allHard.length) return 'pass';
  const states = new Map(
    comparison.evaluations
      .filter(
        (item) =>
          item.offer_id === offerId &&
          allHard.some((condition) => condition.id === item.condition_id),
      )
      .map((item) => [item.condition_id, item.state]),
  );
  if (shared.some((condition) => states.get(condition.id) === 'fail')) return 'fail';
  if (shared.some((condition) => states.get(condition.id) !== 'pass')) return 'unknown';
  if (!alternatives.length) return 'pass';
  const branchStates = alternatives.map((alternative) => {
    if (alternative.conditions.some((condition) => states.get(condition.id) === 'fail'))
      return 'fail';
    if (alternative.conditions.some((condition) => states.get(condition.id) !== 'pass'))
      return 'unknown';
    return 'pass';
  });
  if (branchStates.includes('pass')) return 'pass';
  return branchStates.includes('unknown') ? 'unknown' : 'fail';
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
  departure_city: ['nơi khởi hành', 'departure city'],
  date_from: ['ngày khởi hành từ', 'departure date from'],
  date_to: ['ngày khởi hành đến', 'departure date through'],
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
