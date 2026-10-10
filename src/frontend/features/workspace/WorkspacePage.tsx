import { useEffect, useRef, useState } from 'react';
import { buildCreateRequirement, buildEdits, directBudgetReason } from '../../api/form';
import { directMonthReason } from '../../api/travelFilters';
import type { ConditionValue, JsonValue, Requirement, Tree } from '../../api/types';
import type { LocalSession } from '../../app/storage';
import { usePreferences } from '../../app/preferences';
import { Dialog } from '../../components/Dialog';
import { Icon } from '../../components/Icon';
import { CriteriaForm, PreferenceSliders } from './CriteriaForm';
import { Activity, Results } from './Results';
import { WhatIfPanel } from './WhatIfPanel';
import type { useWorkspace } from './useWorkspace';

type Workspace = ReturnType<typeof useWorkspace>;
const fieldNames: Record<string, [string, string]> = {
  destinations: ['Điểm đến', 'Destination'],
  departure_origin: ['Khởi hành', 'Origin'],
  departure_date: ['Ngày đi', 'Departure date'],
  return_date: ['Ngày về', 'Return date'],
  estimated_cost: ['Ngân sách', 'Budget'],
  duration_days: ['Thời lượng', 'Duration'],
  hotel_stars_min: ['Khách sạn', 'Hotel'],
  shopping_stops: ['Điểm mua sắm', 'Shopping stops'],
  transport: ['Phương tiện', 'Transport'],
  included_services: ['Dịch vụ', 'Services'],
  party: ['Thành viên', 'Party'],
  notes: ['Ghi chú', 'Notes'],
  reference_urls: ['Tour tham chiếu', 'Reference tours'],
  hard_tree: ['Kết hợp điều kiện bắt buộc', 'Required condition grouping'],
  preference_tree: ['Kết hợp các ưu tiên', 'Preference grouping'],
  'preference_levels.cost': ['Tiết kiệm chi phí', 'Save on cost'],
  'preference_levels.comfort': ['Khách sạn tiện nghi', 'Hotel comfort'],
  'preference_levels.pace': ['Nhịp đi thư thả', 'Relaxed pace'],
  'preference_levels.culture': ['Trải nghiệm văn hóa', 'Cultural experiences'],
};
const safeUrl = (value: string | null) => {
  try {
    const u = new URL(value || '');
    return ['http:', 'https:'].includes(u.protocol) ? u.href : null;
  } catch {
    return null;
  }
};
function showValue(value: JsonValue | ConditionValue | undefined, english = false): string {
  if (value === null || value === undefined) return '—';
  if (typeof value !== 'object') return String(value);
  if (Array.isArray(value)) return value.map((item) => showValue(item, english)).join(', ');
  if ('kind' in value) {
    switch (value.kind) {
      case 'set':
        return (value as { items: string[] }).items.join(', ');
      case 'date':
        return `${(value as { value: string }).value}${'upper' in value && value.upper ? ` — ${value.upper}` : ''}`;
      case 'number':
        return String((value as { amount: number }).amount);
      case 'budget': {
        const budget = value as {
          amount: string | number;
          upper?: string | number | null;
          currency?: string;
          basis?: string;
          coverage?: string;
          measure?: string;
        };
        const amount = (v: string | number) =>
          /^\d+$/.test(String(v))
            ? BigInt(v).toLocaleString(english ? 'en-GB' : 'vi-VN')
            : String(v);
        const basis =
          budget.basis === 'group_total'
            ? english
              ? 'whole party'
              : 'cả nhóm'
            : budget.basis === 'per_person'
              ? english
                ? 'per person'
                : 'mỗi người'
              : budget.basis === 'per_adult'
                ? english
                  ? 'per adult'
                  : 'mỗi người lớn'
                : english
                  ? 'basis unknown'
                  : 'đơn vị chưa rõ';
        const coverage =
          budget.coverage === 'trip_total'
            ? english
              ? 'trip total'
              : 'toàn bộ chuyến đi'
            : english
              ? 'tour price'
              : 'giá tour';
        const measure =
          budget.measure === 'listed'
            ? english
              ? 'listed price'
              : 'giá niêm yết'
            : english
              ? 'payable cost'
              : 'chi phí thực trả';
        return `${amount(budget.amount)}${budget.upper ? ` — ${amount(budget.upper)}` : ''} ${budget.currency || ''} · ${basis} · ${coverage} · ${measure}`;
      }
      case 'entities':
        return (value as { members: { raw: string }[] }).members
          .map((member) => member.raw)
          .join(', ');
      case 'qualitative':
      case 'temporal':
        return String((value as { raw: string }).raw);
      case 'unresolved':
        return String((value as { raw: string }).raw);
    }
  }
  if ('field' in value && 'value' in value) return showValue(value.value as JsonValue, english);
  return Object.entries(value)
    .map(([key, item]) => `${key}: ${showValue(item as JsonValue, english)}`)
    .join(' · ');
}
function TreeSummary({ tree, requirement }: { tree: Tree; requirement: Requirement }) {
  const { t } = usePreferences();
  const field = requirement.conditions.find((c) => c.id === tree.condition_id)?.field;
  if (tree.kind === 'predicate')
    return (
      <span>
        {field && fieldNames[field] ? t(...fieldNames[field]) : t('Điều kiện', 'Condition')}
      </span>
    );
  return (
    <span className="tree-expression">
      (
      {tree.children?.map((child, i) => (
        <span key={i}>
          {i > 0 && <strong> {tree.kind === 'all' ? t('VÀ', 'AND') : t('HOẶC', 'OR')} </strong>}
          <TreeSummary tree={child} requirement={requirement} />
        </span>
      ))}
      )
    </span>
  );
}

export function WorkspacePage({
  session,
  workspace: w,
  onDraft,
}: {
  session: LocalSession;
  workspace: Workspace;
  onDraft: (v: LocalSession['draft']) => void;
}) {
  const { t, locale } = usePreferences();
  const { state: s, catalog } = w;
  const [editing, setEditing] = useState(false);
  const [review, setReview] = useState(false);
  const [composer, setComposer] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const proposalRef = useRef<HTMLElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    setEditing(false);
    setReview(false);
    setComposer('');
    setAnswers({});
    setLocalError(null);
  }, [session.id]);
  useEffect(() => {
    if (s.proposal && !s.busy) {
      confirmRef.current?.scrollIntoView({
        block: 'center',
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? 'instant'
          : 'smooth',
      });
      confirmRef.current?.focus({ preventScroll: true });
    }
  }, [s.proposal, s.busy]);
  const draftBase = s.proposal?.preview || s.requirement;
  let dirty = false;
  try {
    dirty = !!draftBase && buildEdits(session.draft, draftBase, catalog || undefined).length > 0;
  } catch {
    dirty = !!draftBase;
  }
  const outdated =
    !!s.comparison?.result &&
    !!s.requirement &&
    s.comparison.result.revision !== s.requirement.revision;
  const submit = () => {
    setLocalError(null);
    if (s.requirement) {
      void w.saveEdits(session.draft);
      setEditing(false);
    } else if (session.draft.mode === 'structured') {
      try {
        buildCreateRequirement(session.draft, catalog || undefined);
        setReview(true);
      } catch (error) {
        setLocalError(
          error instanceof Error
            ? error.message
            : t('Kiểm tra lại nhu cầu.', 'Check your requirements.'),
        );
      }
    } else void w.create(session.draft);
  };
  const name = (field: string) => {
    const key = fieldNames[field] ? field : field.split('.').at(-1) || field;
    return fieldNames[key] ? t(...fieldNames[key]) : key.replaceAll('_', ' ');
  };
  const pretty = (value: JsonValue | ConditionValue | undefined) =>
    showValue(value, locale === 'en');
  const operator = (value: string) =>
    ({
      eq: '=',
      neq: '≠',
      gte: '≥',
      lte: '≤',
      near: t('Khoảng', 'About'),
      prefer_low: t('Ưu tiên thấp', 'Prefer lower'),
      prefer_high: t('Ưu tiên cao', 'Prefer higher'),
      in: t('Trong', 'In'),
      contains: t('Có', 'Contains'),
      contains_any: t('Có một trong', 'Includes any'),
      contains_all: t('Có tất cả', 'Includes all'),
    })[value] || value.replaceAll('_', ' ');
  const show = (value: ConditionValue) =>
    value.kind === 'set'
      ? value.items
          .map(
            (id) =>
              catalog?.destinations.find((d) => d.id === id)?.label ||
              catalog?.origins.find((d) => d.id === id)?.label ||
              catalog?.transports.find((d) => d.id === id)?.label ||
              id,
          )
          .join(', ')
      : pretty(value);
  const heading = s.requirement
    ? t('Nhìn rõ từng lựa chọn.', 'See each option clearly.')
    : t('Chuyến đi bắt đầu từ điều bạn cần.', 'Start with what matters to you.');
  return (
    <>
      <header className="workspace-heading">
        <div>
          <span className="eyebrow">{t('TÌM TOUR', 'FIND A TOUR')}</span>
          <h1>{heading}</h1>
          <p>
            {t(
              'Giữ nhu cầu của bạn ở bên cạnh. Đối chiếu tour, dữ kiện và nguồn.',
              'Keep your requirements close. Compare tours, facts and sources.',
            )}
          </p>
        </div>
        {s.requirement && (
          <button
            className="btn btn-primary"
            disabled={s.busy || !!s.proposal || dirty || !s.requirement.readiness.can_collect_data}
            onClick={() => void w.search()}
          >
            {t('Tìm kiếm', 'Search')}
            <Icon name="search" />
          </button>
        )}
      </header>
      {(s.error || localError || w.catalogError) && (
        <div className="notice error" role="alert">
          <p>{s.error || localError || w.catalogError}</p>
          {s.discardIds.length > 1 && (
            <button
              className="btn"
              disabled={s.busy}
              onClick={() => void w.discard(s.discardIds[0], s.discardIds.slice(1))}
            >
              {t('Bỏ cùng những thay đổi liên quan', 'Discard related changes together')}
            </button>
          )}
          <button
            className="text-action"
            onClick={() => {
              setLocalError(null);
              if (!catalog) void w.reloadCatalog();
              else void w.refresh();
            }}
          >
            {t('Tải lại trạng thái', 'Reload state')}
            <Icon name="arrow" />
          </button>
        </div>
      )}
      {!catalog ? (
        <div className="form-skeleton" role="status">
          {t('Đang tải danh mục…', 'Loading catalog…')}
        </div>
      ) : (
        <>
          <div
            className={`sync-banner ${outdated ? 'stale' : s.proposal || dirty ? 'pending' : s.busy ? 'running' : s.requirement ? 'matched' : ''}`}
            role="status"
          >
            <Icon name={s.proposal || dirty || outdated ? 'info' : 'check'} />
            <div>
              <strong>
                {s.busy
                  ? t('Đang xử lý yêu cầu', 'Processing your request')
                  : s.proposal
                    ? t('Thay đổi đang chờ xác nhận', 'Changes await confirmation')
                    : dirty
                      ? t('Bạn có thay đổi chưa gửi', 'You have unsent changes')
                      : outdated
                        ? t(
                            'Bảng đang xem theo nhu cầu trước',
                            'This comparison uses earlier requirements',
                          )
                        : s.requirement
                          ? t('Nhu cầu đã được xác nhận', 'Requirements confirmed')
                          : t(
                              'Bạn kiểm tra nhu cầu trước khi tìm',
                              'Review your requirements before searching',
                            )}
              </strong>
              <p>
                {s.proposal || dirty
                  ? t(
                      'Xác nhận hoặc hủy thay đổi để tiếp tục tìm kiếm.',
                      'Confirm or discard changes before searching.',
                    )
                  : outdated
                    ? t(
                        'Bấm Tìm kiếm để đối chiếu theo nhu cầu hiện tại.',
                        'Search again to compare your current requirements.',
                      )
                    : t(
                        'Xác nhận nhu cầu và Tìm kiếm là hai bước riêng.',
                        'Confirming requirements and searching are separate steps.',
                      )}
              </p>
            </div>
          </div>
          {!s.requirement && !s.proposal ? (
            <div className="form-layout">
              <section className="form-card">
                <CriteriaForm
                  values={session.draft}
                  catalog={catalog}
                  onChange={onDraft}
                  onSubmit={submit}
                  busy={s.busy}
                />
              </section>
              <aside className="form-story">
                <img
                  src="/assets/kyoto.jpg"
                  alt={t('Cổng torii đỏ tại Kyoto', 'Red torii gates in Kyoto')}
                />
                <h2>
                  {t(
                    'Một chuyến đi hợp ý, bắt đầu bằng nhu cầu rõ ràng.',
                    'A fitting trip starts with clear requirements.',
                  )}
                </h2>
                <p>
                  {t(
                    'Đi cùng giúp đặt các lựa chọn cạnh nhau. Bạn giữ quyền quyết định.',
                    'Di cung puts your options side by side. The decision stays yours.',
                  )}
                </p>
              </aside>
            </div>
          ) : (
            <div className="results-layout">
              <aside className="criteria-panel">
                <section>
                  <div className="section-heading">
                    <h2>{t('Nhu cầu của bạn', 'Your requirements')}</h2>
                    <button
                      className="text-action"
                      onClick={() => setEditing(!editing)}
                      disabled={s.busy}
                    >
                      {editing ? t('Thu gọn', 'Collapse') : t('Sửa nhiều mục', 'Edit requirements')}
                      <Icon name="edit" />
                    </button>
                  </div>
                  {editing ? (
                    <CriteriaForm
                      values={session.draft}
                      catalog={catalog}
                      onChange={onDraft}
                      onSubmit={submit}
                      busy={s.busy}
                      editing
                      budgetLocked={draftBase ? directBudgetReason(draftBase) : null}
                      monthsLocked={draftBase ? directMonthReason(draftBase) : null}
                    />
                  ) : (
                    draftBase && (
                      <>
                        <dl className="criteria-list">
                          {draftBase.conditions.map((c) => (
                            <div key={c.id}>
                              <dt>
                                {name(c.field)}{' '}
                                <span className="condition-strength">
                                  {c.strength === 'hard'
                                    ? t('Bắt buộc', 'Required')
                                    : c.strength === 'soft'
                                      ? t('Ưu tiên', 'Preferred')
                                      : t('Cần làm rõ', 'Unresolved')}
                                </span>
                              </dt>
                              <dd>
                                <button
                                  className="criterion-value"
                                  disabled={s.busy}
                                  onClick={() => setEditing(true)}
                                >
                                  {show(c.value)} <Icon name="edit" size={14} />
                                </button>{' '}
                                <small>{operator(c.operator)}</small>
                              </dd>
                            </div>
                          ))}
                          {draftBase.party.adults !== null && (
                            <div>
                              <dt>{t('Thành viên', 'Party')}</dt>
                              <dd>
                                {draftBase.party.adults} {t('người lớn', 'adults')}
                                {draftBase.party.children.length > 0 &&
                                  ` · ${draftBase.party.children.length} ${t('trẻ em', 'children')}`}
                              </dd>
                            </div>
                          )}
                          {['duration_days', 'hotel_stars_min', 'shopping_stops', 'transport']
                            .filter((field) => !draftBase.conditions.some((c) => c.field === field))
                            .map((field) => (
                              <div key={field}>
                                <dt>{name(field)}</dt>
                                <dd>
                                  <button
                                    className="criterion-value"
                                    disabled={s.busy}
                                    onClick={() => setEditing(true)}
                                  >
                                    {t('Chưa chỉ định', 'Not specified')}
                                    <Icon name="edit" size={14} />
                                  </button>
                                </dd>
                              </div>
                            ))}
                        </dl>
                        <PreferenceSliders
                          values={session.draft}
                          catalog={catalog}
                          onChange={onDraft}
                          disabled={s.busy}
                        />
                        {draftBase.notes && <p className="notes-copy">{draftBase.notes}</p>}
                        {draftBase.reference_urls.length > 0 && (
                          <div className="reference-links">
                            {draftBase.reference_urls.map((url) => (
                              <p key={url}>
                                <a
                                  href={safeUrl(url) || undefined}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  {url}
                                  <Icon name="source" />
                                </a>
                              </p>
                            ))}
                          </div>
                        )}
                        {draftBase.hard_tree?.kind === 'any' && (
                          <p>
                            <TreeSummary tree={draftBase.hard_tree} requirement={draftBase} />
                          </p>
                        )}
                      </>
                    )
                  )}
                  {s.requirement?.readiness.blockers.length ? (
                    <div className="notice">
                      <strong>{t('Cần làm rõ', 'Needs clarification')}</strong>
                      {s.requirement.readiness.blockers.map((b) => (
                        <p key={b}>{b}</p>
                      ))}
                    </div>
                  ) : null}
                </section>
                {s.proposal && (
                  <section
                    className="proposal"
                    ref={proposalRef}
                    aria-labelledby="proposal-heading"
                  >
                    <h2 id="proposal-heading">{t('Kiểm tra thay đổi', 'Review changes')}</h2>
                    <p>
                      {t(
                        'Nhu cầu chỉ cập nhật sau khi xác nhận.',
                        'Requirements update only after confirmation.',
                      )}
                    </p>
                    <ul className="diff-list">
                      {s.proposal.changes.map((change) => (
                        <li key={change.id}>
                          <strong>
                            {name(
                              change.condition_id
                                ? draftBase?.conditions.find((c) => c.id === change.condition_id)
                                    ?.field || change.path
                                : change.path,
                            )}
                          </strong>
                          <div>
                            <del>{pretty(change.before)}</del>
                            <Icon name="arrow" />
                            <ins>{pretty(change.after)}</ins>
                          </div>
                          <p>{change.reason}</p>
                          <button
                            type="button"
                            className="text-action"
                            disabled={s.busy || dirty}
                            onClick={() => void w.discard(change.id)}
                          >
                            {t('Bỏ thay đổi này', 'Discard this change')}
                          </button>
                        </li>
                      ))}
                    </ul>
                    {s.proposal.clarifications.map((item, index) => {
                      if (!item || typeof item !== 'object' || Array.isArray(item))
                        return <p key={index}>{pretty(item)}</p>;
                      const id = typeof item.id === 'string' ? item.id : null;
                      return (
                        <div className="clarification" key={id || index}>
                          <p>{item.question}</p>
                          {id && (
                            <form
                              onSubmit={(event) => {
                                event.preventDefault();
                                void w.clarify(id, answers[id] || '');
                              }}
                            >
                              <label className="field">
                                {t('Câu trả lời của bạn', 'Your answer')}
                                <input
                                  required
                                  value={answers[id] || ''}
                                  onChange={(event) =>
                                    setAnswers({ ...answers, [id]: event.target.value })
                                  }
                                />
                              </label>
                              <button className="btn" disabled={s.busy || dirty}>
                                {t('Gửi trả lời', 'Submit answer')}
                              </button>
                            </form>
                          )}
                        </div>
                      );
                    })}
                    <div className="proposal-actions">
                      <button
                        ref={confirmRef}
                        className="btn btn-primary"
                        disabled={
                          s.busy ||
                          dirty ||
                          s.proposal.status !== 'pending' ||
                          !(
                            s.proposal.preview.readiness.can_confirm ??
                            s.proposal.preview.readiness.can_collect_data
                          )
                        }
                        onClick={() => void w.confirm()}
                      >
                        {t('Xác nhận tất cả', 'Confirm all')}
                        <Icon name="check" />
                      </button>
                      <button
                        className="btn"
                        disabled={s.busy}
                        onClick={() => void w.cancelProposal()}
                      >
                        {t('Hủy tất cả', 'Discard all')}
                      </button>
                    </div>
                  </section>
                )}
                {dirty && !editing && (
                  <button
                    className="btn"
                    disabled={s.busy}
                    onClick={() => void w.saveEdits(session.draft)}
                  >
                    {t('Xem thay đổi', 'Review changes')}
                  </button>
                )}
                <section className="chat">
                  <div className="section-heading">
                    <h2>{t('Trao đổi về chuyến đi', 'Discuss your trip')}</h2>
                    <Icon name="route" />
                  </div>
                  <div className="chat-transcript" aria-live="polite">
                    {session.chat.length === 0 && (
                      <p className="form-hint">
                        {t(
                          'Nhắn để sửa nhu cầu, hỏi về bảng hoặc yêu cầu nhóm tour khác.',
                          'Ask to edit requirements, discuss the comparison or find another group.',
                        )}
                      </p>
                    )}
                    {session.chat.map((line) => (
                      <p key={line.id} className={`chat-message ${line.role}`}>
                        <strong>{line.role === 'user' ? t('Bạn', 'You') : 'Đi cùng'}</strong>
                        {line.text}
                      </p>
                    ))}
                  </div>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      const text = composer.trim();
                      if (!text) return;
                      setComposer('');
                      void w.sendMessage(text);
                    }}
                  >
                    <label className="sr-only" htmlFor="chat-composer">
                      {t('Tin nhắn', 'Message')}
                    </label>
                    <textarea
                      id="chat-composer"
                      rows={3}
                      maxLength={catalog.limits.text_characters}
                      value={composer}
                      onChange={(e) => setComposer(e.target.value)}
                      placeholder={t(
                        'Ví dụ: đổi ngân sách, tìm nhóm khác…',
                        'For example: change the budget, find another group…',
                      )}
                    />
                    <button className="btn" disabled={s.busy || !composer.trim()}>
                      {t('Gửi', 'Send')}
                      <Icon name="arrow" />
                    </button>
                  </form>
                </section>
              </aside>
              <div className="results-panel">
                <Activity events={s.events} job={s.job} onCancel={() => void w.cancelJob()} />
                <Results
                  comparison={s.comparison}
                  busy={s.busy || !!s.proposal || dirty || outdated}
                  onOfferChange={(tourId, offerId) => void w.offerChange(tourId, offerId)}
                  onEvidence={(id) => void w.openEvidence(id)}
                />
                {s.comparison?.result?.origin === 'source' && (
                  <WhatIfPanel
                    analysis={
                      s.whatIf?.result?.comparison_id === s.comparison.id &&
                      s.whatIf.result.revision === s.requirement?.revision
                        ? s.whatIf
                        : null
                    }
                    disabled={s.busy || !!s.proposal || dirty || outdated}
                    onAnalyze={() => void w.analyze()}
                    onApply={(id) => void w.applyScenario(id)}
                    onEvidence={(id) => void w.openEvidence(id)}
                  />
                )}
              </div>
            </div>
          )}
          {s.requirement && session.runs.length > 0 && (
            <nav className="run-history" aria-label={t('Các lượt tìm', 'Search history')}>
              {session.runs.map((run, index) => (
                <button
                  className="btn"
                  key={run.id}
                  aria-pressed={s.comparison?.id === run.id}
                  disabled={s.busy}
                  onClick={() => void w.loadRun(run.id)}
                >
                  {t('Lượt', 'Search')} {index + 1}
                </button>
              ))}
            </nav>
          )}
          {s.busy && !s.requirement && (
            <Activity events={s.events} job={s.job} onCancel={() => void w.cancelJob()} />
          )}
        </>
      )}
      <Dialog
        open={review}
        title={t('Xác nhận nhu cầu chuyến đi', 'Confirm your trip requirements')}
        onClose={() => setReview(false)}
      >
        <dl className="criteria-list">
          <div>
            <dt>{t('Điểm đến', 'Destination')}</dt>
            <dd>
              {catalog?.destinations.find((d) => d.id === session.draft.destinations[0])?.label}
            </dd>
          </div>
          <div>
            <dt>{t('Khởi hành', 'Departure')}</dt>
            <dd>
              {catalog?.origins.find((d) => d.id === session.draft.departureOrigin)?.label} ·{' '}
              {session.draft.departureMonths.length
                ? session.draft.departureMonths
                    .map((month) =>
                      new Date(`${month}-01T12:00:00Z`).toLocaleDateString(
                        locale === 'vi' ? 'vi-VN' : 'en-GB',
                        { month: 'long', year: 'numeric', timeZone: 'UTC' },
                      ),
                    )
                    .join(', ')
                : session.draft.departureDate}
            </dd>
          </div>
          <div>
            <dt>{t('Ngân sách / người lớn', 'Budget / adult')}</dt>
            <dd>
              {Number(session.draft.budgetMin || 0).toLocaleString(
                locale === 'vi' ? 'vi-VN' : 'en-GB',
              )}{' '}
              – {Number(session.draft.budget).toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB')}{' '}
              VND
            </dd>
          </div>
          <div>
            <dt>{t('Thành viên', 'Party')}</dt>
            <dd>
              {session.draft.adults} {t('người lớn', 'adults')} · {session.draft.childAges.length}{' '}
              {t('trẻ em', 'children')}
            </dd>
          </div>
          {session.draft.durationDays && (
            <div>
              <dt>{t('Thời lượng khoảng', 'Approximate duration')}</dt>
              <dd>
                {session.draft.durationDays} {t('ngày', 'days')}
              </dd>
            </div>
          )}
        </dl>
        <p>
          {t(
            'Xác nhận lưu nhu cầu. Bạn bấm Tìm kiếm ở bước tiếp theo.',
            'Confirmation saves your requirements. Search in the next step.',
          )}
        </p>
        <button
          className="btn btn-primary"
          onClick={() => {
            setReview(false);
            void w.create(session.draft);
          }}
        >
          {t('Xác nhận nhu cầu', 'Confirm requirements')}
          <Icon name="check" />
        </button>
      </Dialog>
      <Dialog
        open={w.evidenceOpen}
        title={t('Dữ kiện và nguồn', 'Fact and source')}
        onClose={w.closeEvidence}
      >
        {w.evidenceError ? (
          <p role="alert">{w.evidenceError}</p>
        ) : w.evidence ? (
          w.evidence.quality.origin === 'synthetic' ? (
            <p>{t('Nguồn dữ kiện chưa được kết nối.', 'Source evidence is not connected.')}</p>
          ) : (
            <>
              <span className="eyebrow">{w.evidence.publisher}</span>
              <blockquote lang="vi">{w.evidence.raw_quote}</blockquote>
              <dl className="criteria-list">
                <div>
                  <dt>{t('Ghi nhận lúc', 'Observed at')}</dt>
                  <dd>
                    {Number.isFinite(Date.parse(w.evidence.observed_at))
                      ? new Date(w.evidence.observed_at).toLocaleString(
                          locale === 'vi' ? 'vi-VN' : 'en-GB',
                          { timeZone: 'Asia/Ho_Chi_Minh', hour12: false },
                        )
                      : t('Chưa có thời điểm hợp lệ', 'No valid timestamp')}
                  </dd>
                </div>
                <div>
                  <dt>{t('Trạng thái xác minh', 'Verification')}</dt>
                  <dd>
                    {w.evidence.quality.verification === 'independently_verified'
                      ? t('Đã xác minh độc lập', 'Independently verified')
                      : w.evidence.quality.verification === 'catalog_validated'
                        ? t('Đã kiểm tra bản ghi catalog', 'Catalog record validated')
                        : w.evidence.quality.verification === 'supplier_published'
                          ? t('Nhà cung cấp công bố', 'Supplier published')
                          : t('Chưa xác minh', 'Unverified')}
                  </dd>
                </div>
                <div>
                  <dt>{t('Cách lấy dữ kiện', 'Collection method')}</dt>
                  <dd>
                    {w.evidence.method === 'database_record'
                      ? t(
                          'Bản ghi dữ liệu; chưa xác minh nội dung website',
                          'Database record; website content is not verified',
                        )
                      : w.evidence.method === 'html'
                        ? t('Nội dung trang nguồn', 'Source page content')
                        : t('Dữ liệu có cấu trúc từ nguồn', 'Structured source data')}
                  </dd>
                </div>
              </dl>
              {w.evidence.locator.section_title && <p>{w.evidence.locator.section_title}</p>}
              {w.evidence.deep_link.reason && (
                <p className="form-hint">{w.evidence.deep_link.reason}</p>
              )}
              {safeUrl(w.evidence.deep_link.url || w.evidence.source_url) && (
                <a
                  className="btn"
                  href={safeUrl(w.evidence.deep_link.url || w.evidence.source_url)!}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t('Mở nguồn', 'Open source')}
                  <Icon name="source" />
                </a>
              )}
            </>
          )
        ) : (
          <p role="status">{t('Đang tải dữ kiện…', 'Loading evidence…')}</p>
        )}
      </Dialog>
    </>
  );
}
