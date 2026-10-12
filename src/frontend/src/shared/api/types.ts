/** DTOs for the active src/backend API. No legacy envelope or /v2 fallbacks. */

export interface CurrentSession {
  id: string;
  session_id: string;
  token: string;
  token_type: 'Bearer';
  expires_at: string;
}

export interface CurrentCatalog {
  destinations: string[];
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
  comparison?: CurrentComparison;
}

export type CurrentAgentProgressEvent =
  | { type: 'progress'; status: string }
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
}

export interface CurrentRequirement {
  id: string;
  conditions: CurrentCondition[];
  missing: string[];
  raw_text: string;
  travelers: number;
}

export interface CurrentOffer {
  id: string;
  tour_id: string;
  departure_date: string;
  price: number | null;
  currency: string;
  price_basis: 'exact' | 'from' | 'contact';
  price_trusted: boolean;
  price_freshness: 'fresh' | 'stale' | 'unknown';
  departure_freshness: 'fresh' | 'stale' | 'unknown';
  pricing_metadata_state: 'missing' | 'validated' | 'invalid' | 'untrusted';
  availability: string;
  conditions: string;
  evidence: { url: string; method: string; observed_at: string; record_ref: string };
}

export interface CurrentTourSnapshot {
  id: string;
  supplier: string;
  name: string;
  url: string;
  destinations: string[];
  raw_destinations: string[];
  route: string[];
  destination_countries: string[];
  destination_country_complete: boolean;
  departure_city: string;
  duration_days: number | null;
  transport: string;
  accommodation: string;
  itinerary: string;
  inclusions: string;
  exclusions: string;
  cancellation_policy: string;
  surcharges: string;
  child_policy: string;
  evidence: { url: string; method: string; observed_at: string; record_ref: string };
  observed_at: string;
  verification: string;
  offers: CurrentOffer[];
}

export interface CurrentEvaluation {
  offer_id: string;
  condition_id: string;
  state: 'pass' | 'fail' | 'unknown';
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
}

export interface CurrentHistoryItem {
  id: string;
  kind: 'requirement' | 'comparison';
  created_at: string;
}

export interface CurrentHistoryPage {
  items: CurrentHistoryItem[];
  next_cursor: string | null;
}
