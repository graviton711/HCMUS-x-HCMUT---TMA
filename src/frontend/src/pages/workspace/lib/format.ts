import type { CurrentComparison, CurrentCondition, CurrentEvaluation } from '../../../shared/api';

export function display(value: unknown): string {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function conditionState(comparison: CurrentComparison, offerId: string) {
  const states = comparison.evaluations.filter((item) => item.offer_id === offerId);
  if (states.some((item) => item.state === 'fail')) return 'fail';
  if (states.some((item) => item.state === 'unknown')) return 'unknown';
  return states.length ? 'pass' : 'unknown';
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
