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

export function validSession(v: unknown): v is LocalSession {
  if (!record(v) || typeof v.id !== 'string' || typeof v.title !== 'string' || !validDraft(v.draft))
    return false;
  return (
    typeof v.pinned === 'boolean' &&
    typeof v.createdAt === 'string' &&
    typeof v.updatedAt === 'string' &&
    ['requirementId', 'comparisonId'].every((k) => v[k] === null || typeof v[k] === 'string')
  );
}
