import { ApiClient } from '../api/client';
import type { HistoryItem } from '../api/types';
import { accountFetch } from './auth';
import { newSession, type LocalSession } from './storage';

export const accountClient = (id: string) => new ApiClient(undefined, undefined, accountFetch(id));
export function fromHistory(item: HistoryItem, previous?: LocalSession): LocalSession {
  const original = previous ?? newSession();
  return {
    ...original,
    id: previous?.id ?? item.requirement_id,
    title: item.title || previous?.title || '',
    pinned: item.pinned,
    historyVersion: item.version,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    requirementId: item.requirement_id,
    proposalId: item.proposal_id,
    comparisonId: item.comparison_id,
    pendingComparisonId: item.pending_comparison_id,
    jobId: item.job_id,
    pendingMessageId: item.pending_message_id,
    analysisId: item.analysis_id,
    runs: item.runs.map((r) => ({ id: r.id, revision: r.revision, createdAt: r.created_at })),
    serverHydrated: previous?.serverHydrated ?? Boolean(previous?.requirementId),
  };
}
/** Load every available page, bounded to avoid an unbounded export/request loop. */
export async function allHistory(client: ApiClient, signal?: AbortSignal) {
  const items: HistoryItem[] = [];
  let after: string | undefined,
    retention = 0;
  const seen = new Set<string>();
  for (let page = 0; page < 100; page++) {
    const result = await client.history(after, { signal });
    retention = result.retention_days;
    items.push(
      ...result.items.filter((i) => !items.some((x) => x.requirement_id === i.requirement_id)),
    );
    if (!result.next_cursor) return { items, retention };
    if (seen.has(result.next_cursor)) throw new Error('Cursor lịch sử lặp lại; hãy tải lại.');
    seen.add(result.next_cursor);
    after = result.next_cursor;
  }
  throw new Error('Lịch sử vượt giới hạn 10.000 phiên. Chưa tải đủ để xuất dữ liệu.');
}
