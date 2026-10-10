export type JsonValue = null | boolean | number | string | JsonValue[] | JsonObject;
export interface JsonObject {
  [key: string]: JsonValue;
}
export type Strength = 'hard' | 'soft' | 'unresolved';
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'partial' | 'failed' | 'cancelled';
export interface ApiErrorPayload {
  code: string;
  message: string;
  retryable: boolean;
  details: JsonObject;
  field_path?: string | null;
  trace_id?: string;
}
export interface Envelope<T> {
  schema_version: '2.0-draft';
  request_id: string;
  data: T;
}
export interface Session {
  id: string;
  session_id: string;
  token: string;
  token_type: string;
  expires_at: string;
}
export interface Health {
  status: 'ok' | 'degraded';
  data_origin: 'source' | 'synthetic';
  data_provider: 'fixture' | 'http' | 'supabase';
  worker_enabled: boolean;
  schema_version: string;
  api_versions: string[];
  database_schema_version: number;
}
export interface CatalogEntry {
  id: string;
  label: string;
  parent_id?: string | null;
}
export interface CatalogField {
  id: string;
  operators: string[];
  processing_methods: string[];
  strength_choices: string[];
}
export interface Catalog {
  catalog_version: string;
  destinations: CatalogEntry[];
  origins: CatalogEntry[];
  fields: CatalogField[];
  required_by_input_kind: Record<string, string[]>;
  defaults: JsonObject;
  qualitative_policy: JsonObject;
  assessment_policy: JsonObject;
  transports: CatalogEntry[];
  tour_types: CatalogEntry[];
  preference_dimensions: {
    id: 'cost' | 'comfort' | 'pace' | 'culture';
    min: number;
    max: number;
    default: PreferenceLevel;
    supported: boolean;
  }[];
  limits: {
    reference_urls: number;
    recommendations: number;
    candidate_limit_default: number;
    text_characters: number;
    contact_characters: number;
    page_default: number;
    page_max: number;
    body_bytes: number;
  };
  upstream_contract: string;
}
export interface NumberValue {
  kind: 'number';
  amount: number;
  upper?: number | null;
}
export interface SetValue {
  kind: 'set';
  items: string[];
}
export interface DateValue {
  kind: 'date';
  value: string;
  upper?: string | null;
}
export interface BudgetValue {
  kind: 'budget';
  amount: number | string;
  upper?: number | string | null;
  currency?: string | null;
  basis?: 'per_adult' | 'per_person' | 'group_total' | null;
  coverage?: 'tour_price' | 'trip_total';
  coverage_origin?: 'explicit' | 'system_default';
}
export interface UnresolvedValue {
  kind: 'unresolved';
  raw: string;
  reason: string;
}
export interface EntityMember {
  raw: string;
  entity_type: 'place' | 'transport' | 'service' | 'supplier' | 'tour_type';
  entity_id: string | null;
  status: 'resolved' | 'catalog_missing';
}
export interface EntitiesValue {
  kind: 'entities';
  members: EntityMember[];
  catalog_version: string;
}
export interface TemporalValue {
  kind: 'temporal';
  raw: string;
  calendar: 'gregorian' | 'vietnamese_lunar' | 'unresolved';
  group_id: string;
  role: 'start' | 'end' | 'single';
  semantics: 'availability' | 'exact' | 'departure_window' | 'ambiguous' | 'single';
  day?: number | null;
  month?: number | null;
  year?: number | null;
  year_origin?: string | null;
  holiday?: 'tet' | null;
  holiday_year?: number | null;
  leap?: boolean | null;
  resolved_date?: string | null;
  reason?: string | null;
  converter_version?: string | null;
}
export interface QualitativeValue {
  kind: 'qualitative';
  concept: 'supplier_reputation' | 'service_quality' | 'price_value' | 'nature';
  raw: string;
  metric_policy?: string | null;
}
export type ConditionValue =
  | NumberValue
  | SetValue
  | DateValue
  | BudgetValue
  | UnresolvedValue
  | EntitiesValue
  | TemporalValue
  | QualitativeValue;
export interface SourceReference {
  kind: 'text' | 'form' | 'system_default';
  message_id?: string | null;
  quote?: string | null;
  start?: number | null;
  end?: number | null;
  field_path?: string | null;
  submitted_value?: JsonValue;
  rule?: string | null;
}
export interface FormCondition {
  id: string;
  field: string;
  operator: string;
  value: ConditionValue;
  strength: Strength;
  scope?: 'main_journey' | 'itinerary' | null;
}
export interface Condition extends FormCondition {
  sources: SourceReference[];
  trace?: { raw_values: string[]; rule: string; version: string } | null;
}
export interface Tree {
  kind: 'all' | 'any' | 'predicate';
  condition_id?: string | null;
  children?: Tree[];
}
export interface Child {
  id: string;
  age: number | null;
}
export interface Party {
  adults: number | null;
  children: Child[];
  rooming?: string | null;
  sources?: SourceReference[];
}
export interface PreferenceLevel {
  level: number;
  origin: 'user' | 'system_default';
}
export type PreferenceDimension = 'cost' | 'comfort' | 'pace' | 'culture';
export type Preferences = Record<PreferenceDimension, PreferenceLevel>;
export interface Clarification {
  id: string;
  field_path: string;
  reason_code: string;
  question: string;
  options: string[];
  blocking: boolean;
}
export interface SemanticIssue {
  reason_code: string;
  responsibility: 'user' | 'backend' | 'data';
  condition_ids: string[];
  explanation: string;
  blocking: boolean;
}
export interface Readiness {
  can_confirm?: boolean;
  can_search?: boolean;
  completeness?: JsonObject;
  status: 'ready' | 'needs_clarification' | 'unsupported';
  can_collect_data: boolean;
  can_evaluate_hard_constraints: boolean;
  reasons: string[];
  blockers: string[];
  scope_coverage: 'complete' | 'partial' | 'unavailable';
  unassessed_preferences: string[];
}
export interface Requirement {
  schema_version: '2.0-draft';
  policy_version: string;
  id: string;
  revision: number;
  input_kind: 'structured' | 'text' | 'urls';
  mode: 'discover' | 'compare_urls' | 'hybrid';
  timezone: string;
  messages: { id: string; text: string; received_at: string }[];
  targets: { target_id: string; url: string }[];
  party: Party;
  conditions: Condition[];
  hard_tree: Tree;
  preference_tree: Tree;
  clarifications: Clarification[];
  readiness: Readiness;
  issues: SemanticIssue[];
  preference_levels: Preferences | null;
  reference_urls: string[];
  notes: string;
  provenance: JsonObject;
  created_at: string;
  active_proposal?: { id: string; version: number } | null;
  latest_job_id?: string | null;
  latest_comparison_id?: string | null;
  latest_comparison_job_id?: string | null;
}
export interface StructuredForm {
  conditions: FormCondition[];
  party: Party;
  hard_tree?: Tree | null;
  preference_tree?: Tree | null;
  preference_levels?: Preferences;
  notes?: string;
}
export type CreateRequirementRequest = {
  input:
    | { kind: 'structured'; form: StructuredForm }
    | { kind: 'text'; text: string }
    | { kind: 'urls' };
  reference_urls?: string[];
  timezone?: string;
};
export interface AcceptedRequirement {
  requirement_id: string;
  revision: 0;
  proposal_id: string;
  job_id?: string;
  proposal_version?: number;
  status: 'queued' | 'pending' | 'needs_clarification';
}
export type CreateRequirementResponse = Requirement | AcceptedRequirement;
export interface Change {
  id: string;
  path: string;
  condition_id: string | null;
  before: JsonValue;
  after: JsonValue;
  origin: 'user_edit' | 'chat_inference';
  reason: string;
}
export interface Proposal {
  id: string;
  version: number;
  requirement_id: string;
  base_revision: number;
  status: 'pending' | 'needs_clarification' | 'confirmed' | 'cancelled' | 'superseded' | 'expired';
  expires_at: string;
  preview: Requirement;
  changes: Change[];
  clarifications: Clarification[];
  requested_action: 'search' | 'next_group' | null;
  parse_job_id: string | null;
}
export type TypedEdit =
  | { op: 'upsert_condition'; condition: FormCondition }
  | { op: 'replace_condition_value'; condition_id: string; value: ConditionValue }
  | { op: 'remove_condition'; condition_id: string }
  | { op: 'replace_party'; party: Party }
  | { op: 'set_preference_level'; dimension: PreferenceDimension; level: number }
  | { op: 'replace_reference_urls'; reference_urls: string[] }
  | { op: 'set_notes'; notes: string }
  | { op: 'replace_tree'; tree: Tree; tree_kind: 'hard_tree' | 'preference_tree' }
  | { op: 'answer_clarification'; clarification_id: string; answer: JsonValue };
export interface CreateProposalRequest {
  expected_revision: number;
  proposal_id?: string | null;
  expected_proposal_version?: number | null;
  input: { kind: 'structured'; edits: TypedEdit[] } | { kind: 'message'; text: string };
}
export interface AcceptedProposal {
  proposal_id: string;
  proposal_version: number;
  job_id: string;
  status: 'queued';
}
export type CreateProposalResponse = Proposal | AcceptedProposal;
export interface ConfirmProposalRequest {
  expected_revision: number;
  expected_proposal_version: number;
}
export interface CancelProposalResult {
  proposal_id: string;
  status: 'cancelled';
  committed_requirement: Requirement;
}
export interface DiscardChangesRequest extends ConfirmProposalRequest {
  change_ids: string[];
}
export interface CreateComparisonRequest {
  requirement_id: string;
  revision: number;
  round_intent?: 'initial' | 'next_group' | 'offer_change';
  previous_comparison_id?: string | null;
  excluded_tour_ids?: string[];
  offer_selections?: { tour_id: string; offer_snapshot_id: string }[];
  candidate_limit?: number;
}
export interface AcceptedComparison {
  comparison_id: string;
  job_id: string;
  requirement_id: string;
  revision: number;
  status: 'queued';
}
export type DataState = 'present' | 'missing' | 'conflicting' | 'invalid' | 'unsupported';
export type Verification =
  'catalog_validated' | 'supplier_published' | 'independently_verified' | 'unverified';
export type Completeness = 'complete' | 'partial' | 'unknown';
export interface Fact<T = JsonValue> {
  value: T | null;
  raw_value: string | null;
  data_state: DataState;
  verification: Verification;
  completeness: Completeness;
  observed_at: string;
  evidence_ids: string[];
  unit: string | null;
  scope: string | null;
  normalization_rule: string | null;
  reason: string | null;
}
export interface Applicability {
  field: 'adults' | 'children_count' | 'rooming' | 'unresolved';
  value: number | string;
}
export interface PriceQuote {
  quote_id: string;
  kind: 'exact' | 'from' | 'range';
  amount: number | string;
  upper_amount: number | string | null;
  currency: string;
  basis: 'per_adult' | 'per_child' | 'per_infant' | 'per_room' | 'per_group';
  coverage: 'tour_price' | 'trip_total' | 'unspecified';
  age_min: number | null;
  age_max_exclusive: number | null;
  applicability: Applicability[];
}
export interface ExtraCharge {
  charge_id: string;
  amount: number | string;
  currency: string;
  basis: 'per_adult' | 'per_child' | 'per_person' | 'per_group' | 'per_room';
  required: boolean | null;
  applicability: Applicability[];
}
export interface Offer {
  snapshot_id: string;
  offer_id: string;
  tour_snapshot_id: string;
  fields: Record<string, Fact>;
  price_quotes: Fact<PriceQuote>[];
  extra_charges: Fact<ExtraCharge>[];
  pricing_complete: Fact<boolean> | null;
  catalog_fields: Record<string, Fact>;
}
export interface ComparisonColumn {
  id: string;
  candidate_id: string | null;
  tour_id: string | null;
  tour_snapshot_id: string | null;
  offer_snapshot_id: string | null;
  selected_offer_snapshot_id: string | null;
  title: string | null;
  title_reason?: string | null;
  supplier: { id: string; display_name: string } | null;
  canonical_url: string;
  origin: 'reference' | 'discovery' | 'both';
  target_ids: string[];
  source_ids: string[];
  offer_reason: string | null;
  offer_options: Offer[];
  eligible_offer_snapshot_ids: string[];
  offer_assessments: {
    offer_snapshot_id: string;
    hard_status: string | null;
    evaluation_ids: string[];
  }[];
  offers_complete: boolean;
}
export interface ComparisonRow {
  id: string;
  field: string;
  label: string;
  scope: 'tour' | 'offer' | 'cost' | 'evaluation';
  value_type: 'date' | 'number' | 'set' | 'text' | 'boolean' | 'price_list';
  unit: string | null;
  order: number;
  condition_ids: string[];
}
export interface Freshness {
  state: 'fresh' | 'stale' | 'unknown';
  checked_at: string;
  expires_at: string | null;
  policy_version: string;
}
export interface ComparisonCell {
  row_id: string;
  column_id: string;
  value: JsonValue;
  raw_value: (string | null)[];
  data_state: DataState;
  verification: Verification;
  completeness: Completeness;
  observed_at: string | null;
  freshness: Freshness;
  evidence_ids: string[];
  reason_code: string | null;
  evaluation_ids: string[];
}
export interface Evaluation {
  id: string;
  condition_id: string;
  candidate_id: string;
  field: string;
  strength: Strength;
  expected: JsonValue;
  actual: JsonValue;
  status: 'pass' | 'fail' | 'unknown' | 'not_evaluated';
  reason_code: string;
  evidence_ids: string[];
  data_quality: JsonObject;
  offer_snapshot_id: string | null;
}
export interface Recommendation {
  candidate_id: string;
  rank: number;
  score: number | null;
  coverage: number | null;
  score_interval: { lower: number | null; upper: number | null };
  ranking_basis: string;
  rank_status: string;
  eligible_offer_snapshot_ids: string[];
  contributions: JsonObject[];
  evaluation_ids: string[];
  reason: string;
}
export interface Recommendations {
  kind: 'personalized' | 'similar';
  candidate_ids: string[];
  items: Recommendation[];
  ranking_policy_version: string;
  unsupported_dimensions: string[];
  needs_verification: string[];
  excluded_tour_ids: string[];
  candidate_limit: number;
  truncated: boolean;
  evaluated_count: number;
}
export interface MetricOperand {
  candidate_id?: string;
  snapshot_id?: string;
  requirement_id?: string;
  revision?: number;
  field: string;
  quote_id?: string;
  value: JsonValue;
  evidence_ids: string[];
}
export interface Metric {
  id: string;
  operation: 'subtract' | 'multiply';
  operands: MetricOperand[];
  result: number | string | null;
  currency: string;
  basis: string;
  coverage: string;
  comparable: boolean;
  limitations: string[];
  evidence_ids: string[];
}
export interface Claim {
  id: string;
  metric_ids: string[];
  text: string;
  evidence_ids: string[];
  limitations: string[];
}
export interface SemanticAssessmentItem {
  candidate_id: string;
  condition_id: string;
  tour_snapshot_id: string;
  status: string;
  explanation?: string;
  evidence_ids: string[];
  usable_for_ranking: boolean;
  [key: string]: JsonValue | undefined;
}
export interface SemanticAssessment {
  state: string;
  reason_code?: string | null;
  items: SemanticAssessmentItem[];
  [key: string]: JsonValue | SemanticAssessmentItem[] | undefined;
}
export interface Analysis {
  metrics: Metric[];
  semantic_assessment: SemanticAssessment;
  retrieval: JsonObject;
  candidate_pool: { candidate_id: string; tour_snapshot_id: string; hard_status: string | null }[];
  metric_availability: {
    id?: string;
    metric?: string;
    state?: string;
    reason_code?: string | null;
    [key: string]: JsonValue | undefined;
  }[];
  claims: Claim[];
}
export interface SourceCoverage {
  source_id: string;
  target_id: string | null;
  status: 'ok' | 'partial' | 'blocked' | 'unsupported' | 'timeout' | 'error';
  reason_code: string | null;
  tour_snapshot_ids: string[];
  offer_snapshot_ids: string[];
  truncated: boolean;
}
export interface Warning {
  code: string;
  source_id: string;
  target_id: string | null;
  snapshot_id: string | null;
  field_path: string | null;
  explanation: string;
  retryable: boolean;
}
export interface ComparisonResult {
  id: string;
  requirement_id: string;
  revision: number;
  requirement_snapshot: Requirement;
  origin: 'source' | 'synthetic';
  evaluated_at: string;
  policy_versions: Record<string, string>;
  columns: ComparisonColumn[];
  rows: ComparisonRow[];
  cells: ComparisonCell[];
  evaluations: Evaluation[];
  recommendations: Recommendations;
  analysis: Analysis;
  source_coverage: SourceCoverage[];
  warnings: Warning[];
  empty_reason: string | null;
}
export interface Comparison {
  id: string;
  status: JobStatus;
  result: ComparisonResult | null;
}
export interface Job {
  id: string;
  resource_id: string;
  kind: string;
  status: JobStatus;
  phase: string;
  stage: string;
  resource_ref: string;
  created_at: string;
  deadline_at: string;
  completed_at: string | null;
  error: ApiErrorPayload | null;
  metrics: JsonObject | null;
}
export interface JobEvent {
  seq: number;
  job_id: string;
  stage: string;
  status: 'started' | 'completed' | 'partial' | 'failed' | 'cancelled' | 'skipped';
  occurred_at: string;
  source_id: string | null;
  summary: string;
  counts: Record<string, number> | null;
  error_code: string | null;
}
export interface JobEvents {
  items: JobEvent[];
  next_seq: number;
  has_more: boolean;
}
export interface Evidence {
  id: string;
  snapshot_id: string;
  url: string;
  publisher: string;
  method: 'json_ld' | 'json' | 'api' | 'html' | 'synthetic_fixture' | 'database_record';
  raw_quote: string;
  observed_at: string;
  record_ref?: {
    table: 'tours' | 'offers';
    record_key: string;
    field: string;
    content_hash: string;
  } | null;
  source_url: string;
  source_id: string | null;
  locator: {
    section_title: string | null;
    element_id: string | null;
    css_selector: string | null;
    text_quote: { exact: string | null; prefix: string | null; suffix: string | null };
    upstream_locator: string;
  };
  deep_link: {
    url: string | null;
    method: 'text_fragment' | 'page';
    status: 'best_effort' | 'unavailable';
    verified_at: string | null;
    reason: string | null;
  };
  retained_excerpt_url: string | null;
  quality: {
    origin: 'source' | 'synthetic';
    verification: Verification;
    independently_verified: boolean;
    provenance_kind: 'database_record' | 'website_excerpt';
  };
}
export interface ChatContext {
  requirement_revision: number;
  proposal_id?: string | null;
  proposal_version?: number | null;
  comparison_id?: string | null;
  result_revision?: number | null;
  offer_snapshot_ids?: string[];
  evidence_ids?: string[];
}
export interface SendMessageRequest {
  text: string;
  client_message_id: string;
  context: ChatContext;
}
export interface AcceptedMessage {
  message_id: string;
  status: 'queued';
  job_id: string;
}
export interface ChatAnswer {
  text: string;
  comparison_id?: string;
  revision?: number;
  metrics?: Metric[];
  evaluations?: Evaluation[];
}
export interface ChatOutcome {
  message_id: string;
  intent: 'answer' | 'edit' | 'search' | 'next_group' | 'clarify';
  requested_action: 'search' | 'next_group' | null;
  proposal_id: string | null;
  proposal_version?: number;
  job_id?: string;
  status?: 'queued';
  answer: ChatAnswer | null;
}
export interface MessageResult {
  accepted: AcceptedMessage;
  result: ChatOutcome | null;
}
export interface ContactRequest {
  category: 'feedback' | 'data_issue' | 'support';
  message: string;
  reply_to?: string | null;
  comparison_id?: string | null;
  client_submission_id?: string | null;
  context?: { session_id?: string | null; comparison_id?: string | null };
}
export interface ContactTicket {
  ticket_id: string;
  status: 'new' | 'in_progress' | 'resolved';
  created_at: string;
}
export type Column = ComparisonColumn;
export type Row = ComparisonRow;
export type Cell = ComparisonCell;

export interface HistoryItem {
  requirement_id: string;
  revision: number;
  status: string;
  title: string;
  pinned: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  proposal_id: string | null;
  comparison_id: string | null;
  pending_comparison_id: string | null;
  job_id: string | null;
  analysis_id: string | null;
  pending_message_id: string | null;
  runs: { id: string; revision: number; created_at: string }[];
  runs_limited: boolean;
}
export interface HistoryPage {
  items: HistoryItem[];
  next_cursor: string | null;
  retention_days: number;
}
export interface HistoryDetail extends HistoryItem {
  requirement: Requirement;
  transcript: {
    items: { id: string; role: 'user' | 'assistant'; text: string; occurred_at: string }[];
    limited: boolean;
  };
}
export interface HistoryMetadata {
  version: number;
  title: string;
  pinned: boolean;
  archived: boolean;
  updated_at: string | null;
}
export interface Population {
  eligible: number;
  ineligible: number;
  unknown: number;
  eligible_candidate_ids: string[];
  has_hard_constraints: boolean;
}
export interface WhatIfRank {
  candidate_id: string;
  rank: number;
  score_lower: number | null;
  score_upper: number | null;
  coverage: number | null;
  tied: boolean;
}
export interface WhatIfScenario {
  id: string;
  kind: 'remove_hard_group' | 'remove_soft_group' | 'relax_bound' | 'remove_hard_pair';
  group_ids: string[];
  condition_ids: string[];
  label: string;
  state: 'measured' | 'insufficient_data';
  population: Population;
  additional_candidate_ids: string[];
  proven_blocked_candidate_ids: string[];
  previously_unknown_candidate_ids: string[];
  joint_only_candidate_ids: string[];
  restriction_ratio: {
    state: 'computed' | 'blocked' | 'not_applicable';
    numerator: number;
    denominator: number;
    percent: number | null;
    reason_code: string | null;
    meaning: string;
  };
  top_before: WhatIfRank[];
  top_after: WhatIfRank[];
  top_changed: boolean;
  rank_changes: {
    candidate_id: string;
    before: WhatIfRank;
    after: WhatIfRank;
    rank_delta: number;
    evidence_ids: string[];
  }[];
  rank_changes_truncated: boolean;
  witnesses: {
    candidate_id: string;
    title: string | null;
    canonical_url: string;
    tour_snapshot_id: string;
    offer_snapshot_id: string | null;
    original_status: 'pass' | 'fail' | 'unknown';
    original_evaluations: JsonObject[];
    scenario_evaluations: JsonObject[];
    evidence_ids: string[];
  }[];
  witnesses_truncated: boolean;
  edits: JsonObject[];
  tradeoffs: JsonObject[];
  limitations: string[];
  minimal_within_tested_subsets: boolean;
  insight: string;
}
export interface WhatIfAnalysis {
  id: string;
  comparison_id: string;
  requirement_id: string;
  revision: number;
  policy_version: string;
  origin: 'source' | 'synthetic';
  evaluated_at: string;
  scope: JsonObject;
  baseline: Population;
  baseline_top: WhatIfRank[];
  groups: {
    id: string;
    strength: 'hard' | 'soft';
    condition_ids: string[];
    fields: string[];
    label: string;
  }[];
  scenarios: WhatIfScenario[];
  candidates: JsonObject[];
  semantic_assessment: JsonObject;
  explanation: JsonObject;
  limits: JsonObject;
  limitations: string[];
}
export interface WhatIf {
  id: string;
  status: JobStatus;
  result: WhatIfAnalysis | null;
}
export interface AcceptedWhatIf {
  analysis_id: string;
  job_id: string;
  comparison_id: string;
  requirement_id: string;
  revision: number;
  status: 'queued';
}
