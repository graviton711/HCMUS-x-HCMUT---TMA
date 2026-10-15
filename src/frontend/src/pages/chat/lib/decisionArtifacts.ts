import type { CurrentComparison, CurrentRequirement } from '../../../shared/api';
import type { ChatMsg } from '../../../features/chat';

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (typeof value === 'object' && value !== null) {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(record[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}

/** Compare decision content while ignoring the server identity of a requirement. */
export function sameDecision(left: CurrentRequirement, right: CurrentRequirement): boolean {
  const withoutServerId = (requirement: CurrentRequirement) => ({
    ...Object.fromEntries(Object.entries(requirement).filter(([key]) => key !== 'id')),
    alternatives: requirement.alternatives ?? [],
    assumptions: requirement.assumptions ?? [],
  });
  const leftDecision = withoutServerId(left);
  const rightDecision = withoutServerId(right);
  return canonical(leftDecision) === canonical(rightDecision);
}

export function latestDecisionArtifact(messages: ChatMsg[]) {
  return (
    [...messages]
      .reverse()
      .find(
        (message): message is Extract<ChatMsg, { kind: 'decision_draft' | 'comparison' }> =>
          message.kind === 'decision_draft' || message.kind === 'comparison',
      ) ?? null
  );
}

export function draftForComparison(messages: ChatMsg[], comparison: CurrentComparison) {
  return (
    [...messages]
      .reverse()
      .find(
        (message): message is Extract<ChatMsg, { kind: 'decision_draft' }> =>
          message.kind === 'decision_draft' &&
          sameDecision(message.requirement, comparison.requirement),
      ) ?? null
  );
}

/** New comparisons include the metric contract even when no candidates have metric rows. */
export function hasDecisionMetrics(comparison: CurrentComparison) {
  return (
    Array.isArray(comparison.decision_views) &&
    comparison.decision_views.length >= 3 &&
    Array.isArray(comparison.metric_profiles) &&
    Array.isArray(comparison.decision_options)
  );
}
