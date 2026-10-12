import { emptySearchDraft, type SearchDraft } from '../../../entities/search-draft';
import type { LocalSession } from './types';

const record = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/** Narrowed draft shape. Saved drafts with extra legacy keys are stripped before validation. */
export function validDraft(v: unknown): v is SearchDraft {
  if (!record(v)) return false;
  return (
    Object.entries(emptySearchDraft).every(([key, original]) => {
      const value = v[key];
      if (Array.isArray(original)) return Array.isArray(value);
      return typeof value === typeof original;
    }) &&
    ['structured', 'text'].includes(String(v.mode)) &&
    ['destinations', 'transport'].every(
      (key) => Array.isArray(v[key]) && v[key].every((item) => typeof item === 'string'),
    )
  );
}

export function validChatMsg(v: unknown): boolean {
  if (!record(v) || typeof v.id !== 'string' || typeof v.kind !== 'string') return false;
  if (v.kind === 'user' || v.kind === 'assistant') return typeof v.text === 'string';
  if (v.kind === 'error') {
    return (
      typeof v.text === 'string' && (v.expired === undefined || typeof v.expired === 'boolean')
    );
  }
  if (v.kind === 'choice') {
    if (
      !record(v.choice) ||
      typeof v.choice.question !== 'string' ||
      !Array.isArray(v.choice.options)
    )
      return false;
    return (
      typeof v.choice.allow_custom === 'boolean' &&
      v.choice.options.every(
        (option) =>
          record(option) && typeof option.label === 'string' && typeof option.value === 'string',
      )
    );
  }
  if (v.kind === 'tool_activity') {
    return (
      Array.isArray(v.tools) &&
      v.tools.every(
        (tool) =>
          record(tool) &&
          typeof tool.id === 'string' &&
          typeof tool.name === 'string' &&
          ['running', 'completed', 'error'].includes(String(tool.status)),
      )
    );
  }
  if (v.kind === 'comparison') {
    const comparison = v.comparison;
    return (
      record(comparison) &&
      typeof comparison.id === 'string' &&
      record(comparison.requirement) &&
      Array.isArray(comparison.ranked) &&
      Array.isArray(comparison.near_miss) &&
      Array.isArray(comparison.tour_snapshots) &&
      Array.isArray(comparison.evaluations) &&
      record(comparison.analysis)
    );
  }
  return false;
}

export function validSession(v: unknown): v is LocalSession {
  if (!record(v) || typeof v.id !== 'string' || typeof v.title !== 'string' || !validDraft(v.draft))
    return false;
  return (
    typeof v.pinned === 'boolean' &&
    typeof v.createdAt === 'string' &&
    typeof v.updatedAt === 'string' &&
    Array.isArray(v.messages) &&
    v.messages.every(validChatMsg) &&
    ['requirementId', 'comparisonId', 'agentSessionId'].every(
      (k) => v[k] === null || typeof v[k] === 'string',
    )
  );
}
