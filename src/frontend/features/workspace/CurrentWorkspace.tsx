import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormValues } from '../../api/form';
import {
  CurrentBackendClient,
  type CurrentCatalog,
  type CurrentComparison,
  type CurrentRequirement,
} from '../../api/current';
import { getAccess, putAccess, type LocalSession, type SessionAccess } from '../../app/storage';
import { usePreferences } from '../../app/preferences';
import './CurrentWorkspace.css';

const accessFlights = new Map<string, Promise<SessionAccess>>();

async function accessFor(session: LocalSession): Promise<SessionAccess> {
  const saved = getAccess(session.id);
  if (saved) return saved;
  if (session.requirementId)
    throw new Error('Phiên backend đã hết hạn. Bản nháp vẫn còn; hãy tạo phiên mới để tìm tiếp.');
  const pending = accessFlights.get(session.id);
  if (pending) return pending;
  const request = new CurrentBackendClient()
    .createSession()
    .then((created) => {
      const access = {
        token: created.token,
        expiresAt: created.expires_at,
        backendId: created.session_id || created.id,
      };
      putAccess(session.id, access);
      return access;
    })
    .finally(() => accessFlights.delete(session.id));
  accessFlights.set(session.id, request);
  return request;
}

function currentForm(draft: FormValues, catalog: CurrentCatalog): Record<string, unknown> {
  const unsupported: string[] = [];
  if (draft.mode === 'urls' || draft.referenceUrls.length) unsupported.push('URL tours');
  if (draft.returnDate || draft.departureMonths.length)
    unsupported.push('return dates/month ranges');
  if (draft.budgetMin) unsupported.push('budget ranges');
  if (draft.budget && draft.budgetBasis !== 'per_adult') unsupported.push('non-adult budget basis');
  if (draft.childAges.length) unsupported.push('child-age pricing');
  if (draft.hotelStars) unsupported.push('hotel rating');
  if (draft.shopping !== 'any') unsupported.push('shopping preference');
  if (draft.transport.length > 1) unsupported.push('multiple transport choices');
  if (draft.includedServices.length) unsupported.push('included services');
  if (draft.notes.trim()) unsupported.push('additional notes');
  if (Object.values(draft.preferenceLevels).some((level) => level !== 3))
    unsupported.push('soft ranking preferences');
  if (unsupported.length)
    throw new Error(
      `These criteria are not supported by the current backend and were not sent: ${unsupported.join(', ')}.`,
    );

  for (const [label, value] of [
    ['budget', draft.budget],
    ['duration', draft.durationDays],
  ] as const) {
    if (
      value &&
      (!/^\d+$/u.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) <= 0)
    )
      throw new Error(`${label} must be a positive whole number.`);
  }
  if (draft.budget && Number(draft.budget) > 10 ** 15)
    throw new Error('Budget is above the supported numeric range.');
  if (!Number.isInteger(draft.adults) || draft.adults < 0 || draft.adults > 100)
    throw new Error('Adult count must be a whole number from 1 to 100.');
  if (draft.departureDate) {
    const parsed = new Date(`${draft.departureDate}T00:00:00Z`);
    if (
      !/^\d{4}-\d{2}-\d{2}$/u.test(draft.departureDate) ||
      Number.isNaN(parsed.getTime()) ||
      parsed.toISOString().slice(0, 10) !== draft.departureDate
    )
      throw new Error('Departure date is invalid.');
  }

  const destination = draft.destinations[0]?.trim();
  if (destination && !catalog.destinations.includes(destination))
    throw new Error('Choose a destination from the backend catalog, or describe it in your text.');
  const form: Record<string, unknown> = {};
  if (draft.destinations.length) form.destinations = draft.destinations;
  if (draft.departureOrigin.trim()) form.departure_city = draft.departureOrigin.trim();
  if (draft.departureDate) form.date_from = draft.departureDate;
  if (draft.budget) form.budget_max = Number(draft.budget);
  if (draft.durationDays) form.duration_days = Number(draft.durationDays);
  if (draft.transport.length === 1) form.transport = draft.transport[0];
  if (draft.adults > 0) form.travelers = draft.adults;
  return form;
}

function display(value: unknown): string {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function safeUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function conditionState(comparison: CurrentComparison, offerId: string) {
  const states = comparison.evaluations.filter((item) => item.offer_id === offerId);
  if (states.some((item) => item.state === 'fail')) return 'fail';
  if (states.some((item) => item.state === 'unknown')) return 'unknown';
  return states.length ? 'pass' : 'unknown';
}

export function CurrentWorkspace({
  session,
  onChangeSession,
}: {
  session: LocalSession;
  onChangeSession: (changes: Partial<LocalSession>) => void;
}) {
  const { t } = usePreferences();
  const [client, setClient] = useState<CurrentBackendClient | null>(null);
  const [catalog, setCatalog] = useState<CurrentCatalog | null>(null);
  const [requirement, setRequirement] = useState<CurrentRequirement | null>(null);
  const [comparison, setComparison] = useState<CurrentComparison | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [stale, setStale] = useState(false);
  const [reload, setReload] = useState(0);
  const sessionRef = useRef(session);
  sessionRef.current = session;

  useEffect(() => {
    const target = sessionRef.current;
    let active = true;
    setClient(null);
    setCatalog(null);
    setRequirement(null);
    setComparison(null);
    setBusy(true);
    setError('');
    setStale(false);
    void (async () => {
      try {
        const access = await accessFor(target);
        const api = new CurrentBackendClient(access.token);
        const [loadedCatalog, health] = await Promise.all([api.catalog(), api.health()]);
        if (health.status !== 'ok') throw new Error('Backend is not ready. Try again shortly.');
        if (!active) return;
        setClient(api);
        setCatalog(loadedCatalog);
        if (target.requirementId) {
          const loaded = await api.requirement(target.requirementId);
          if (!active) return;
          setRequirement(loaded.requirement);
          if (target.comparisonId) {
            const previous = await api.comparison(target.comparisonId);
            if (!active) return;
            setComparison(previous.comparison);
          }
        }
      } catch (cause) {
        if (active)
          setError(cause instanceof Error ? cause.message : 'Could not connect to backend.');
      } finally {
        if (active) setBusy(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [session.id, reload]);

  const destinations = catalog?.destinations ?? [];
  const writeDraft = (changes: Partial<FormValues>) => {
    onChangeSession({
      draft: { ...session.draft, ...changes },
      ...(requirement
        ? {
            requirementId: null,
            comparisonId: null,
            pendingComparisonId: null,
            jobId: null,
            analysisId: null,
          }
        : {}),
    });
    if (requirement) {
      setRequirement(null);
      setComparison(null);
      setStale(true);
    }
  };

  const interpret = async () => {
    if (!client || !catalog) return;
    setBusy(true);
    setError('');
    setStale(false);
    try {
      const form = currentForm(session.draft, catalog);
      const result = await client.createRequirement(session.draft.text.trim(), form);
      setRequirement(result.requirement);
      setComparison(null);
      const title =
        session.draft.destinations[0] ||
        session.draft.text.trim().slice(0, 48) ||
        t('Nhu cầu mới', 'New trip');
      onChangeSession({ requirementId: result.requirement.id, comparisonId: null, title });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not interpret this trip.');
    } finally {
      setBusy(false);
    }
  };

  const search = async () => {
    if (!client || !requirement) return;
    setBusy(true);
    setError('');
    try {
      const result = await client.createComparison(requirement.id);
      setComparison(result.comparison);
      onChangeSession({
        comparisonId: result.comparison.id,
        pendingComparisonId: null,
        runs: [
          ...session.runs.filter((run) => run.id !== result.comparison.id),
          { id: result.comparison.id, revision: 1, createdAt: new Date().toISOString() },
        ],
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not compare tours.');
    } finally {
      setBusy(false);
    }
  };

  const tourById = useMemo(
    () => new Map((comparison?.tour_snapshots ?? []).map((tour) => [tour.id, tour])),
    [comparison],
  );

  return (
    <section className="current-workspace" aria-labelledby="current-workspace-title">
      <header className="current-heading">
        <span className="eyebrow">{t('BACKEND HIỆN TẠI', 'CURRENT BACKEND')}</span>
        <h1 id="current-workspace-title">
          {t(
            'Chọn điều quan trọng. Đối chiếu bằng dữ kiện.',
            'Compare tours using the facts available.',
          )}
        </h1>
        <p>
          {t(
            'Mỗi lần tìm được diễn giải riêng. Dữ kiện thiếu, cũ hoặc chưa xác minh sẽ không được xem là đạt.',
            'Each search is interpreted independently. Missing, stale or unverified facts are not treated as a pass.',
          )}
        </p>
      </header>

      {error && (
        <div className="notice error" role="alert">
          <p>{error}</p>
          {!catalog && (
            <button className="btn" disabled={busy} onClick={() => setReload((value) => value + 1)}>
              {t('Thử kết nối lại', 'Try connecting again')}
            </button>
          )}
        </div>
      )}
      {stale && (
        <p className="notice" role="status">
          {t(
            'Nhu cầu đã đổi; hãy diễn giải lại trước khi tìm.',
            'Your criteria changed; interpret them again before searching.',
          )}
        </p>
      )}

      <div className="current-card">
        <h2>{t('Nhu cầu chuyến đi', 'Trip requirements')}</h2>
        <p className="current-hint">
          {t(
            'Backend hiện hỗ trợ điểm đến, nơi/ngày khởi hành, ngân sách tối đa, thời lượng và số người lớn. Điều kiện khác sẽ bị chặn thay vì bỏ qua.',
            'The backend currently supports destinations, departure city/date, maximum budget, duration and adult count. Other criteria are blocked instead of silently ignored.',
          )}
        </p>
        <div className="current-grid">
          <label className="field current-wide">
            {t('Mô tả chuyến đi', 'Describe the trip')}
            <textarea
              rows={4}
              maxLength={2000}
              value={session.draft.text}
              onChange={(event) => writeDraft({ mode: 'text', text: event.target.value })}
              placeholder={t(
                'Ví dụ: Đà Lạt 3 ngày, khởi hành từ TP.HCM, tối đa 8 triệu/người',
                'Example: 3 days in Da Lat, depart from Ho Chi Minh City, up to VND 8 million per person',
              )}
            />
          </label>
          <label className="field">
            {t('Điểm đến trong catalog', 'Destination from catalog')}
            <input
              list={`destinations-${session.id}`}
              value={session.draft.destinations[0] ?? ''}
              onChange={(event) =>
                writeDraft({ destinations: event.target.value ? [event.target.value] : [] })
              }
              placeholder={t('Chọn hoặc nhập trong mô tả', 'Select or describe it above')}
            />
            <datalist id={`destinations-${session.id}`}>
              {destinations.map((destination) => (
                <option key={destination} value={destination} />
              ))}
            </datalist>
          </label>
          <label className="field">
            {t('Khởi hành từ', 'Departure city')}
            <input
              value={session.draft.departureOrigin}
              onChange={(event) => writeDraft({ departureOrigin: event.target.value })}
            />
          </label>
          <label className="field">
            {t('Ngày khởi hành', 'Departure date')}
            <input
              type="date"
              value={session.draft.departureDate}
              onChange={(event) => writeDraft({ departureDate: event.target.value })}
            />
          </label>
          <label className="field">
            {t('Ngân sách tối đa (VND/người lớn)', 'Maximum budget (VND/adult)')}
            <input
              inputMode="numeric"
              value={session.draft.budget}
              onChange={(event) => writeDraft({ budget: event.target.value })}
            />
          </label>
          <label className="field">
            {t('Số ngày', 'Duration (days)')}
            <input
              inputMode="numeric"
              value={session.draft.durationDays}
              onChange={(event) => writeDraft({ durationDays: event.target.value })}
            />
          </label>
          <label className="field">
            {t('Người lớn', 'Adults')}
            <input
              type="number"
              min={0}
              max={100}
              value={session.draft.adults}
              onChange={(event) => writeDraft({ adults: Number(event.target.value) })}
            />
          </label>
        </div>
        <div className="current-actions">
          <button
            className="btn btn-primary"
            disabled={busy || !catalog || !session.draft.text.trim()}
            onClick={() => void interpret()}
          >
            {busy ? t('Đang xử lý…', 'Working…') : t('Diễn giải nhu cầu', 'Interpret requirements')}
          </button>
          {requirement && (
            <button className="btn" disabled={busy} onClick={() => void search()}>
              {t('Tìm và so sánh tour', 'Find and compare tours')}
            </button>
          )}
          {busy && (
            <span role="status">{t('Đang kết nối backend…', 'Connecting to backend…')}</span>
          )}
        </div>
      </div>

      {requirement && (
        <section className="current-card" aria-labelledby="interpreted-title">
          <h2 id="interpreted-title">{t('Backend đã hiểu', 'Interpreted by the backend')}</h2>
          {requirement.missing.length > 0 && (
            <p className="current-missing">
              {t('Thiếu dữ kiện bắt buộc:', 'Missing required information:')}{' '}
              {requirement.missing.join(', ')}
            </p>
          )}
          {requirement.conditions.length ? (
            <ul className="current-condition-list">
              {requirement.conditions.map((condition) => (
                <li key={condition.id}>
                  <span>{condition.field.replaceAll('_', ' ')}</span>
                  <code>
                    {condition.operator} {display(condition.value)}
                  </code>
                  <small>{condition.strength}</small>
                </li>
              ))}
            </ul>
          ) : (
            <p>
              {t(
                'Chưa trích xuất được điều kiện. Có thể tiếp tục để xem dữ kiện nào còn thiếu.',
                'No criteria were extracted. You can continue to see what data is missing.',
              )}
            </p>
          )}
        </section>
      )}

      {comparison && (
        <section className="current-results" aria-labelledby="current-results-title">
          <div className="current-results-heading">
            <div>
              <span className="eyebrow">{t('KẾT QUẢ CÓ LƯU SNAPSHOT', 'PERSISTED SNAPSHOT')}</span>
              <h2 id="current-results-title">
                {t('Các tour có thể đối chiếu', 'Tours available for comparison')}
              </h2>
            </div>
            <small>
              {comparison.candidates_considered} {t('tour đã xem', 'tours considered')}
            </small>
          </div>
          {comparison.ranked.length === 0 ? (
            <p className="notice">
              {t(
                'Chưa có offer nào chứng minh đủ điều kiện. Đây không đồng nghĩa không có tour phù hợp; hãy kiểm tra dữ kiện thiếu hoặc chưa xác minh.',
                'No offer could prove it meets the requirements. This does not prove no suitable tour exists; check missing or unverified data.',
              )}
            </p>
          ) : (
            <div className="current-tour-list">
              {comparison.ranked.map((ranked, index) => {
                const tour = tourById.get(ranked.tour_id);
                const offer = tour?.offers.find((item) => item.id === ranked.offer_id);
                if (!tour || !offer) return null;
                const state = conditionState(comparison, offer.id);
                const url = safeUrl(tour.url || tour.evidence.url);
                return (
                  <article className="current-tour-card" key={`${tour.id}-${offer.id}`}>
                    <div className="current-tour-topline">
                      <span className={`current-state ${state}`}>
                        {t(
                          state === 'pass'
                            ? 'Đã kiểm tra'
                            : state === 'fail'
                              ? 'Không đạt'
                              : 'Cần xác minh',
                          state === 'pass'
                            ? 'Checked'
                            : state === 'fail'
                              ? 'Does not match'
                              : 'Needs verification',
                        )}
                      </span>
                      <span>#{index + 1}</span>
                    </div>
                    <h3>{tour.name || tour.id}</h3>
                    <p className="current-supplier">
                      {tour.supplier || t('Chưa rõ nhà cung cấp', 'Supplier not listed')}
                    </p>
                    <dl className="current-tour-facts">
                      <div>
                        <dt>{t('Điểm đến', 'Destinations')}</dt>
                        <dd>
                          {tour.destinations.join(' · ') || t('Chưa có dữ kiện', 'Not available')}
                        </dd>
                      </div>
                      <div>
                        <dt>{t('Khởi hành', 'Departure')}</dt>
                        <dd>
                          {offer.departure_date || t('Chưa có ngày', 'Date unavailable')} ·{' '}
                          {tour.departure_city || t('Chưa rõ nơi đi', 'City unavailable')}
                        </dd>
                      </div>
                      <div>
                        <dt>{t('Giá công bố', 'Published price')}</dt>
                        <dd>
                          {offer.price == null
                            ? t('Liên hệ / chưa có giá', 'Contact / price unavailable')
                            : `${offer.price.toLocaleString()} ${offer.currency} (${offer.price_basis})`}
                        </dd>
                      </div>
                      <div>
                        <dt>{t('Độ mới / tin cậy', 'Freshness / trust')}</dt>
                        <dd>
                          {offer.price_freshness} ·{' '}
                          {offer.price_trusted
                            ? t('đã xác thực metadata', 'metadata trusted')
                            : t('chưa xác thực', 'not trusted')}
                        </dd>
                      </div>
                    </dl>
                    {tour.exclusions && (
                      <p>
                        <strong>{t('Chưa gồm:', 'Exclusions:')}</strong> {tour.exclusions}
                      </p>
                    )}
                    {tour.inclusions && (
                      <p>
                        <strong>{t('Bao gồm:', 'Inclusions:')}</strong> {tour.inclusions}
                      </p>
                    )}
                    {tour.surcharges && (
                      <p>
                        <strong>{t('Phụ thu:', 'Surcharges:')}</strong> {tour.surcharges}
                      </p>
                    )}
                    {url && (
                      <a href={url} target="_blank" rel="noreferrer">
                        {t('Mở nguồn tour', 'Open tour source')}
                      </a>
                    )}
                  </article>
                );
              })}
            </div>
          )}
          <div className="current-analysis">
            {comparison.analysis.risks.length > 0 && (
              <div>
                <h3>{t('Điểm cần lưu ý', 'Risks to review')}</h3>
                <ul>
                  {comparison.analysis.risks.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {comparison.analysis.hidden_costs.length > 0 && (
              <div>
                <h3>{t('Chi phí cần kiểm tra', 'Costs to verify')}</h3>
                <ul>
                  {comparison.analysis.hidden_costs.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}
    </section>
  );
}
