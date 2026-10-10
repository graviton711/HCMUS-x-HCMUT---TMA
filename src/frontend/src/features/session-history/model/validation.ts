import { emptySearchDraft, validMonth, type SearchDraft } from '../../../entities/search-draft';
import type { LocalSession } from './types';

const record = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

export function validDraft(v: unknown): v is SearchDraft {
  if (!record(v)) return false;
  const levels = v.preferenceLevels;
  return (
    Object.entries(emptySearchDraft).every(([key, original]) => {
      const value = v[key];
      if (Array.isArray(original)) return Array.isArray(value);
      if (record(original)) return record(value);
      return typeof value === typeof original;
    }) &&
    ['structured', 'text', 'urls'].includes(String(v.mode)) &&
    ['destinations', 'transport', 'includedServices', 'referenceUrls'].every(
      (key) => Array.isArray(v[key]) && v[key].every((item) => typeof item === 'string'),
    ) &&
    Array.isArray(v.childAges) &&
    Array.isArray(v.departureMonths) &&
    v.departureMonths.length <= 12 &&
    v.departureMonths.every((month) => typeof month === 'string' && validMonth(month)) &&
    v.childAges.every(
      (age) =>
        age === null || (typeof age === 'number' && Number.isInteger(age) && age >= 0 && age <= 17),
    ) &&
    record(levels) &&
    ['cost', 'comfort', 'pace', 'culture'].every(
      (key) =>
        typeof levels[key] === 'number' &&
        Number.isInteger(levels[key]) &&
        levels[key] >= 0 &&
        levels[key] <= 5,
    ) &&
    record(v.strengths) &&
    Object.values(v.strengths).every((value) => value === 'hard' || value === 'soft') &&
    ['any', 'few', 'none'].includes(String(v.shopping)) &&
    ['per_adult', 'per_person', 'group_total'].includes(String(v.budgetBasis))
  );
}

export function validSession(v: unknown): v is LocalSession {
  if (!record(v) || typeof v.id !== 'string' || typeof v.title !== 'string' || !validDraft(v.draft))
    return false;
  return (
    typeof v.pinned === 'boolean' &&
    typeof v.createdAt === 'string' &&
    typeof v.updatedAt === 'string' &&
    [
      'requirementId',
      'proposalId',
      'comparisonId',
      'pendingComparisonId',
      'jobId',
      'pendingMessageId',
    ].every((k) => v[k] === null || typeof v[k] === 'string') &&
    Array.isArray(v.runs) &&
    v.runs.every(
      (r) =>
        record(r) &&
        typeof r.id === 'string' &&
        typeof r.revision === 'number' &&
        typeof r.createdAt === 'string',
    ) &&
    Array.isArray(v.chat) &&
    v.chat.every(
      (m) =>
        record(m) &&
        typeof m.id === 'string' &&
        ['user', 'assistant'].includes(String(m.role)) &&
        typeof m.text === 'string',
    )
  );
}
