/** DTOs for the active src/backend API. No legacy envelope or /v2 fallbacks. */

export interface CurrentSession {
  id: string;
  session_id: string;
  token: string;
  token_type: "Bearer";
  expires_at: string;
}

export interface CurrentCatalog {
  destinations: string[];
}

export interface CurrentHealth {
  status: "ok";
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
  | { type: "progress"; status: string }
  | {
      type: "tool";
      id: string;
      name: string;
      message?: string;
      status: "running" | "completed" | "error";
    };

export interface CurrentCondition {
  id: string;
  field: string;
  operator: string;
  value: unknown;
  strength: "hard" | "soft";
  quote: string;
  weight_percent?: number | null;
}

export interface CurrentRequirement {
  id: string;
  conditions: CurrentCondition[];
  missing: string[];
  raw_text: string;
  travelers: number;
  traveler_mix?: Partial<
    Record<"adult" | "child" | "small_child" | "infant", number>
  >;
  ranking?: {
    order_by: {
      field:
        "price" | "departure_date" | "duration_days" | "tour_name" | "soft_fit";
      direction: "asc" | "desc";
    }[];
  } | null;
}

export interface CurrentOffer {
  id: string;
  tour_id: string;
  departure_date: string;
  price: number | null;
  currency: string;
  price_basis: "exact" | "from" | "contact" | "unknown";
  price_by_age?: Partial<
    Record<"adult" | "child" | "small_child" | "infant", number | null>
  >;
  single_supplement?: number | null;
  supplements?: string;
  departure_freshness: "fresh" | "stale" | "unknown";
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
  offers: CurrentOffer[];
}

export interface CurrentEvaluation {
  offer_id: string;
  condition_id: string;
  state: "pass" | "partial" | "fail" | "unknown";
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
  ranking_currencies?: string[];
  decision_views?: CurrentDecisionView[];
  metric_profiles?: CurrentMetricProfile[];
  decision_options?: CurrentDecisionOption[];
  recommendation?: CurrentDecisionOption | null;
  extracted_facts?: unknown[];
}

export interface CurrentDecisionView {
  kind:
    | "cheapest"
    | "best_fit"
    | "experience_rich"
    | "fewest_legs"
    | "cancellation_flexible"
    | "family_friendly"
    | "included_value"
    | "balanced";
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
  kind:
    | "age_range"
    | "age_price"
    | "discount"
    | "room"
    | "bed"
    | "eligibility"
    | "other";
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
  state: "observed" | "partial" | "unknown";
  evidence: CurrentMetricEvidence[];
  method_version: string;
}

export interface CurrentCostExposure {
  name: string;
  obligation: "mandatory" | "optional" | "conditional" | "unknown";
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
    price_basis: "exact" | "from" | "contact" | "unknown";
    currency: string;
    group_total_calculated: number | null;
    group_total_scope: string;
    total_is_lower_bound: boolean;
    priced_extras: CurrentCostExposure[];
    unpriced_exclusions: CurrentCostExposure[];
    optional_or_conditional: CurrentCostExposure[];
    state: "observed" | "partial" | "unknown";
  };
  preference_fit: {
    condition_id: string;
    lower_score: number;
    upper_score: number;
    state: "observed" | "partial" | "unknown";
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
}

export interface CurrentHistoryItem {
  id: string;
  kind: "requirement" | "comparison";
  created_at: string;
}

export interface CurrentHistoryPage {
  items: CurrentHistoryItem[];
  next_cursor: string | null;
}
