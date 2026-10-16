import type { CurrentRequirement } from '../../../shared/api';

/**
 * Drop one hard condition (wherever it lives) plus anything that would dangle:
 * assumptions referencing it and alternative branches left empty. Soft weights are
 * untouched because relaxation options only ever name hard conditions.
 */
export function relaxRequirement(
  requirement: CurrentRequirement,
  conditionId: string,
): CurrentRequirement {
  const remaining = new Set<string>();
  const conditions = (requirement.conditions ?? []).filter((condition) => {
    const keep = condition.id !== conditionId;
    if (keep) remaining.add(condition.id);
    return keep;
  });
  const alternatives = (requirement.alternatives ?? [])
    .map((branch) => ({
      ...branch,
      conditions: branch.conditions.filter((condition) => {
        const keep = condition.id !== conditionId;
        if (keep) remaining.add(condition.id);
        return keep;
      }),
    }))
    .filter((branch) => branch.conditions.length > 0);
  const assumptions = (requirement.assumptions ?? []).filter((assumption) =>
    (assumption.condition_ids ?? []).every((id) => remaining.has(id)),
  );
  return { ...requirement, conditions, alternatives, assumptions };
}
