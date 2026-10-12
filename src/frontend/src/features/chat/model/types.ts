import type { CurrentAgentChoice, CurrentComparison } from '../../../shared/api';

export type ChatPhase = 'idle' | 'thinking' | 'working';

export type ChatMsg =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'assistant'; text: string }
  | { id: string; kind: 'choice'; choice: CurrentAgentChoice }
  | {
      id: string;
      kind: 'tool_activity';
      tools: {
        id: string;
        name: string;
        message?: string;
        status: 'running' | 'completed' | 'error';
      }[];
    }
  | {
      id: string;
      kind: 'comparison';
      comparison: CurrentComparison;
    }
  | { id: string; kind: 'error'; text: string; expired?: boolean };
