import type { WhatIf } from '../../api/types';
import { usePreferences } from '../../app/preferences';
import { formatResultValue } from './Results';

const link = (value: string) => {
  try {
    const u = new URL(value);
    return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password
      ? u.href
      : undefined;
  } catch {
    return undefined;
  }
};
export function WhatIfPanel({
  analysis,
  disabled,
  onAnalyze,
  onApply,
  onEvidence,
}: {
  analysis: WhatIf | null;
  disabled: boolean;
  onAnalyze: () => void;
  onApply: (id: string) => void;
  onEvidence: (id: string) => void;
}) {
  const { t, locale } = usePreferences();
  const show = (value: unknown): string => {
    if (!value || typeof value !== 'object' || Array.isArray(value))
      return formatResultValue(value, locale);
    const v = value as Record<string, unknown>;
    if (v.kind === 'budget')
      return `${formatResultValue(v.amount, locale)} ${String(v.currency ?? '')} ${v.basis === 'per_adult' ? t('/ người lớn', '/ adult') : ''}`;
    if (v.kind === 'number') return formatResultValue(v.amount, locale);
    if (v.kind === 'date') return formatResultValue(v.value, locale);
    if (v.kind === 'set') return formatResultValue(v.items, locale);
    if (typeof v.raw === 'string') return v.raw;
    return t('Giá trị cần kiểm tra trong đề xuất', 'Review the value in the proposal');
  };
  const result = analysis?.result;
  return (
    <section className="what-if-panel" aria-labelledby="what-if-heading">
      <h2 id="what-if-heading">
        {t('Nếu thay đổi điều kiện thì sao?', 'What if your conditions changed?')}
      </h2>
      <p>
        {t(
          'Đo lại lựa chọn trong dữ liệu đã đọc khi bỏ hoặc nới điều kiện. Mỗi thay đổi cần bạn xem và xác nhận.',
          'Measure available options when conditions are removed or relaxed. Every change needs your review and confirmation.',
        )}
      </p>
      <button className="btn" disabled={disabled} onClick={onAnalyze}>
        {t('Phân tích tác động điều kiện', 'Analyze condition impact')}
      </button>
      {result && (
        <>
          <p>
            {t('Yêu cầu gốc', 'Original requirements')}: <strong>{result.baseline.eligible}</strong>{' '}
            {t('đạt', 'eligible')}
            {' · '}
            {result.baseline.ineligible} {t('không đạt', 'ineligible')}
            {' · '}
            {result.baseline.unknown} {t('chưa đủ dữ liệu', 'unknown')}.
          </p>
          <p className="form-hint">
            {t(
              'Kết quả chỉ trong tập dữ liệu đã đọc tại thời điểm phân tích. Tỷ lệ không phải mức quan trọng hay phần trăm đóng góp của điều kiện.',
              'Results apply only to the data read at analysis time. Percentages are not condition importance or contribution.',
            )}
          </p>
          <p>
            {t('Phạm vi', 'Scope')}: {result.candidates.length}{' '}
            {t('lựa chọn đã đọc', 'options read')}
            {typeof result.limits.candidate_limit === 'number' &&
              ` / ${result.limits.candidate_limit} ${t('giới hạn', 'limit')}`}
            {' · '}
            {result.scenarios.length} {t('kịch bản', 'scenarios')}.{' '}
            {t('Phân tích lúc', 'Analyzed at')}{' '}
            {new Date(result.evaluated_at).toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB', {
              timeZone: 'Asia/Ho_Chi_Minh',
            })}
            .
          </p>
          {result.limits.scenarios_truncated === true && (
            <p className="notice">
              {t(
                'Danh sách kịch bản bị giới hạn; chưa xét hết các thay đổi có thể có.',
                'Scenario list is limited; not all possible changes were examined.',
              )}
            </p>
          )}
          {result.scope.all_offers_complete === false && (
            <p className="notice">
              {t(
                'Chưa đọc đủ các mức giá/lịch khởi hành cho mọi tour.',
                'Some tours have incomplete price or departure coverage.',
              )}
            </p>
          )}
          {result.limitations.length > 0 && (
            <ul>
              {result.limitations.map((text, i) => (
                <li key={i}>{text}</li>
              ))}
            </ul>
          )}
          {result.scenarios.length === 0 && (
            <p>
              {t('Chưa có kịch bản đủ dữ liệu để phân tích.', 'No scenarios could be measured.')}
            </p>
          )}
          {result.scenarios.map((s) => (
            <details className="what-if-scenario" key={s.id}>
              <summary>
                {s.label}
                {' · '}
                {s.additional_candidate_ids.length} {t('lựa chọn bổ sung', 'additional options')}
              </summary>
              <p>{s.insight}</p>
              <p>
                {s.population.eligible} {t('đạt', 'eligible')}
                {' · '}
                {s.population.ineligible} {t('không đạt', 'ineligible')}
                {' · '}
                {s.population.unknown} {t('chưa đủ dữ liệu', 'unknown')}
              </p>
              {s.joint_only_candidate_ids.length > 0 && (
                <p>
                  {s.joint_only_candidate_ids.length}{' '}
                  {t(
                    'lựa chọn chỉ xuất hiện khi thay đổi đồng thời cả hai nhóm điều kiện.',
                    'options appear only when both condition groups change together.',
                  )}
                </p>
              )}
              {s.minimal_within_tested_subsets && (
                <p className="form-hint">
                  {t(
                    'Đây là thay đổi tối thiểu trong các nhóm đơn/cặp đã thử; chưa xét mọi tổ hợp.',
                    'This is minimal among the tested single and pair groups, not all possible combinations.',
                  )}
                </p>
              )}
              <dl className="criteria-list">
                <div>
                  <dt>{t('Bị điều kiện gốc loại, nay đạt', 'Originally failed, now eligible')}</dt>
                  <dd>{s.proven_blocked_candidate_ids.length}</dd>
                </div>
                <div>
                  <dt>{t('Trước chưa đủ dữ liệu, nay đạt', 'Originally unknown, now eligible')}</dt>
                  <dd>{s.previously_unknown_candidate_ids.length}</dd>
                </div>
                <div>
                  <dt>{t('Tỷ lệ bị điều kiện gốc giới hạn', 'Measured restriction ratio')}</dt>
                  <dd>
                    {s.restriction_ratio.state === 'computed' &&
                    s.restriction_ratio.percent !== null
                      ? `${s.restriction_ratio.percent.toLocaleString('vi-VN', { maximumFractionDigits: 1 })}% (${s.restriction_ratio.numerator}/${s.restriction_ratio.denominator})`
                      : t('Chưa xác định', 'Not established')}
                    <p className="form-hint">{s.restriction_ratio.meaning}</p>
                  </dd>
                </div>
              </dl>
              {s.top_changed && (
                <p>
                  {t(
                    'Nhóm đứng đầu thay đổi trong kịch bản này.',
                    'The top group changes in this scenario.',
                  )}
                </p>
              )}
              {(s.top_before.length > 0 || s.top_after.length > 0) && (
                <dl className="criteria-list">
                  {[
                    [
                      t('Nhóm đứng đầu theo nhu cầu gốc', 'Original top group'),
                      s.top_before,
                    ] as const,
                    [t('Nhóm đứng đầu trong kịch bản', 'Scenario top group'), s.top_after] as const,
                  ].map(([label, ranks]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>
                        <ol>
                          {ranks.map((r) => (
                            <li key={r.candidate_id}>
                              {String(
                                result.candidates.find((c) => c.candidate_id === r.candidate_id)
                                  ?.title ?? r.candidate_id,
                              )}
                              {r.score_lower !== null &&
                                ` · ${r.score_lower.toFixed(2)}–${r.score_upper!.toFixed(2)}`}
                              {r.tied && ` · ${t('đồng hạng', 'tied')}`}
                            </li>
                          ))}
                        </ol>
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
              {s.rank_changes.length > 0 && (
                <ul>
                  {s.rank_changes.map((c) => {
                    const candidate = result.candidates.find(
                      (x) => x.candidate_id === c.candidate_id,
                    );
                    const title =
                      typeof candidate?.title === 'string' ? candidate.title : c.candidate_id;
                    return (
                      <li key={c.candidate_id}>
                        {title}: {c.before.rank} → {c.after.rank}
                        {c.after.score_lower !== null &&
                          ` · ${c.after.score_lower.toFixed(2)}–${c.after.score_upper!.toFixed(2)}`}
                        {c.after.tied && ` · ${t('đồng hạng', 'tied')}`}
                      </li>
                    );
                  })}
                </ul>
              )}
              {s.tradeoffs.length > 0 && (
                <div>
                  <strong>{t('Đánh đổi khi thay đổi nhu cầu', 'Tradeoffs')}</strong>
                  <ul>
                    {s.tradeoffs.map((item, i) => {
                      const before =
                        item.before &&
                        typeof item.before === 'object' &&
                        !Array.isArray(item.before)
                          ? item.before
                          : null;
                      const after =
                        item.after && typeof item.after === 'object' && !Array.isArray(item.after)
                          ? item.after
                          : null;
                      const group = result.groups.find((g) =>
                        g.condition_ids.includes(String(item.condition_id)),
                      );
                      return (
                        <li key={i}>
                          {group?.label || t('Điều kiện', 'Condition')}: {show(before?.value)} →{' '}
                          {after
                            ? show(after.value)
                            : t('Bỏ điều kiện này', 'Remove this condition')}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
              {s.witnesses.map((w) => (
                <article key={w.candidate_id}>
                  <h3>{w.title || t('Lựa chọn bổ sung', 'Additional option')}</h3>
                  {link(w.canonical_url) && (
                    <a href={link(w.canonical_url)} target="_blank" rel="noopener noreferrer">
                      {t('Mở tour nguồn', 'Open source tour')}
                    </a>
                  )}
                  <div className="button-row">
                    {w.evidence_ids.map((id, i) => (
                      <button className="text-action" key={id} onClick={() => onEvidence(id)}>
                        {t('Dữ kiện', 'Evidence')} {i + 1}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
              {(s.witnesses_truncated || s.rank_changes_truncated) && (
                <p className="form-hint">
                  {t(
                    'Một phần ví dụ hoặc thay đổi thứ hạng đã được giới hạn.',
                    'Some witnesses or rank changes are omitted by the analysis limits.',
                  )}
                </p>
              )}
              {s.limitations.map((text, i) => (
                <p className="form-hint" key={i}>
                  {text}
                </p>
              ))}
              <button
                className="btn"
                disabled={disabled || s.edits.length === 0 || s.state !== 'measured'}
                onClick={() => onApply(s.id)}
              >
                {t('Xem đề xuất sửa nhu cầu', 'Review proposed requirement changes')}
              </button>
            </details>
          ))}
        </>
      )}
    </section>
  );
}
