import { describe, expect, it } from 'vitest';
import {
  buildCreateRequirement,
  buildEdits,
  canonicalUrls,
  emptyForm,
  FormValidationError,
  formFromRequirement,
} from './form';
import type { FormValues } from './form';
import * as contracts from './contracts';
import type { ComparisonResult, Condition, Requirement } from './types';

const predicate = (id: string, field: string, amount: number): Condition => ({
  id,
  field,
  operator: 'near',
  strength: 'soft',
  value: { kind: 'number', amount },
  sources: [{ kind: 'form', field_path: `conditions.${id}` }],
});
function requirement(): Requirement {
  return {
    schema_version: '2.0-draft',
    policy_version: 'requirements-v2.2',
    id: 'req_1',
    revision: 1,
    input_kind: 'structured',
    mode: 'discover',
    timezone: 'Asia/Ho_Chi_Minh',
    messages: [],
    targets: [],
    party: { adults: 2, children: [{ id: 'child_existing', age: 8 }] },
    conditions: [
      predicate('duration_existing', 'duration_days', 5),
      predicate('hotel_existing', 'hotel_stars_min', 4),
    ],
    hard_tree: { kind: 'all', children: [] },
    preference_tree: {
      kind: 'any',
      children: [
        { kind: 'predicate', condition_id: 'duration_existing' },
        { kind: 'predicate', condition_id: 'hotel_existing' },
      ],
    },
    clarifications: [],
    readiness: {
      status: 'ready',
      can_collect_data: true,
      can_evaluate_hard_constraints: true,
      reasons: [],
      blockers: [],
      scope_coverage: 'complete',
      unassessed_preferences: [],
    },
    issues: [],
    preference_levels: null,
    reference_urls: [],
    notes: '',
    provenance: {},
    created_at: '2026-10-08T00:00:00Z',
  };
}
const structuredValues = (): FormValues => ({
  ...structuredClone(emptyForm),
  destinations: ['country:jp'],
  departureOrigin: 'city:vn:hcmc',
  departureDate: '2026-11-10',
  adults: 2,
  budget: '35000000',
});

describe('Form serialization', () => {
  it('defaults the personalized budget to hard while leaving optional preferences soft', () => {
    const input = buildCreateRequirement({ ...structuredValues(), durationDays: '5' }).input;
    if (input.kind !== 'structured') throw new Error('Expected structured input');
    expect(input.form.conditions.find((c) => c.field === 'estimated_cost')?.strength).toBe('hard');
    expect(input.form.conditions.find((c) => c.field === 'duration_days')?.strength).toBe('soft');
    const legacy = buildCreateRequirement({
      ...structuredValues(),
      strengths: { estimated_cost: 'soft' },
    }).input;
    if (legacy.kind !== 'structured') throw new Error('Expected structured input');
    expect(legacy.form.conditions.find((c) => c.field === 'estimated_cost')?.strength).toBe('soft');
  });
  it('requires explicit structured inputs and does not infer them from URLs', () => {
    expect(() => buildCreateRequirement(emptyForm)).toThrow(FormValidationError);
    const urlOnly = {
      ...structuredClone(emptyForm),
      mode: 'urls' as const,
      referenceUrls: ['https://example.com/tour'],
    };
    expect(buildCreateRequirement(urlOnly)).toEqual({
      input: { kind: 'urls' },
      reference_urls: ['https://example.com/tour'],
      timezone: 'Asia/Ho_Chi_Minh',
    });
  });

  it('serializes distinct shopping preferences without a fabricated cutoff', () => {
    const few = buildCreateRequirement({ ...structuredValues(), shopping: 'few' });
    const none = buildCreateRequirement({ ...structuredValues(), shopping: 'none' });
    expect(few.input.kind).toBe('structured');
    if (few.input.kind !== 'structured' || none.input.kind !== 'structured')
      throw new Error('Unexpected request kind');
    expect(few.input.form.conditions.find((c) => c.field === 'shopping_stops')).toMatchObject({
      operator: 'prefer_low',
      strength: 'soft',
      value: { kind: 'number', amount: 0 },
    });
    expect(none.input.form.conditions.find((c) => c.field === 'shopping_stops')).toMatchObject({
      operator: 'eq',
      strength: 'hard',
      value: { kind: 'number', amount: 0 },
    });
  });

  it('keeps predicate IDs, OR tree, unknown conditions and child identities when editing unrelated controls', () => {
    const r = requirement(),
      values = formFromRequirement(r);
    const originalTree = structuredClone(r.preference_tree);
    expect(buildEdits(values, r)).toEqual([]);
    values.durationDays = '7';
    values.childAges = [10];
    expect(buildEdits(values, r)).toEqual([
      {
        op: 'replace_condition_value',
        condition_id: 'duration_existing',
        value: { kind: 'number', amount: 7 },
      },
      { op: 'replace_party', party: { adults: 2, children: [{ id: 'child_existing', age: 10 }] } },
    ]);
    expect(r.preference_tree).toEqual(originalTree);
    expect(r.conditions[1].id).toBe('hotel_existing');
  });

  it('preserves foreign and ranged budgets for other edits and blocks silent currency/coverage conversion', () => {
    const r = requirement();
    r.conditions.push({
      id: 'budget_existing',
      field: 'estimated_cost',
      operator: 'between',
      strength: 'soft',
      value: {
        kind: 'budget',
        amount: '2000.50',
        upper: '3000.50',
        currency: 'USD',
        basis: 'group_total',
        coverage: 'trip_total',
      },
      sources: [{ kind: 'form', field_path: 'conditions.budget_existing' }],
    });
    const values = formFromRequirement(r);
    values.notes = 'Keep the original budget meaning.';
    expect(buildEdits(values, r)).toEqual([
      { op: 'set_notes', notes: 'Keep the original budget meaning.' },
    ]);
    values.budget = '2500';
    expect(() => buildEdits(values, r)).toThrow(FormValidationError);
    expect(r.conditions.at(-1)?.value).toMatchObject({
      currency: 'USD',
      basis: 'group_total',
      coverage: 'trip_total',
      upper: '3000.50',
    });
  });

  it('refuses to flatten multiple predicates of the same field into one control', () => {
    const r = requirement();
    r.conditions.push(predicate('duration_other', 'duration_days', 6));
    const values = formFromRequirement(r);
    values.durationDays = '8';
    expect(() => buildEdits(values, r)).toThrow(FormValidationError);
  });

  it('normalizes URL fragments/duplicates and rejects credentials, invalid dates and child ages', () => {
    expect(canonicalUrls(['https://EXAMPLE.com/tour#price', 'https://example.com/tour'])).toEqual([
      'https://example.com/tour',
    ]);
    expect(() => canonicalUrls(['https://user:password@example.com'])).toThrow(FormValidationError);
    expect(() =>
      buildCreateRequirement({ ...structuredValues(), departureDate: '2026-02-31' }),
    ).toThrow(FormValidationError);
    expect(() => buildCreateRequirement({ ...structuredValues(), childAges: [18] })).toThrow(
      FormValidationError,
    );
  });

  it('checks revision and complete matrix bindings at the response boundary', () => {
    const r = requirement();
    expect(() => contracts.requirement(r)).not.toThrow();
    const comparison: ComparisonResult = {
      id: 'comparison_1',
      requirement_id: r.id,
      revision: 2,
      requirement_snapshot: r,
      origin: 'source',
      evaluated_at: r.created_at,
      policy_versions: {},
      columns: [],
      rows: [],
      cells: [],
      evaluations: [],
      recommendations: {
        kind: 'similar',
        candidate_ids: [],
        items: [],
        ranking_policy_version: 'rank-v2.3-bounds',
        unsupported_dimensions: [],
        needs_verification: [],
        excluded_tour_ids: [],
        candidate_limit: 20,
        truncated: false,
        evaluated_count: 0,
      },
      analysis: {
        metrics: [],
        semantic_assessment: { state: 'skipped', items: [] },
        retrieval: {},
        candidate_pool: [],
        metric_availability: [],
        claims: [],
      },
      source_coverage: [],
      warnings: [],
      empty_reason: 'NO_CANDIDATES',
    };
    expect(() => contracts.comparisonResult(comparison)).toThrow(contracts.ContractError);
    comparison.revision = 1;
    expect(() => contracts.comparisonResult(comparison)).not.toThrow();
    comparison.recommendations.candidate_ids = ['missing'];
    expect(() => contracts.comparisonResult(comparison)).toThrow(contracts.ContractError);
  });
});
