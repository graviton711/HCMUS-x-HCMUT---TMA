import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { PreferencesProvider } from '../app/preferences';
import { Activity, Results, formatAmount, formatResultValue } from '../features/workspace/Results';
import type {
  Comparison,
  ComparisonCell,
  ComparisonColumn,
  ComparisonResult,
  Job,
  JobEvent,
  JsonValue,
  Requirement,
} from '../api/types';

// Contract fixtures stay in tests and never enter the shipped application.
const at = '2026-10-08T08:00:00Z';
const requirement: Requirement = {
  id: 'requirement-test',
  schema_version: '2.0-draft',
  policy_version: 'test',
  revision: 1,
  input_kind: 'urls',
  mode: 'compare_urls',
  timezone: 'Asia/Ho_Chi_Minh',
  messages: [],
  targets: [{ target_id: 'reference-test', url: 'https://example.test/reference' }],
  party: { adults: null, children: [] },
  conditions: [],
  hard_tree: { kind: 'all', children: [] },
  preference_tree: { kind: 'all', children: [] },
  clarifications: [],
  readiness: {
    status: 'ready',
    can_collect_data: true,
    can_evaluate_hard_constraints: false,
    reasons: [],
    blockers: [],
    scope_coverage: 'complete',
    unassessed_preferences: [],
  },
  issues: [],
  preference_levels: null,
  reference_urls: ['https://example.test/reference'],
  notes: '',
  provenance: {},
  created_at: at,
};
const column: ComparisonColumn = {
  id: 'tour-test',
  candidate_id: 'tour-test',
  tour_id: 'tour-test',
  tour_snapshot_id: 'tour-snapshot-test',
  offer_snapshot_id: null,
  selected_offer_snapshot_id: null,
  title: 'Tên tour từ nguồn kiểm thử',
  supplier: { id: 'supplier-test', display_name: 'Nhà cung cấp kiểm thử' },
  canonical_url: 'https://example.test/tour',
  origin: 'discovery',
  target_ids: [],
  source_ids: ['source-test'],
  offer_reason: 'OFFER_MISSING',
  offer_options: [],
  eligible_offer_snapshot_ids: [],
  offer_assessments: [],
  offers_complete: false,
};
const cell: ComparisonCell = {
  row_id: 'duration_days',
  column_id: 'tour-test',
  value: 5,
  raw_value: ['5 ngày'],
  data_state: 'present',
  verification: 'supplier_published',
  completeness: 'partial',
  observed_at: at,
  freshness: { state: 'unknown', checked_at: at, expires_at: null, policy_version: 'test' },
  evidence_ids: ['evidence-duration'],
  reason_code: null,
  evaluation_ids: [],
};
function comparison(overrides: Partial<ComparisonResult> = {}): Comparison {
  return {
    id: 'comparison-test',
    status: 'succeeded',
    result: {
      id: 'comparison-test',
      requirement_id: requirement.id,
      revision: 1,
      requirement_snapshot: requirement,
      origin: 'source',
      evaluated_at: at,
      policy_versions: { ranking: 'test' },
      columns: [column],
      rows: [
        {
          id: 'duration_days',
          field: 'duration_days',
          label: 'Thời lượng',
          scope: 'tour',
          value_type: 'number',
          unit: 'days',
          order: 0,
          condition_ids: [],
        },
      ],
      cells: [cell],
      evaluations: [],
      recommendations: {
        kind: 'similar',
        candidate_ids: ['tour-test'],
        items: [
          {
            candidate_id: 'tour-test',
            rank: 1,
            score: null,
            coverage: null,
            score_interval: { lower: null, upper: null },
            ranking_basis: 'conservative_lower_bound',
            rank_status: 'no_preferences',
            eligible_offer_snapshot_ids: [],
            contributions: [],
            evaluation_ids: [],
            reason: 'Không có điều kiện bắt buộc để kết luận phù hợp.',
          },
        ],
        ranking_policy_version: 'test',
        unsupported_dimensions: ['pace'],
        needs_verification: [],
        excluded_tour_ids: [],
        candidate_limit: 20,
        truncated: false,
        evaluated_count: 1,
      },
      analysis: {
        metrics: [],
        semantic_assessment: { state: 'skipped', items: [] },
        retrieval: {},
        candidate_pool: [],
        metric_availability: [],
        claims: [],
      },
      source_coverage: [
        {
          source_id: 'source-test',
          target_id: null,
          status: 'ok',
          reason_code: null,
          tour_snapshot_ids: ['tour-snapshot-test'],
          offer_snapshot_ids: [],
          truncated: false,
        },
      ],
      warnings: [],
      empty_reason: null,
      ...overrides,
    },
  };
}
function render(value: Comparison) {
  return renderToStaticMarkup(
    <PreferencesProvider>
      <Results
        comparison={value}
        busy={false}
        onOfferChange={() => undefined}
        onEvidence={() => undefined}
      />
    </PreferencesProvider>,
  );
}

describe('source value formatting', () => {
  it('retains range, basis, coverage, age brackets and applicability', () => {
    const value = formatResultValue(
      {
        kind: 'range',
        amount: '1200000',
        upper_amount: '1400000',
        currency: 'VND',
        basis: 'per_child',
        coverage: 'tour_price',
        age_min: 5,
        age_max_exclusive: 12,
        applicability: [{ field: 'rooming', value: 'Phòng cùng bố mẹ' }],
      },
      'vi',
    );
    expect(value).toContain('1.200.000 ₫ – 1.400.000 ₫ / trẻ em');
    expect(value).toContain('Giá tour');
    expect(value).toContain('5 ≤ tuổi < 12');
    expect(value).toContain('Điều kiện phòng: Phòng cùng bố mẹ');
  });
  it('does not turn a from price into an exact price or hide unknown coverage', () => {
    expect(
      formatResultValue(
        {
          kind: 'from',
          amount: 1200,
          currency: 'USD',
          basis: 'per_group',
          coverage: 'unspecified',
        },
        'en',
      ),
    ).toBe('From 1,200 USD / group · Price coverage unspecified');
  });
  it('preserves large decimal strings without float rounding', () => {
    expect(formatAmount('123456789012345.12345', 'USD', 'en')).toBe('123456789012345.12345 USD');
  });
  it('keeps false and zero as source values', () => {
    expect(formatResultValue(false, 'vi')).toBe('Không');
    expect(formatResultValue(0, 'vi', 'days')).toBe('0 ngày');
  });
});

describe('comparison presentation', () => {
  it('highlights an adult quote without losing other price bases or their source coverage', () => {
    const child = {
      kind: 'exact',
      amount: 2000000,
      currency: 'VND',
      basis: 'per_child',
      coverage: 'unspecified',
      age_min: 5,
      age_max_exclusive: 12,
      applicability: [],
    };
    const adult = {
      kind: 'from',
      amount: 5000000,
      currency: 'VND',
      basis: 'per_adult',
      coverage: 'tour_price',
      age_min: null,
      age_max_exclusive: null,
      applicability: [{ field: 'rooming', value: 'Phòng đôi' }],
    };
    const group = {
      kind: 'exact',
      amount: 7000000,
      currency: 'VND',
      basis: 'per_group',
      coverage: 'trip_total',
      age_min: null,
      age_max_exclusive: null,
      applicability: [],
    };
    const renderPrices = (quotes: JsonValue[]) =>
      render(
        comparison({
          rows: [
            {
              id: 'price_quotes',
              field: 'price_quotes',
              label: 'Giá công bố',
              scope: 'offer',
              value_type: 'price_list',
              unit: null,
              order: 0,
              condition_ids: [],
            },
          ],
          cells: [{ ...cell, row_id: 'price_quotes', value: quotes }],
        }),
      );
    const adultHtml = renderPrices([child, adult, group]);
    const primaryAdult = adultHtml.match(/<div class="price">([\s\S]*?)<\/div>/)?.[1];
    const secondaryAdult = adultHtml.match(
      /<details class="calculation-details">([\s\S]*?)<\/details>/,
    )?.[1];
    expect(primaryAdult).toContain('Từ 5.000.000 ₫ / người lớn · Giá tour');
    expect(primaryAdult).toContain('Điều kiện phòng: Phòng đôi');
    expect(primaryAdult).not.toContain('/ trẻ em');
    expect(secondaryAdult).toContain('2.000.000 ₫ / trẻ em · Chưa rõ phạm vi giá');
    expect(secondaryAdult).toContain('5 ≤ tuổi &lt; 12');
    expect(secondaryAdult).toContain('7.000.000 ₫ / nhóm · Tổng chuyến đi');

    const withoutAdultHtml = renderPrices([child, group]);
    const primaryChild = withoutAdultHtml.match(/<div class="price">([\s\S]*?)<\/div>/)?.[1];
    expect(primaryChild).toContain('2.000.000 ₫ / trẻ em · Chưa rõ phạm vi giá');
    expect(primaryChild).not.toContain('/ người lớn');
  });
  it('keeps quality dimensions distinct without treating a timestamp as verification', () => {
    const html = render(comparison());
    expect(html).toContain('Nhà cung cấp công bố');
    expect(html).toContain('Một phần');
    expect(html).toContain('Độ mới chưa rõ');
    expect(html).not.toContain('Đã xác minh độc lập');
    expect(html).toContain('Xem nguồn Thời lượng · Tên tour từ nguồn kiểm thử');
  });
  it('does not present a conflicting normalized value as a fact', () => {
    const html = render(
      comparison({
        cells: [{ ...cell, value: 987654321, raw_value: [], data_state: 'conflicting' }],
      }),
    );
    expect(html).toContain('Dữ kiện mâu thuẫn');
    expect(html).not.toContain('987.654.321');
  });
  it('refuses server synthetic output', () => {
    const html = render(comparison({ origin: 'synthetic' }));
    expect(html).toContain('Nguồn tour thật chưa sẵn sàng');
    expect(html).not.toContain(column.title);
    expect(html).not.toContain('<table');
  });
  it('keeps unreadable references visible even when there are no recommendations', () => {
    const original = comparison().result!;
    const html = render(
      comparison({
        columns: [
          {
            ...column,
            id: 'reference-test',
            candidate_id: null,
            tour_id: null,
            tour_snapshot_id: null,
            title: null,
            origin: 'reference',
            target_ids: ['reference-test'],
          },
        ],
        cells: [
          {
            ...cell,
            column_id: 'reference-test',
            data_state: 'missing',
            value: null,
            raw_value: [],
          },
        ],
        recommendations: { ...original.recommendations, candidate_ids: [], items: [] },
        empty_reason: 'ONLY_UNVERIFIED',
      }),
    );
    expect(html).toContain('Tham chiếu để đối chiếu');
    expect(html).toContain('Chưa đọc đủ dữ kiện từ URL này');
    expect(html).toContain('Chưa có dữ kiện');
    expect(html).toContain('<table');
  });
  it('shows a backend metric result rather than recalculating it from operands', () => {
    const original = comparison().result!;
    const html = render(
      comparison({
        analysis: {
          ...original.analysis,
          metrics: [
            {
              id: 'metric-test',
              operation: 'subtract',
              operands: [
                { candidate_id: 'tour-test', field: 'price_quotes', value: 250, evidence_ids: [] },
                { candidate_id: 'tour-other', field: 'price_quotes', value: 50, evidence_ids: [] },
              ],
              result: 980,
              currency: 'VND',
              basis: 'per_adult',
              coverage: 'tour_price',
              comparable: true,
              limitations: ['Chưa gồm phụ thu.'],
              evidence_ids: ['evidence-price'],
            },
          ],
        },
      }),
    );
    expect(html).toContain('class="metric-value">980 ₫');
    expect(html).not.toContain('200 ₫');
    expect(html).toContain('Chưa gồm phụ thu.');
  });
  it('does not mutate the source snapshot during presentation', () => {
    const value = comparison();
    const before = JSON.stringify(value);
    render(value);
    expect(JSON.stringify(value)).toBe(before);
  });
});

describe('processing activity', () => {
  it('orders events by backend sequence and excludes other jobs', () => {
    const job: Job = {
      id: 'job-test',
      resource_id: 'comparison-test',
      kind: 'v2_comparison',
      status: 'partial',
      phase: 'comparison',
      stage: 'comparison',
      resource_ref: 'comparison-test',
      created_at: at,
      deadline_at: at,
      completed_at: at,
      error: null,
      metrics: null,
    };
    const event: JobEvent = {
      seq: 1,
      job_id: 'job-test',
      stage: 'retrieval',
      status: 'completed',
      occurred_at: at,
      source_id: null,
      summary: 'Bước thứ nhất từ backend.',
      counts: null,
      error_code: null,
    };
    const html = renderToStaticMarkup(
      <PreferencesProvider>
        <Activity
          job={job}
          events={[
            { ...event, seq: 2, summary: 'Bước thứ hai từ backend.' },
            { ...event, job_id: 'other-job', summary: 'Không thuộc job này.' },
            event,
          ]}
          onCancel={() => undefined}
        />
      </PreferencesProvider>,
    );
    expect(html.indexOf('Bước thứ nhất')).toBeLessThan(html.indexOf('Bước thứ hai'));
    expect(html).not.toContain('Không thuộc job này.');
    expect(html).toContain('một phần dữ liệu');
  });
});
