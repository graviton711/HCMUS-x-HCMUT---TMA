/** DTOs for the active src/backend API. No legacy envelope or /v2 fallbacks. */

export interface CurrentSession {
  id: string;
  session_id: string;
  token: string;
  token_type: 'Bearer';
  expires_at: string;
}

export interface CurrentHealth {
  status: 'ok';
  version: string;
}

export interface CurrentAgentSession {
  agent_session_id: string;
}

export interface CurrentAgentChoice {
  question: string;
  options: { label: string; value: string }[];
  allow_custom: boolean;
}

export interface CurrentAgentResponse {
  assistant_text: string;
  choices?: CurrentAgentChoice;
  tool_calls: { name: string; status: string }[];
  requirement?: CurrentRequirement;
  decision_draft?: CurrentRequirement;
  comparison?: CurrentComparison;
}

export type CurrentAgentProgressEvent =
  | { type: 'progress'; status: string }
  | { type: 'text'; text: string }
  | {
      type: 'tool';
      id: string;
      name: string;
      message?: string;
      status: 'running' | 'completed' | 'error';
    };

export interface CurrentCondition {
  id: string;
  field: string;
  operator: string;
  value: unknown;
  strength: 'hard' | 'soft';
  quote: string;
  weight_percent?: number | null;
}

export interface CurrentRequirement {
  id: string;
  conditions: CurrentCondition[];
  alternatives?: CurrentRequirementAlternative[];
  assumptions?: CurrentRequirementAssumption[];
  missing: string[];
  raw_text: string;
  travelers: number;
  traveler_mix?: Partial<Record<'adult' | 'child' | 'small_child' | 'infant', number>>;
  ranking?: {
    order_by: {
      field: 'price' | 'departure_date' | 'duration_days' | 'tour_name' | 'soft_fit';
      direction: 'asc' | 'desc';
    }[];
  } | null;
}

export interface CurrentRequirementAlternative {
  id: string;
  label: string;
  conditions: CurrentCondition[];
}

export interface CurrentRequirementAssumption {
  id: string;
  kind: 'date_window';
  label: string;
  quote: string;
  date_from: string;
  date_to: string;
  condition_ids: string[];
  timezone: 'Asia/Ho_Chi_Minh';
  edited?: boolean;
}

export interface CurrentOffer {
  id: string;
  tour_id: string;
  departure_date: string;
  price: number | null;
  currency: string;
  price_basis: 'exact' | 'from' | 'contact' | 'unknown';
  price_by_age?: Partial<Record<'adult' | 'child' | 'small_child' | 'infant', number | null>>;
  single_supplement?: number | null;
  supplements?: string;
  departure_freshness: 'fresh' | 'stale' | 'unknown';
  availability: string;
  conditions: string;
  evidence: {
    url: string;
    method: string;
    observed_at: string;
    record_ref: string;
  };
}

export interface CurrentTourSnapshot {
  id: string;
  supplier: string;
  name: string;
  url: string;
  destinations: string[];
  raw_destinations: string[];
  route: string[];
  route_observed?: boolean;
  departure_city: string;
  duration_days: number | null;
  duration_nights?: number | null;
  transport: string;
  accommodation: string;
  itinerary: string;
  inclusions: string;
  exclusions: string;
  cancellation_policy: string;
  surcharges: string;
  child_policy: string;
  evidence: {
    url: string;
    method: string;
    observed_at: string;
    record_ref: string;
  };
  observed_at: string;
  verification: string;
  detail_state?: 'index' | 'complete';
  offers: CurrentOffer[];
}

export interface CurrentEvaluation {
  offer_id: string;
  condition_id: string;
  alternative_id?: string | null;
  state: 'pass' | 'partial' | 'fail' | 'unknown';
  quote: string;
  reason_code: string;
  reason: string;
}

export interface CurrentComparison {
  id: string;
  requirement: CurrentRequirement;
  ranked: { tour_id: string; offer_id: string; score: number }[];
  near_miss: { tour_id: string; offer_id: string; score: number }[];
  tour_snapshots: CurrentTourSnapshot[];
  evaluations: CurrentEvaluation[];
  analysis: {
    hidden_costs: string[];
    conditions: string[];
    risks: string[];
    benefits: string[];
  };
  candidates_considered: number;
  decision_trace?: CurrentDecisionTrace | null;
  ranking_currencies?: string[];
  decision_views?: CurrentDecisionView[];
  metric_profiles?: CurrentMetricProfile[];
  decision_options?: CurrentDecisionOption[];
  near_miss_profiles?: CurrentMetricProfile[];
  assumptions?: string[];
}

export interface CurrentDecisionView {
  kind:
    | 'cheapest'
    | 'best_fit'
    | 'experience_rich'
    | 'fewest_legs'
    | 'cancellation_flexible'
    | 'included_value'
    | 'balanced';
  candidates: { tour_id: string; offer_id: string; score: number }[];
  currencies: string[];
  note: string;
}

export interface CurrentMetricEvidence {
  source_field: string;
  quote: string;
  observed_at: string;
  url: string;
}

export interface CurrentCancellationRule {
  days_before_departure: number | null;
  refund_percent: number | null;
  fee_amount: number | null;
  currency: string;
  evidence: CurrentMetricEvidence;
}

export interface CurrentFamilyFact {
  kind: 'age_range' | 'age_price' | 'discount' | 'room' | 'bed' | 'eligibility' | 'other';
  min_age: number | null;
  max_age: number | null;
  amount: number | null;
  percent: number | null;
  condition: string;
  evidence: CurrentMetricEvidence;
}

export interface CurrentMetricMeasure {
  value: unknown;
  lower_bound: number | null;
  upper_bound: number | null;
  unit: string;
  state: 'observed' | 'partial' | 'unknown';
  evidence: CurrentMetricEvidence[];
  method_version: string;
}

export interface CurrentCostExposure {
  name: string;
  obligation: 'mandatory' | 'optional' | 'conditional' | 'unknown';
  amount: number | null;
  currency: string;
  unit: string;
  applies_when: string;
  source_field: string;
  quote: string;
  calculated_total: number | null;
}

export interface CurrentMetricProfile {
  tour_id: string;
  offer_id: string;
  cost: {
    listed_price: number | null;
    price_basis: 'exact' | 'from' | 'contact' | 'unknown';
    currency: string;
    group_total_calculated: number | null;
    group_total_scope: string;
    priced_extras: CurrentCostExposure[];
    unpriced_exclusions: CurrentCostExposure[];
    optional_or_conditional: CurrentCostExposure[];
    state: 'observed' | 'partial' | 'unknown';
  };
  preference_fit: {
    condition_id: string;
    lower_score: number;
    upper_score: number;
    state: 'observed' | 'partial' | 'unknown';
    evidence: CurrentMetricEvidence[];
  }[];
  metrics: Record<string, CurrentMetricMeasure>;
  inclusions: CurrentMetricMeasure[];
  exclusions: CurrentCostExposure[];
  cancellation_rules: CurrentCancellationRule[];
  family_facts: CurrentFamilyFact[];
}

export interface CurrentDecisionOption {
  tour_id: string;
  offer_id: string;
  objective: string;
  title: string;
  reason: string;
  tradeoffs: string[];
  metric_comparisons?: CurrentOptionMetricComparison[];
}

export interface CurrentOptionMetricComparison {
  key: string;
  value: number | null;
  reference_median: number | null;
  unit: string;
  currency: string;
  scope: string;
  state: 'observed' | 'partial' | 'unknown';
  relation: 'favorable' | 'tradeoff' | 'similar' | 'unknown';
  higher_is_better: boolean | null;
  evidence: CurrentMetricEvidence[];
}

export interface CurrentDecisionTrace {
  scanned_tours: number;
  scanned_offers: number;
  eligible_tours: number;
  eligible_offers: number;
  excluded_offers: number;
  condition_counts: {
    condition_id: string;
    pass_offers: number;
    fail_offers: number;
    unknown_offers: number;
    pass_tours: number;
    fail_tours: number;
    unknown_tours: number;
  }[];
  sequential_funnel: {
    condition_id: string;
    label?: string;
    group_id?: string;
    stage: number;
    offers_before: number;
    offers_after: number;
    tours_before: number;
    tours_after: number;
  }[];
  first_blockers: {
    condition_id: string;
    state: 'fail' | 'unknown';
    offers: number;
    tours: number;
  }[];
  alternative_counts?: {
    alternative_id: string;
    label: string;
    eligible_offers: number;
    eligible_tours: number;
  }[];
  snapshot_available: boolean;
}

export interface CurrentEliminatedOffer {
  tour_id: string;
  tour_name: string;
  supplier: string;
  tour_url: string;
  offer: CurrentOffer;
  conditions: {
    condition_id: string;
    alternative_id?: string | null;
    field: string;
    value: unknown;
    state: 'pass' | 'fail' | 'unknown';
    reason_code: string;
    reason: string;
    quote: string;
  }[];
}

export interface CurrentEliminatedPage {
  comparison_id: string;
  items: CurrentEliminatedOffer[];
  limit: number;
  next_cursor: string | null;
  total: number;
}

export interface CurrentCostScenarioAssumptions {
  travelers: number;
  traveler_mix: Partial<Record<'adult' | 'child' | 'small_child' | 'infant', number>>;
  rooms?: number | null;
  single_rooms?: number | null;
  nights?: number | null;
}

export interface CurrentCostScenarioItem {
  tour_id: string;
  tour_name: string;
  offer_id: string;
  currency: string;
  price_basis: 'exact' | 'from' | 'contact' | 'unknown';
  listed_price: number | null;
  group_base_calculated: number | null;
  priced_mandatory_extras: CurrentCostExposure[];
  known_total: number | null;
  unresolved_exposures: CurrentCostExposure[];
  delta_from_original: number | null;
  state: 'observed' | 'partial' | 'unknown';
  evidence: CurrentMetricEvidence[];
}

export interface CurrentCostScenario {
  source_comparison_id: string;
  assumptions: CurrentCostScenarioAssumptions;
  scanned_offers: number;
  items: CurrentCostScenarioItem[];
}
