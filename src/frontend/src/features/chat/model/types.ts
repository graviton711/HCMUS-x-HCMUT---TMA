import type { CurrentComparison, CurrentRequirement } from '../../../shared/api';

export type ChatPhase = 'idle' | 'thinking' | 'working';

export interface ChatStep {
  id: 'interpret' | 'compare';
  state: 'pending' | 'active' | 'done' | 'error';
}

export type ChatMsg =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'assistant'; text: string }
  | { id: string; kind: 'interpretation'; requirement: CurrentRequirement }
  | {
      id: string;
      kind: 'comparison';
      comparison: CurrentComparison;
      dropped: string[];
    }
  | { id: string; kind: 'error'; text: string; expired?: boolean };
