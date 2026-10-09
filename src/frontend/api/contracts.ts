import type {
  ComparisonResult,
  Envelope,
  JsonObject,
  JsonValue,
  Requirement,
  WhatIfAnalysis,
} from './types';

export class ContractError extends Error {
  constructor(path: string) {
    super(`Response API không đúng contract tại ${path}.`);
    this.name = 'ContractError';
  }
}
export type Validator = (value: unknown, path?: string) => void;
const fail = (path = 'data'): never => {
  throw new ContractError(path);
};
export function record(value: unknown, path = 'data'): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return fail(path);
  return value as Record<string, unknown>;
}
const string: Validator = (v, p) => {
  if (typeof v !== 'string') fail(p);
};
const number: Validator = (v, p) => {
  if (typeof v !== 'number' || !Number.isFinite(v)) fail(p);
};
const integer: Validator = (v, p) => {
  number(v, p);
  if (!Number.isInteger(v)) fail(p);
};
const boolean: Validator = (v, p) => {
  if (typeof v !== 'boolean') fail(p);
};
const literal =
  (...choices: (string | number | boolean | null)[]): Validator =>
  (v, p) => {
    if (!choices.includes(v as string)) fail(p);
  };
const optional =
  (schema: Validator): Validator =>
  (v, p) => {
    if (v !== undefined) schema(v, p);
  };
const nullable =
  (schema: Validator): Validator =>
  (v, p) => {
    if (v !== null) schema(v, p);
  };
const list =
  (schema: Validator): Validator =>
  (v, p = 'data') => {
    if (!Array.isArray(v)) return fail(p);
    v.forEach((item, i) => schema(item, `${p}[${i}]`));
  };
const shape =
  (fields: Record<string, Validator>): Validator =>
  (v, p = 'data') => {
    const r = record(v, p);
    for (const [key, schema] of Object.entries(fields)) schema(r[key], `${p}.${key}`);
  };
const dictionary =
  (schema: Validator): Validator =>
  (v, p = 'data') => {
    for (const [key, entry] of Object.entries(record(v, p))) schema(entry, `${p}.${key}`);
  };
const union =
  (...schemas: Validator[]): Validator =>
  (v, p) => {
    for (const schema of schemas) {
      try {
        schema(v, p);
        return;
      } catch (error) {
        if (!(error instanceof ContractError)) throw error;
      }
    }
    fail(p);
  };
const strings = list(string);
const maybeString = nullable(string);
const maybeNumber = nullable(number);
export const json: Validator = (v, p = 'data') => {
  if (v === null || typeof v === 'string' || typeof v === 'boolean') return;
  if (typeof v === 'number') {
    number(v, p);
    return;
  }
  if (Array.isArray(v)) {
    list(json)(v, p);
    return;
  }
  dictionary(json)(v, p);
};
export function jsonObject(value: unknown): JsonObject {
  dictionary(json)(value);
  return value as JsonObject;
}
export function jsonValue(value: unknown): JsonValue {
  json(value);
  return value as JsonValue;
}
export function envelope(value: unknown): Envelope<unknown> {
  shape({ schema_version: literal('2.0-draft'), request_id: string, data: json })(
    value,
    'response',
  );
  return value as Envelope<unknown>;
}
export const errorPayload = shape({
  code: string,
  message: string,
  retryable: boolean,
  details: dictionary(json),
  field_path: optional(maybeString),
  trace_id: optional(string),
});
export const session = shape({
  id: string,
  session_id: string,
  token: string,
  token_type: string,
  expires_at: string,
});
export const health = shape({
  status: literal('ok', 'degraded'),
  data_origin: literal('source', 'synthetic'),
  data_provider: literal('fixture', 'http', 'supabase'),
  worker_enabled: boolean,
  schema_version: string,
  api_versions: strings,
  database_schema_version: integer,
});
const catalogEntry = shape({ id: string, label: string, parent_id: optional(maybeString) });
const preferenceLevel = shape({ level: integer, origin: literal('user', 'system_default') });
const preferences = shape({
  cost: preferenceLevel,
  comfort: preferenceLevel,
  pace: preferenceLevel,
  culture: preferenceLevel,
});
export const catalog = shape({
  catalog_version: string,
  destinations: list(catalogEntry),
  origins: list(catalogEntry),
  fields: list(
    shape({
      id: string,
      operators: strings,
      processing_methods: strings,
      strength_choices: strings,
    }),
  ),
  required_by_input_kind: dictionary(strings),
  defaults: dictionary(json),
  qualitative_policy: dictionary(json),
  assessment_policy: dictionary(json),
  transports: list(catalogEntry),
  tour_types: list(catalogEntry),
  preference_dimensions: list(
    shape({
      id: literal('cost', 'comfort', 'pace', 'culture'),
      min: number,
      max: number,
      default: preferenceLevel,
      supported: boolean,
    }),
  ),
  limits: shape({
    reference_urls: integer,
    recommendations: integer,
    candidate_limit_default: integer,
    text_characters: integer,
    contact_characters: integer,
    page_default: integer,
    page_max: integer,
    body_bytes: integer,
  }),
  upstream_contract: string,
});
const money = union(number, string);
const value: Validator = (v, p) => {
  const r = record(v, p);
  switch (r.kind) {
    case 'number':
      shape({ kind: literal('number'), amount: integer, upper: optional(nullable(integer)) })(v, p);
      break;
    case 'set':
      shape({ kind: literal('set'), items: strings })(v, p);
      break;
    case 'date':
      shape({ kind: literal('date'), value: string, upper: optional(maybeString) })(v, p);
      break;
    case 'budget':
      shape({
        kind: literal('budget'),
        amount: money,
        upper: optional(nullable(money)),
        currency: optional(maybeString),
        basis: optional(nullable(literal('per_adult', 'per_person', 'group_total'))),
        coverage: optional(literal('tour_price', 'trip_total')),
        coverage_origin: optional(literal('explicit', 'system_default')),
      })(v, p);
      break;
    case 'unresolved':
      shape({ kind: literal('unresolved'), raw: string, reason: string })(v, p);
      break;
    case 'entities':
      shape({
        kind: literal('entities'),
        catalog_version: string,
        members: list(
          shape({
            raw: string,
            entity_type: literal('place', 'transport', 'service', 'supplier', 'tour_type'),
            entity_id: maybeString,
            status: literal('resolved', 'catalog_missing'),
          }),
        ),
      })(v, p);
      break;
    case 'temporal':
      shape({
        kind: literal('temporal'),
        raw: string,
        calendar: literal('gregorian', 'vietnamese_lunar', 'unresolved'),
        group_id: string,
        role: literal('start', 'end', 'single'),
        semantics: literal('availability', 'exact', 'departure_window', 'ambiguous', 'single'),
        resolved_date: optional(maybeString),
        reason: optional(maybeString),
      })(v, p);
      break;
    case 'qualitative':
      shape({
        kind: literal('qualitative'),
        concept: literal('supplier_reputation', 'service_quality', 'price_value', 'nature'),
        raw: string,
        metric_policy: optional(maybeString),
      })(v, p);
      break;
    default:
      fail(`${p}.kind`);
  }
};
const sourceReference = shape({
  kind: literal('text', 'form', 'system_default'),
  message_id: optional(maybeString),
  quote: optional(maybeString),
  start: optional(nullable(integer)),
  end: optional(nullable(integer)),
  field_path: optional(maybeString),
  submitted_value: optional(json),
  rule: optional(maybeString),
});
const condition = shape({
  id: string,
  field: string,
  operator: string,
  value,
  strength: literal('hard', 'soft', 'unresolved'),
  scope: optional(nullable(literal('main_journey', 'itinerary'))),
  sources: list(sourceReference),
  trace: optional(nullable(shape({ raw_values: strings, rule: string, version: string }))),
});
const party = shape({
  adults: nullable(integer),
  children: list(shape({ id: string, age: nullable(integer) })),
  rooming: optional(maybeString),
  sources: optional(list(sourceReference)),
});
const tree: Validator = (v, p) => {
  const r = record(v, p);
  shape({
    kind: literal('all', 'any', 'predicate'),
    condition_id: optional(maybeString),
    children: optional(list(tree)),
  })(v, p);
  if (r.kind === 'predicate' && typeof r.condition_id !== 'string') fail(p);
};
const clarification = shape({
  id: string,
  field_path: string,
  reason_code: string,
  question: string,
  options: strings,
  blocking: boolean,
});
const requirementShape = shape({
  schema_version: literal('2.0-draft'),
  policy_version: string,
  id: string,
  revision: integer,
  input_kind: literal('structured', 'text', 'urls'),
  mode: literal('discover', 'compare_urls', 'hybrid'),
  timezone: string,
  messages: list(shape({ id: string, text: string, received_at: string })),
  targets: list(shape({ target_id: string, url: string })),
  party,
  conditions: list(condition),
  hard_tree: tree,
  preference_tree: tree,
  clarifications: list(clarification),
  readiness: shape({
    can_confirm: optional(boolean),
    can_search: optional(boolean),
    completeness: optional(dictionary(json)),
    status: literal('ready', 'needs_clarification', 'unsupported'),
    can_collect_data: boolean,
    can_evaluate_hard_constraints: boolean,
    reasons: strings,
    blockers: strings,
    scope_coverage: literal('complete', 'partial', 'unavailable'),
    unassessed_preferences: strings,
  }),
  issues: list(
    shape({
      reason_code: string,
      responsibility: literal('user', 'backend', 'data'),
      condition_ids: strings,
      explanation: string,
      blocking: boolean,
    }),
  ),
  preference_levels: nullable(preferences),
  reference_urls: strings,
  notes: string,
  provenance: dictionary(json),
  created_at: string,
  active_proposal: optional(nullable(shape({ id: string, version: integer }))),
  latest_job_id: optional(maybeString),
  latest_comparison_id: optional(maybeString),
  latest_comparison_job_id: optional(maybeString),
});
export const requirement: Validator = (v, p = 'data') => {
  requirementShape(v, p);
  const r = v as Requirement;
  if (
    r.revision < 0 ||
    r.reference_urls.length !== r.targets.length ||
    r.reference_urls.some((url, i) => url !== r.targets[i].url)
  )
    fail(`${p}.targets`);
  if (r.revision === 0 && (r.conditions.length || r.messages.length)) fail(`${p}.revision`);
};
export const acceptedRequirement = shape({
  requirement_id: string,
  revision: literal(0),
  proposal_id: string,
  job_id: optional(string),
  proposal_version: optional(integer),
  status: literal('queued', 'pending', 'needs_clarification'),
});
export const createRequirement = union(requirement, acceptedRequirement);
export const proposal = shape({
  id: string,
  version: integer,
  requirement_id: string,
  base_revision: integer,
  status: literal(
    'pending',
    'needs_clarification',
    'confirmed',
    'cancelled',
    'superseded',
    'expired',
  ),
  expires_at: string,
  preview: requirement,
  changes: list(
    shape({
      id: string,
      path: string,
      condition_id: maybeString,
      before: json,
      after: json,
      origin: literal('user_edit', 'chat_inference'),
      reason: string,
    }),
  ),
  clarifications: list(clarification),
  requested_action: nullable(literal('search', 'next_group')),
  parse_job_id: maybeString,
});
export const acceptedProposal = shape({
  proposal_id: string,
  proposal_version: integer,
  job_id: string,
  status: literal('queued'),
});
export const createProposal = union(proposal, acceptedProposal);
export const cancelProposal = shape({
  proposal_id: string,
  status: literal('cancelled'),
  committed_requirement: requirement,
});
export const acceptedComparison = shape({
  comparison_id: string,
  job_id: string,
  requirement_id: string,
  revision: integer,
  status: literal('queued'),
});
const dataState = literal('present', 'missing', 'conflicting', 'invalid', 'unsupported');
const verification = literal(
  'supplier_published',
  'independently_verified',
  'catalog_validated',
  'unverified',
);
const completeness = literal('complete', 'partial', 'unknown');
const fact = (contents: Validator) =>
  shape({
    value: nullable(contents),
    raw_value: maybeString,
    data_state: dataState,
    verification,
    completeness,
    observed_at: string,
    evidence_ids: strings,
    unit: maybeString,
    scope: maybeString,
    normalization_rule: maybeString,
    reason: maybeString,
  });
const applicability = list(
  shape({ field: literal('adults', 'children_count', 'rooming', 'unresolved'), value: money }),
);
const price = shape({
  quote_id: string,
  kind: literal('exact', 'from', 'range'),
  amount: money,
  upper_amount: nullable(money),
  currency: string,
  basis: literal('per_adult', 'per_child', 'per_infant', 'per_room', 'per_group'),
  coverage: literal('tour_price', 'trip_total', 'unspecified'),
  age_min: nullable(integer),
  age_max_exclusive: nullable(integer),
  applicability,
});
const charge = shape({
  charge_id: string,
  amount: money,
  currency: string,
  basis: literal('per_adult', 'per_child', 'per_person', 'per_group', 'per_room'),
  required: nullable(boolean),
  applicability,
});
const offer = shape({
  snapshot_id: string,
  offer_id: string,
  tour_snapshot_id: string,
  fields: dictionary(fact(json)),
  price_quotes: list(fact(price)),
  extra_charges: list(fact(charge)),
  pricing_complete: nullable(fact(boolean)),
  catalog_fields: dictionary(fact(json)),
});
const column = shape({
  id: string,
  candidate_id: maybeString,
  tour_id: maybeString,
  tour_snapshot_id: maybeString,
  offer_snapshot_id: maybeString,
  selected_offer_snapshot_id: maybeString,
  title: maybeString,
  title_reason: optional(maybeString),
  supplier: nullable(shape({ id: string, display_name: string })),
  canonical_url: string,
  origin: literal('reference', 'discovery', 'both'),
  target_ids: strings,
  source_ids: strings,
  offer_reason: maybeString,
  offer_options: list(offer),
  eligible_offer_snapshot_ids: strings,
  offer_assessments: list(
    shape({ offer_snapshot_id: string, hard_status: maybeString, evaluation_ids: strings }),
  ),
  offers_complete: boolean,
});
const row = shape({
  id: string,
  field: string,
  label: string,
  scope: literal('tour', 'offer', 'cost', 'evaluation'),
  value_type: literal('date', 'number', 'set', 'text', 'boolean', 'price_list'),
  unit: maybeString,
  order: integer,
  condition_ids: strings,
});
const cell = shape({
  row_id: string,
  column_id: string,
  value: json,
  raw_value: list(maybeString),
  data_state: dataState,
  verification,
  completeness,
  observed_at: maybeString,
  freshness: shape({
    state: literal('fresh', 'stale', 'unknown'),
    checked_at: string,
    expires_at: maybeString,
    policy_version: string,
  }),
  evidence_ids: strings,
  reason_code: maybeString,
  evaluation_ids: strings,
});
const evaluation = shape({
  id: string,
  condition_id: string,
  candidate_id: string,
  field: string,
  strength: literal('hard', 'soft', 'unresolved'),
  expected: json,
  actual: json,
  status: literal('pass', 'fail', 'unknown', 'not_evaluated'),
  reason_code: string,
  evidence_ids: strings,
  data_quality: dictionary(json),
  offer_snapshot_id: maybeString,
});
const recommendation = shape({
  candidate_id: string,
  rank: integer,
  score: maybeNumber,
  coverage: maybeNumber,
  score_interval: shape({ lower: maybeNumber, upper: maybeNumber }),
  ranking_basis: string,
  rank_status: string,
  eligible_offer_snapshot_ids: strings,
  contributions: list(dictionary(json)),
  evaluation_ids: strings,
  reason: string,
});
const recommendations = shape({
  kind: literal('personalized', 'similar'),
  candidate_ids: strings,
  items: list(recommendation),
  ranking_policy_version: string,
  unsupported_dimensions: strings,
  needs_verification: strings,
  excluded_tour_ids: strings,
  candidate_limit: integer,
  truncated: boolean,
  evaluated_count: integer,
});
const metric = shape({
  id: string,
  operation: literal('subtract', 'multiply'),
  operands: list(
    shape({
      candidate_id: optional(string),
      snapshot_id: optional(string),
      requirement_id: optional(string),
      revision: optional(integer),
      field: string,
      quote_id: optional(string),
      value: json,
      evidence_ids: strings,
    }),
  ),
  result: nullable(money),
  currency: string,
  basis: string,
  coverage: string,
  comparable: boolean,
  limitations: strings,
  evidence_ids: strings,
});
const claim = shape({
  id: string,
  metric_ids: strings,
  text: string,
  evidence_ids: strings,
  limitations: strings,
});
const semanticItem = shape({
  candidate_id: string,
  condition_id: string,
  tour_snapshot_id: string,
  status: string,
  evidence_ids: strings,
  usable_for_ranking: boolean,
});
const analysis = shape({
  metrics: list(metric),
  semantic_assessment: shape({
    state: string,
    items: list(semanticItem),
    reason_code: optional(maybeString),
  }),
  retrieval: dictionary(json),
  candidate_pool: list(
    shape({ candidate_id: string, tour_snapshot_id: string, hard_status: maybeString }),
  ),
  metric_availability: list(dictionary(json)),
  claims: list(claim),
});
const sourceCoverage = shape({
  source_id: string,
  target_id: maybeString,
  status: literal('ok', 'partial', 'blocked', 'unsupported', 'timeout', 'error'),
  reason_code: maybeString,
  tour_snapshot_ids: strings,
  offer_snapshot_ids: strings,
  truncated: boolean,
});
const warning = shape({
  code: string,
  source_id: string,
  target_id: maybeString,
  snapshot_id: maybeString,
  field_path: maybeString,
  explanation: string,
  retryable: boolean,
});
const comparisonResultShape = shape({
  id: string,
  requirement_id: string,
  revision: integer,
  requirement_snapshot: requirement,
  origin: literal('source', 'synthetic'),
  evaluated_at: string,
  policy_versions: dictionary(string),
  columns: list(column),
  rows: list(row),
  cells: list(cell),
  evaluations: list(evaluation),
  recommendations,
  analysis,
  source_coverage: list(sourceCoverage),
  warnings: list(warning),
  empty_reason: maybeString,
});
export const comparisonResult: Validator = (v, p = 'data') => {
  comparisonResultShape(v, p);
  const r = v as ComparisonResult;
  if (
    r.requirement_id !== r.requirement_snapshot.id ||
    r.revision !== r.requirement_snapshot.revision
  )
    fail(`${p}.requirement_snapshot`);
  const cols = new Set(r.columns.map((c) => c.id)),
    rows = new Set(r.rows.map((row) => row.id)),
    pairs = new Set(r.cells.map((c) => `${c.row_id}\u0000${c.column_id}`)),
    evals = new Set(r.evaluations.map((e) => e.id));
  if (
    cols.size !== r.columns.length ||
    rows.size !== r.rows.length ||
    pairs.size !== r.cells.length ||
    pairs.size !== cols.size * rows.size ||
    evals.size !== r.evaluations.length
  )
    fail(`${p}.cells`);
  if (
    r.cells.some(
      (c) =>
        !cols.has(c.column_id) ||
        !rows.has(c.row_id) ||
        c.evaluation_ids.some((id) => !evals.has(id)),
    )
  )
    fail(`${p}.cells`);
  const ids = r.recommendations.candidate_ids;
  if (ids.length > 3 || new Set(ids).size !== ids.length || ids.some((id) => !cols.has(id)))
    fail(`${p}.recommendations`);
  for (const col of r.columns) {
    const options = new Set(col.offer_options.map((o) => o.snapshot_id));
    if (
      col.offer_snapshot_id !== col.selected_offer_snapshot_id ||
      col.offer_options.some((o) => o.tour_snapshot_id !== col.tour_snapshot_id) ||
      (col.offer_snapshot_id && !options.has(col.offer_snapshot_id)) ||
      col.eligible_offer_snapshot_ids.some((id) => !options.has(id))
    )
      fail(`${p}.columns.${col.id}`);
  }
};
export const comparison = shape({
  id: string,
  status: literal('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled'),
  result: nullable(comparisonResult),
});
export const job = shape({
  id: string,
  resource_id: string,
  kind: string,
  status: literal('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled'),
  phase: string,
  stage: string,
  resource_ref: string,
  created_at: string,
  deadline_at: string,
  completed_at: maybeString,
  error: nullable(errorPayload),
  metrics: nullable(dictionary(json)),
});
export const events = shape({
  items: list(
    shape({
      seq: integer,
      job_id: string,
      stage: string,
      status: literal('started', 'completed', 'partial', 'failed', 'cancelled', 'skipped'),
      occurred_at: string,
      source_id: maybeString,
      summary: string,
      counts: nullable(dictionary(integer)),
      error_code: maybeString,
    }),
  ),
  next_seq: integer,
  has_more: boolean,
});
export const cancelJob = shape({
  job_id: string,
  status: literal('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled'),
});
export const evidence = shape({
  id: string,
  snapshot_id: string,
  url: string,
  publisher: string,
  method: literal('json_ld', 'json', 'api', 'html', 'synthetic_fixture', 'database_record'),
  raw_quote: string,
  observed_at: string,
  record_ref: optional(
    nullable(
      shape({
        table: literal('tours', 'offers'),
        record_key: string,
        field: string,
        content_hash: string,
      }),
    ),
  ),
  source_url: string,
  source_id: maybeString,
  locator: shape({
    section_title: maybeString,
    element_id: maybeString,
    css_selector: maybeString,
    text_quote: shape({ exact: maybeString, prefix: maybeString, suffix: maybeString }),
    upstream_locator: string,
  }),
  deep_link: shape({
    url: maybeString,
    method: literal('text_fragment', 'page'),
    status: literal('best_effort', 'unavailable'),
    verified_at: maybeString,
    reason: maybeString,
  }),
  retained_excerpt_url: maybeString,
  quality: shape({
    origin: literal('source', 'synthetic'),
    verification,
    independently_verified: boolean,
    provenance_kind: literal('database_record', 'website_excerpt'),
  }),
});
export const acceptedMessage = shape({
  message_id: string,
  status: literal('queued'),
  job_id: string,
});
export const chatOutcome = shape({
  message_id: string,
  intent: literal('answer', 'edit', 'search', 'next_group', 'clarify'),
  requested_action: nullable(literal('search', 'next_group')),
  proposal_id: maybeString,
  proposal_version: optional(integer),
  job_id: optional(string),
  status: optional(literal('queued')),
  answer: nullable(
    shape({
      text: string,
      comparison_id: optional(string),
      revision: optional(integer),
      metrics: optional(list(metric)),
      evaluations: optional(list(evaluation)),
    }),
  ),
});
export const message = shape({ accepted: acceptedMessage, result: nullable(chatOutcome) });
export const contact = shape({
  ticket_id: string,
  status: literal('new', 'in_progress', 'resolved'),
  created_at: string,
});

export const historyMetadata = shape({
  version: integer,
  title: string,
  pinned: boolean,
  archived: boolean,
  updated_at: maybeString,
});
const historyItem = shape({
  requirement_id: string,
  revision: integer,
  status: string,
  title: string,
  pinned: boolean,
  version: integer,
  created_at: string,
  updated_at: string,
  proposal_id: maybeString,
  comparison_id: maybeString,
  pending_comparison_id: maybeString,
  job_id: maybeString,
  analysis_id: maybeString,
  pending_message_id: maybeString,
  runs: list(shape({ id: string, revision: integer, created_at: string })),
  runs_limited: boolean,
});
export const history = shape({
  items: list(historyItem),
  next_cursor: maybeString,
  retention_days: integer,
});
export const historyDetail: Validator = (v, p = 'data') => {
  historyItem(v, p);
  shape({
    requirement,
    transcript: shape({
      items: list(
        shape({
          id: string,
          role: literal('user', 'assistant'),
          text: string,
          occurred_at: string,
        }),
      ),
      limited: boolean,
    }),
  })(v, p);
  const d = record(v, p);
  if (record(d.requirement, p).id !== d.requirement_id) fail(p);
};
export const linkedHistory = shape({ linked_requirements: integer });
const nonnegative: Validator = (v, p) => {
  integer(v, p);
  if ((v as number) < 0) fail(p);
};
const population: Validator = (v, p = 'population') => {
  shape({
    eligible: nonnegative,
    ineligible: nonnegative,
    unknown: nonnegative,
    eligible_candidate_ids: strings,
    has_hard_constraints: boolean,
  })(v, p);
  const r = record(v, p);
  if (new Set(r.eligible_candidate_ids as string[]).size !== r.eligible) fail(p);
};
const whatIfRank = shape({
  candidate_id: string,
  rank: integer,
  score_lower: maybeNumber,
  score_upper: maybeNumber,
  coverage: maybeNumber,
  tied: boolean,
});
const scenario = shape({
  id: string,
  kind: literal('remove_hard_group', 'remove_soft_group', 'relax_bound', 'remove_hard_pair'),
  group_ids: strings,
  condition_ids: strings,
  label: string,
  state: literal('measured', 'insufficient_data'),
  population,
  additional_candidate_ids: strings,
  proven_blocked_candidate_ids: strings,
  previously_unknown_candidate_ids: strings,
  joint_only_candidate_ids: strings,
  restriction_ratio: shape({
    state: literal('computed', 'blocked', 'not_applicable'),
    numerator: nonnegative,
    denominator: nonnegative,
    percent: maybeNumber,
    reason_code: maybeString,
    meaning: string,
  }),
  top_before: list(whatIfRank),
  top_after: list(whatIfRank),
  top_changed: boolean,
  rank_changes: list(
    shape({
      candidate_id: string,
      before: whatIfRank,
      after: whatIfRank,
      rank_delta: integer,
      evidence_ids: strings,
    }),
  ),
  rank_changes_truncated: boolean,
  witnesses: list(
    shape({
      candidate_id: string,
      title: maybeString,
      canonical_url: string,
      tour_snapshot_id: string,
      offer_snapshot_id: maybeString,
      original_status: literal('pass', 'fail', 'unknown'),
      original_evaluations: list(dictionary(json)),
      scenario_evaluations: list(dictionary(json)),
      evidence_ids: strings,
    }),
  ),
  witnesses_truncated: boolean,
  edits: list(dictionary(json)),
  tradeoffs: list(dictionary(json)),
  limitations: strings,
  minimal_within_tested_subsets: boolean,
  insight: string,
});
export const whatIfAnalysis: Validator = (v, p = 'data') => {
  shape({
    id: string,
    comparison_id: string,
    requirement_id: string,
    revision: integer,
    policy_version: string,
    origin: literal('source', 'synthetic'),
    evaluated_at: string,
    scope: dictionary(json),
    baseline: population,
    baseline_top: list(whatIfRank),
    groups: list(
      shape({
        id: string,
        strength: literal('hard', 'soft'),
        condition_ids: strings,
        fields: strings,
        label: string,
      }),
    ),
    scenarios: list(scenario),
    candidates: list(dictionary(json)),
    semantic_assessment: dictionary(json),
    explanation: dictionary(json),
    limits: dictionary(json),
    limitations: strings,
  })(v, p);
  const a = v as WhatIfAnalysis;
  const ids = new Set(a.candidates.map((c) => c.candidate_id));
  const groups = new Map(a.groups.map((g) => [g.id, g.condition_ids]));
  const same = (x: string[], y: string[]) =>
    new Set(x).size === new Set(y).size && x.every((i) => y.includes(i));
  if (
    a.revision < 1 ||
    ids.size !== a.candidates.length ||
    groups.size !== a.groups.length ||
    new Set(a.scenarios.map((s) => s.id)).size !== a.scenarios.length
  )
    fail(p);
  for (const pop of [a.baseline, ...a.scenarios.map((s) => s.population)])
    if (
      pop.eligible + pop.ineligible + pop.unknown !== ids.size ||
      pop.eligible_candidate_ids.some((i) => !ids.has(i))
    )
      fail(p);
  for (const s of a.scenarios) {
    const added = s.population.eligible_candidate_ids.filter(
      (i) => !a.baseline.eligible_candidate_ids.includes(i),
    );
    const r = s.restriction_ratio;
    if (
      s.group_ids.some((g) => !groups.has(g)) ||
      !same(
        s.condition_ids,
        s.group_ids.flatMap((g) => groups.get(g) ?? []),
      ) ||
      !same(added, s.additional_candidate_ids) ||
      !same(added, [...s.proven_blocked_candidate_ids, ...s.previously_unknown_candidate_ids]) ||
      s.proven_blocked_candidate_ids.some((i) => s.previously_unknown_candidate_ids.includes(i)) ||
      r.numerator !== s.proven_blocked_candidate_ids.length ||
      r.denominator !== s.population.eligible ||
      r.numerator > r.denominator ||
      (r.state === 'computed'
        ? !r.denominator ||
          r.percent === null ||
          s.previously_unknown_candidate_ids.length > 0 ||
          Math.abs(r.percent - (100 * r.numerator) / r.denominator) > 1e-6
        : r.percent !== null) ||
      s.witnesses.some((w) => !added.includes(w.candidate_id)) ||
      s.joint_only_candidate_ids.some((i) => !added.includes(i))
    )
      fail(p);
    for (const rank of [
      ...s.top_before,
      ...s.top_after,
      ...s.rank_changes.flatMap((c) => [c.before, c.after]),
    ])
      if (
        !ids.has(rank.candidate_id) ||
        rank.rank < 1 ||
        (rank.score_lower === null) !== (rank.score_upper === null) ||
        (rank.score_lower !== null &&
          (rank.score_lower < 0 || rank.score_upper! > 1 || rank.score_lower > rank.score_upper!))
      )
        fail(p);
    if (
      s.rank_changes.some(
        (c) =>
          c.candidate_id !== c.before.candidate_id ||
          c.candidate_id !== c.after.candidate_id ||
          c.rank_delta !== c.before.rank - c.after.rank,
      )
    )
      fail(p);
  }
};
export const whatIf: Validator = (v, p = 'data') => {
  shape({
    id: string,
    status: literal('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled'),
    result: nullable(whatIfAnalysis),
  })(v, p);
  const d = record(v, p);
  if (d.result && record(d.result, p).id !== d.id) fail(p);
};
export const acceptedWhatIf = shape({
  analysis_id: string,
  job_id: string,
  comparison_id: string,
  requirement_id: string,
  revision: integer,
  status: literal('queued'),
});
