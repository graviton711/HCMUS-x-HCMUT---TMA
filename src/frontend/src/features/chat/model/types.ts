import type { CurrentAgentChoice, CurrentComparison, CurrentRequirement } from '../../../shared/api';

export type ChatPhase = 'idle' | 'thinking' | 'working';

export type ChatMsg =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'assistant'; text: string }
  | { id: string; kind: 'notice'; text: string }
  | { id: string; kind: 'choice'; choice: CurrentAgentChoice }
  | {
      id: string;
      kind: 'tool_activity';
      tools: {
        id: string;
        name: string;
        message?: string;
        status: 'running' | 'completed' | 'error' | 'cancelled';
      }[];
      outcome?: 'running' | 'completed' | 'error' | 'cancelled';
    }
  | {
      id: string;
      kind: 'comparison';
      comparison: CurrentComparison;
    }
  | {
      id: string;
      kind: 'decision_draft';
      requirement: CurrentRequirement;
      status: 'draft' | 'running' | 'complete';
    }
  | { id: string; kind: 'error'; text: string; expired?: boolean };
