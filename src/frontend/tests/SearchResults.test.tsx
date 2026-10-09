// @vitest-environment jsdom
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it } from 'vitest';
import { PreferencesProvider } from '../app/preferences';
import { Activity, SearchDiagnostics } from '../features/workspace/Results';
import type { ComparisonColumn, Evaluation, Job, JobEvent } from '../api/types';

afterEach(() => localStorage.clear());
const at = '2026-10-09T14:27:10Z';
const column: ComparisonColumn = {
  id: 'tour-a',
  candidate_id: 'tour-a',
  tour_id: 'a',
  tour_snapshot_id: 'ts-a',
  offer_snapshot_id: null,
  selected_offer_snapshot_id: null,
  title: 'Tour A',
  supplier: null,
  canonical_url: 'https://example.test/a',
  origin: 'discovery',
  target_ids: [],
  source_ids: [],
  offer_reason: 'MULTIPLE_OFFERS_UNSELECTED',
  offer_options: [],
  eligible_offer_snapshot_ids: [],
  offer_assessments: [],
  offers_complete: false,
};
function evaluation(id: string, offer: string | null, field: string, reason: string): Evaluation {
  return {
    id,
    condition_id: field,
    candidate_id: column.id,
    field,
    strength: 'hard',
    expected: null,
    actual: null,
    status: 'unknown',
    reason_code: reason,
    evidence_ids: [],
    data_quality: {},
    offer_snapshot_id: offer,
  };
}
function diagnosticResult(): Parameters<typeof SearchDiagnostics>[0]['result'] {
  return {
    columns: [column],
    evaluations: [
      evaluation('aggregate', null, 'departure_date', 'MULTIPLE_OFFERS_UNSELECTED'),
      evaluation('first', 'offer-a', 'departure_date', 'FIELD_STALE'),
      evaluation('second', 'offer-b', 'departure_date', 'FIELD_STALE'),
      evaluation('price', 'offer-a', 'estimated_cost', 'PRICE_COVERAGE_UNCONFIRMED'),
    ],
    recommendations: {
      kind: 'personalized',
      candidate_ids: [],
      items: [],
      ranking_policy_version: 'test',
      unsupported_dimensions: [],
      needs_verification: ['tour-a'],
      excluded_tour_ids: [],
      candidate_limit: 20,
      truncated: true,
      evaluated_count: 1,
    },
    analysis: {
      metrics: [],
      claims: [],
      candidate_pool: [
        { candidate_id: 'tour-a', tour_snapshot_id: 'ts-a', hard_status: 'unknown' },
      ],
      metric_availability: [],
      semantic_assessment: {
        state: 'skipped',
        reason_code: 'NO_ELIGIBLE_SEMANTIC_INPUT',
        items: [],
      },
      retrieval: {
        runs: [
          { scanned_count: 1000, retained_count: 1, scan_truncated: true, offer_truncated: true },
        ],
      },
    },
  };
}
function html(element: React.ReactNode) {
  return renderToStaticMarkup(<PreferencesProvider>{element}</PreferencesProvider>);
}

describe('Search status and evidence blockers', () => {
  it('shows terminal job and historical start events without claiming they are still running', () => {
    const job: Job = {
      id: 'job-a',
      resource_id: 'comparison-a',
      kind: 'v2_comparison',
      status: 'succeeded',
      phase: 'completed',
      stage: 'completed',
      resource_ref: 'comparison-a',
      created_at: at,
      deadline_at: at,
      completed_at: at,
      error: null,
      metrics: null,
    };
    const events: JobEvent[] = [
      'queued',
      'orchestration',
      'reference_collection',
      'publication',
    ].map((stage, i) => ({
      seq: i + 1,
      job_id: job.id,
      stage,
      status: i === 3 ? 'completed' : 'started',
      occurred_at: at,
      source_id: null,
      summary: 'Sự kiện đã lưu',
      counts: null,
      error_code: null,
    }));
    const view = html(<Activity job={job} events={events} onCancel={() => {}} />);
    expect(view).toContain('Hoàn thành');
    expect(view).toContain('Đã bắt đầu');
    expect(view).toContain('Tiếp nhận và xử lý');
    expect(view).not.toContain('Đang thực hiện');
    expect(view).not.toContain('Đang chờ xử lý');
    expect(view).not.toContain('Hủy xử lý');
  });
  it('counts tours once, uses per-offer blockers and explains limited scope and skipped AI', () => {
    const view = html(<SearchDiagnostics result={diagnosticResult()} />);
    expect(view).toContain('1 tour cần xác nhận');
    expect(view).toContain('Dữ liệu đã quá thời hạn');
    expect(view).toContain('phạm vi giá');
    expect(view).toContain('<strong>Chi phí</strong>');
    expect(view).not.toContain('<strong>estimated_cost</strong>');
    expect(view).toContain('1000');
    expect(view).toContain('chưa đại diện toàn bộ kho tour');
    expect(view).toContain('Chưa có tour đạt điều kiện bắt buộc');
    expect(view).not.toContain('2 tour');
    expect(view).not.toContain('Cần chọn một lịch');
  });
  it('translates the diagnosis in English', () => {
    localStorage.setItem('di-cung-display-v1', JSON.stringify({ locale: 'en', theme: 'light' }));
    expect(html(<SearchDiagnostics result={diagnosticResult()} />)).toContain('Data has expired');
  });
  it('omits verification blockers once the backend confirms eligibility', () => {
    const result = diagnosticResult();
    result.recommendations.needs_verification = [];
    result.recommendations.truncated = false;
    result.analysis.retrieval = {};
    result.analysis.semantic_assessment.reason_code = null;
    expect(html(<SearchDiagnostics result={result} />)).toBe('');
  });
});
