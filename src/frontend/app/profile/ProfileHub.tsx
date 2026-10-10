import { useId, useState, type FormEvent } from 'react';
import { Dialog } from '../../components/Dialog';
import { usePreferences } from '../preferences';
import { Icon } from '../../components/Icon';
import type { LocalSession } from '../storage';
import {
  defaultPreferences,
  type TravelPreferences,
  type HubItem,
  type SavedTour,
  type TravelTemplate,
} from './contracts';
import { preferenceDraft, templateDraft } from './apply';
import type { Hub } from './useHub';
import type { FormValues } from '../../api/form';

function PreferenceEditor({
  value,
  busy,
  onSave,
  onApply,
}: {
  value: TravelPreferences;
  busy: boolean;
  onSave: (p: TravelPreferences) => Promise<void>;
  onApply: (d: FormValues) => void;
}) {
  const { t } = usePreferences();
  const [draft, setDraft] = useState(() => structuredClone(value));
  const [message, setMessage] = useState('');
  const id = useId();
  const change = (patch: Partial<TravelPreferences>) => {
    setDraft((d) => ({ ...d, ...patch }));
    setMessage('');
  };
  async function save(e: FormEvent) {
    e.preventDefault();
    setMessage('');
    try {
      await onSave(draft);
      setMessage(t('Đã lưu sở thích.', 'Preferences saved.'));
    } catch {
      /* Hub reports the error; retain edits. */
    }
  }
  return (
    <form className="hub-editor" onSubmit={(e) => void save(e)}>
      <p>
        {t(
          'Lưu những điều bạn thường muốn cho chuyến đi. Mỗi lần dùng vẫn được kiểm tra trước khi tìm.',
          'Save what you usually want on a trip. Review each time before searching.',
        )}
      </p>
      <div className="form-grid">
        <label className="field">
          {t('Khách sạn mong muốn', 'Desired hotel standard')}
          <select
            value={draft.hotel_stars ?? ''}
            onChange={(e) =>
              change({ hotel_stars: e.target.value ? Number(e.target.value) : null })
            }
          >
            <option value="">{t('Chưa chọn', 'Not specified')}</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n} {t('sao trở lên', 'stars or above')}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          {t('Thời lượng mong muốn (ngày)', 'Desired duration (days)')}
          <input
            type="number"
            min="1"
            max="90"
            value={draft.duration_days ?? ''}
            onChange={(e) =>
              change({ duration_days: e.target.value ? Number(e.target.value) : null })
            }
          />
        </label>
        <label className="field">
          {t('Điểm mua sắm', 'Shopping stops')}
          <select
            value={draft.shopping}
            onChange={(e) => change({ shopping: e.target.value as 'any' | 'few' })}
          >
            <option value="any">{t('Không có ưu tiên', 'No preference')}</option>
            <option value="few">
              {t('Ưu tiên ít điểm mua sắm', 'Prefer fewer shopping stops')}
            </option>
          </select>
        </label>
        <label className="hub-check">
          <input
            type="checkbox"
            checked={draft.prefer_lower_listed_price}
            onChange={(e) => change({ prefer_lower_listed_price: e.target.checked })}
          />
          {t(
            'Ưu tiên giá tour niêm yết thấp hơn trong nhóm đạt điều kiện',
            'Prefer lower listed tour prices among eligible tours',
          )}
        </label>
      </div>
      <h3>{t('Mức quan trọng', 'Importance')}</h3>
      <p className="form-hint">
        {t(
          'Mức quan trọng không tự tạo yêu cầu về giá hay khách sạn. Cần chọn điều mong muốn ở trên.',
          'Importance alone does not create a price or hotel preference. Choose the desired values above.',
        )}
      </p>
      <div className="hub-levels">
        {(
          [
            ['cost', t('Tiết kiệm chi phí', 'Lower cost')],
            ['comfort', t('Khách sạn và dịch vụ', 'Hotel and services')],
            ['pace', t('Nhịp đi thư thả', 'Relaxed pace')],
            ['culture', t('Trải nghiệm văn hóa', 'Cultural experiences')],
          ] as const
        ).map(([key, label]) => (
          <label key={key} htmlFor={`${id}-${key}`}>
            <span>
              {label} <strong>{draft.levels[key]}/5</strong>
            </span>
            <input
              id={`${id}-${key}`}
              type="range"
              min="1"
              max="5"
              value={draft.levels[key]}
              onChange={(e) =>
                change({ levels: { ...draft.levels, [key]: Number(e.target.value) } })
              }
            />
            {['pace', 'culture'].includes(key) && (
              <small>{t('Đã lưu, chưa dùng để xếp hạng', 'Saved; not used for ranking yet')}</small>
            )}
          </label>
        ))}
      </div>
      <p className="form-hint">
        {t(
          'Giá niêm yết chưa gồm mọi phụ thu. Thời lượng, khách sạn và mua sắm ở đây là ưu tiên mềm.',
          'Listed prices may exclude surcharges. Duration, hotel and shopping choices here are soft preferences.',
        )}
      </p>
      <div className="button-row">
        <button className="btn btn-primary" disabled={busy}>
          {t('Lưu sở thích', 'Save preferences')}
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy}
          onClick={() => onApply(preferenceDraft(draft))}
        >
          {t('Dùng cho chuyến mới', 'Use for a new trip')}
        </button>
      </div>
      {message && <p role="status">{message}</p>}
    </form>
  );
}

function SavedCard({
  item,
  hub,
  selected,
  onSelect,
  onRecheck,
  onDelete,
}: {
  item: HubItem<SavedTour>;
  hub: Hub;
  selected: boolean;
  onSelect: () => void;
  onRecheck: () => void;
  onDelete: () => void;
}) {
  const { t, locale } = usePreferences();
  const [note, setNote] = useState(item.value.note);
  const [collection, setCollection] = useState(item.value.collection);
  const [message, setMessage] = useState('');
  const v = item.value;
  return (
    <article className="hub-card">
      <label className="hub-check">
        <input type="checkbox" checked={selected} onChange={onSelect} />
        {t('Chọn để đối chiếu', 'Select for comparison')}
      </label>
      <h3>
        <a href={v.url} target="_blank" rel="noopener noreferrer">
          {v.title}
        </a>
      </h3>
      <p>{v.supplier ?? t('Nhà cung cấp chưa rõ', 'Supplier unknown')}</p>
      <dl className="hub-facts">
        <div>
          <dt>{t('Lịch lúc lưu', 'Saved departure')}</dt>
          <dd>{v.departure_date ?? t('Chưa chọn lịch', 'No offer selected')}</dd>
        </div>
        <div>
          <dt>{t('Giá lúc lưu', 'Saved price')}</dt>
          <dd>{v.price_label ?? t('Chưa có giá rõ ràng', 'Price unavailable')}</dd>
        </div>
      </dl>
      <p className="form-hint">
        {t(
          'Dữ liệu lịch sử; cần kiểm tra lại. Phụ thu/tổng thực trả chưa được xác nhận.',
          'Historical snapshot; recheck before use. Surcharges/final payable total are unconfirmed.',
        )}
      </p>
      <p className="form-hint">
        {t('Đối chiếu lúc', 'Evaluated at')}{' '}
        {new Date(v.evaluated_at).toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB')} ·{' '}
        {v.status_at_save === 'recommended'
          ? t('Từng được gợi ý trong lượt đó', 'Recommended in that search')
          : t('Cần xác nhận thêm', 'Needs verification')}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setMessage('');
          void hub
            .mutate(`saved-tours/${item.id}/edit`, {
              expected_version: item.version,
              note,
              collection,
            })
            .then(() => setMessage(t('Đã lưu ghi chú.', 'Notes saved.')))
            .catch(() => {});
        }}
      >
        <label className="field">
          {t('Bộ sưu tập', 'Collection')}
          <input
            maxLength={80}
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
          />
        </label>
        <label className="field">
          {t('Ghi chú của bạn', 'Your notes')}
          <textarea maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <div className="button-row">
          <button className="btn" disabled={hub.busy}>
            {t('Lưu ghi chú', 'Save notes')}
          </button>
          <button type="button" className="btn" disabled={hub.busy} onClick={onRecheck}>
            {t('Kiểm tra lại', 'Recheck')}
          </button>
          <button type="button" className="text-action" disabled={hub.busy} onClick={onDelete}>
            {t('Bỏ lưu', 'Remove')}
          </button>
        </div>
        {message && <p role="status">{message}</p>}
      </form>
    </article>
  );
}
function TemplateCard({
  item,
  hub,
  onUse,
  onDelete,
}: {
  item: HubItem<TravelTemplate>;
  hub: Hub;
  onUse: () => void;
  onDelete: () => void;
}) {
  const { t } = usePreferences();
  const [name, setName] = useState(item.value.name);
  return (
    <article className="hub-card">
      <h3>{item.value.name}</h3>
      <p>
        {item.value.values.adults ?? '—'} {t('người lớn', 'adults')} ·{' '}
        {item.value.values.child_count} {t('trẻ em', 'children')}
      </p>
      <p className="form-hint">
        {t(
          'Chọn lại lịch, ngân sách và tuổi trẻ em khi dùng.',
          'Choose new dates, budget and child ages when reusing.',
        )}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void hub
            .mutate('templates', {
              item_id: item.id,
              expected_version: item.version,
              template: { ...item.value, name: name.trim() },
            })
            .catch(() => {});
        }}
      >
        <label className="field">
          {t('Tên mẫu', 'Template name')}
          <input value={name} required maxLength={80} onChange={(e) => setName(e.target.value)} />
        </label>
        <div className="button-row">
          <button className="btn" disabled={hub.busy || !name.trim()}>
            {t('Đổi tên', 'Rename')}
          </button>
          <button type="button" className="btn btn-primary" disabled={hub.busy} onClick={onUse}>
            {t('Dùng mẫu', 'Use template')}
          </button>
          <button type="button" className="text-action" disabled={hub.busy} onClick={onDelete}>
            {t('Xóa mẫu', 'Delete template')}
          </button>
        </div>
      </form>
    </article>
  );
}

export type HubView = 'overview' | 'saved' | 'preferences' | 'templates' | 'data';
export function ProfileHub({
  view = 'overview',
  owner,
  hub,
  sessions,
  retention,
  historyBusy,
  onNew,
  onOpen,
  onPin,
  onArchive,
  onSignIn,
}: {
  view?: HubView;
  owner?: string;
  hub: Hub;
  sessions: LocalSession[];
  retention: number | null;
  historyBusy: boolean;
  onNew: (draft?: FormValues, title?: string) => void;
  onOpen: (id: string) => void;
  onPin: (s: LocalSession) => void;
  onArchive: (s: LocalSession) => void;
  onSignIn: () => void;
}) {
  const { t } = usePreferences();
  const [selected, setSelected] = useState<string[]>([]);
  const [collection, setCollection] = useState('');
  const [deletion, setDeletion] = useState<
    { kind: 'preferences' | 'template' | 'saved_tour'; id: string; version: number } | 'all' | null
  >(null);
  const [message, setMessage] = useState('');
  const data = hub.data;
  const chosen = data?.saved_tours.filter((item) => selected.includes(item.id)) ?? [];
  const sorted = [...sessions]
    .sort(
      (a, b) =>
        Number(b.pinned) - Number(a.pinned) || Date.parse(b.updatedAt) - Date.parse(a.updatedAt),
    )
    .slice(0, 6);
  const recheck = (urls: string[]) => {
    const d = preferenceDraft(defaultPreferences);
    d.mode = 'urls';
    d.referenceUrls = urls;
    onNew(d, t('Kiểm tra tour lưu', 'Recheck saved tours'));
  };
  const remove = async () => {
    if (!deletion || !data) return;
    const items =
      deletion === 'all'
        ? [
            ...(data.preferences ? [data.preferences] : []),
            ...data.templates,
            ...data.saved_tours,
          ].map((i) => ({ kind: i.kind, id: i.id, version: i.version }))
        : [deletion];
    try {
      for (const item of items) await hub.remove(item.kind, item.id, item.version);
      setDeletion(null);
      setSelected([]);
      setMessage(t('Đã xóa dữ liệu đã chọn.', 'Selected data deleted.'));
    } catch {
      /* Keep dialog open, reload before retry on conflict. */
    }
  };
  const exportData = () => {
    if (!data) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify({ exported_at: new Date().toISOString(), ...data }, null, 2)], {
        type: 'application/json',
      }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'di-cung-profile-hub.json';
    a.click();
    URL.revokeObjectURL(url);
  };
  const collections = [
    ...new Set(data?.saved_tours.map((x) => x.value.collection).filter(Boolean) ?? []),
  ];
  return (
    <div className="profile-hub">
      <section className="account-section hub-intro" hidden={view !== 'overview'}>
        <div>
          <span className="eyebrow">{t('CHUYẾN ĐI TIẾP THEO', 'YOUR NEXT JOURNEY')}</span>
          <h2>{t('Bạn muốn đi đâu tiếp?', 'Where will you go next?')}</h2>
          <p>
            {t(
              'Bắt đầu một kế hoạch mới, hoặc tiếp tục điều bạn đang cân nhắc.',
              'Start a new plan, or pick up where you left off.',
            )}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => onNew()}>
          {t('Tìm chuyến mới', 'Plan a new trip')}
        </button>
      </section>
      {owner && data && (
        <div className="hub-summary" hidden={view !== 'overview'}>
          {[
            [sessions.length, t('Phiên tìm tour', 'Searches'), 'history'],
            [data.saved_tours.length, t('Tour đã lưu', 'Saved tours'), 'pin'],
            [data.templates.length, t('Mẫu nhu cầu', 'Templates'), 'route'],
          ].map(([count, label, icon]) => (
            <div key={label}>
              <Icon name={String(icon)} />
              <strong>{count}</strong>
              <span>{label}</span>
            </div>
          ))}
        </div>
      )}
      <section className="account-section" id="hub-history" hidden={view !== 'overview'}>
        <h2>{t('Gần đây và đã ghim', 'Recent and pinned')}</h2>
        {retention !== null && (
          <p className="form-hint">
            {t(
              `Lịch sử được lưu ${retention} ngày. Tour lưu và mẫu nhu cầu có vòng đời riêng.`,
              `Search history lasts ${retention} days. Saved tours and templates are retained separately.`,
            )}
          </p>
        )}
        {sorted.length ? (
          <ul className="hub-sessions">
            {sorted.map((s) => (
              <li key={s.id}>
                <button className="text-action" onClick={() => onOpen(s.id)}>
                  {s.pinned ? '★ ' : ''}
                  {s.title || t('Chuyến đi mới', 'New trip')}
                </button>
                <div className="button-row">
                  <button className="text-action" disabled={historyBusy} onClick={() => onPin(s)}>
                    {s.pinned ? t('Bỏ ghim', 'Unpin') : t('Ghim', 'Pin')}
                  </button>
                  <button
                    className="text-action"
                    disabled={historyBusy}
                    onClick={() => onArchive(s)}
                  >
                    {t('Ẩn phiên', 'Archive')}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="hub-empty">
            <Icon name="route" size={28} />
            <h3>{t('Một hành trình mới đang chờ bạn', 'Your next journey is waiting')}</h3>
            <p>
              {t(
                'Những phiên tìm tour gần đây sẽ xuất hiện ở đây.',
                'Your recent tour searches will appear here.',
              )}
            </p>
          </div>
        )}
      </section>
      {!owner ? (
        <section className="account-section" hidden={view !== 'overview'}>
          <h2>{t('Mang kế hoạch theo bạn', 'Take your plans with you')}</h2>
          <p>
            {t(
              'Đăng nhập để lưu sở thích, tour và mẫu nhu cầu trên tài khoản.',
              'Sign in to save preferences, tours and templates to your account.',
            )}
          </p>
          <button className="btn" onClick={onSignIn}>
            {t('Đăng nhập', 'Sign in')}
          </button>
        </section>
      ) : (
        <>
          {hub.error && (
            <p className="notice notice-error" role="alert">
              {hub.error}
            </p>
          )}
          <div className="hub-sync" hidden={view !== 'data' && !hub.error}>
            <button className="text-action" disabled={hub.busy} onClick={() => void hub.reload()}>
              {hub.busy
                ? t('Đang đồng bộ…', 'Syncing…')
                : t('Tải lại dữ liệu cá nhân', 'Reload personal data')}
            </button>
            <span role="status">{message}</span>
          </div>
          {!data && !hub.error && view !== 'overview' && (
            <p role="status">{t('Đang tải không gian cá nhân…', 'Loading your workspace…')}</p>
          )}
          {data && (
            <>
              <section className="account-section" id="hub-saved" hidden={view !== 'saved'}>
                <div className="section-heading">
                  <h2>
                    {t('Tour đã lưu', 'Saved tours')}{' '}
                    <span className="count-badge">{data.saved_tours.length}</span>
                  </h2>
                </div>
                <p>
                  {t(
                    'Lưu tour trong kết quả tìm kiếm. Việc lưu không xác nhận giá hiện tại hay đặt chỗ.',
                    'Save tours from search results. Saving does not confirm current prices or make a booking.',
                  )}
                </p>
                <div className="button-row">
                  <label className="field">
                    {t('Lọc bộ sưu tập', 'Filter collection')}
                    <select value={collection} onChange={(e) => setCollection(e.target.value)}>
                      <option value="">{t('Tất cả', 'All')}</option>
                      {collections.map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="btn"
                    disabled={hub.busy || !chosen.length}
                    onClick={() => recheck(chosen.map((x) => x.value.url))}
                  >
                    {t(`Đối chiếu ${chosen.length}/5 tour`, `Compare ${chosen.length}/5 tours`)}
                  </button>
                </div>
                <div className="hub-grid">
                  {data.saved_tours
                    .filter((x) => !collection || x.value.collection === collection)
                    .map((item) => (
                      <SavedCard
                        key={`${item.id}:${item.version}`}
                        item={item}
                        hub={hub}
                        selected={selected.includes(item.id)}
                        onSelect={() => {
                          setMessage('');
                          setSelected(() => {
                            const ids = chosen.map((x) => x.id);
                            return ids.includes(item.id)
                              ? ids.filter((x) => x !== item.id)
                              : ids.length < 5
                                ? [...ids, item.id]
                                : ids;
                          });
                          if (!selected.includes(item.id) && chosen.length >= 5)
                            setMessage(t('Chọn tối đa 5 tour.', 'Select up to five tours.'));
                        }}
                        onRecheck={() => recheck([item.value.url])}
                        onDelete={() =>
                          setDeletion({ kind: 'saved_tour', id: item.id, version: item.version })
                        }
                      />
                    ))}
                </div>
                {!data.saved_tours.length && (
                  <div className="hub-empty">
                    <Icon name="pin" size={28} />
                    <h3>{t('Giữ lại những lựa chọn bạn thích', 'Keep the options you like')}</h3>
                    <p>
                      {t(
                        'Bấm “Lưu tour” trong kết quả tìm kiếm để xem lại tại đây.',
                        'Choose “Save tour” in search results to revisit it here.',
                      )}
                    </p>
                  </div>
                )}
                {data.saved_tours.length > 0 &&
                  !data.saved_tours.some(
                    (x) => !collection || x.value.collection === collection,
                  ) && (
                    <p>{t('Chưa có tour trong bộ sưu tập này.', 'No tours in this collection.')}</p>
                  )}
              </section>
              <section
                className="account-section"
                id="hub-preferences"
                hidden={view !== 'preferences'}
              >
                <h2>{t('Sở thích cho chuyến đi', 'Travel preferences')}</h2>
                <PreferenceEditor
                  key={`${owner}:${data.preferences_version}`}
                  value={data.preferences?.value ?? defaultPreferences}
                  busy={hub.busy}
                  onSave={(p) =>
                    hub.mutate('preferences', {
                      expected_version: data.preferences_version,
                      preferences: p,
                    })
                  }
                  onApply={(d) =>
                    onNew(d, t('Chuyến mới từ sở thích', 'New trip from preferences'))
                  }
                />
                {data.preferences && (
                  <button
                    className="text-action"
                    disabled={hub.busy}
                    onClick={() =>
                      setDeletion({
                        kind: 'preferences',
                        id: 'preferences',
                        version: data.preferences_version,
                      })
                    }
                  >
                    {t('Xóa sở thích đã lưu', 'Delete saved preferences')}
                  </button>
                )}
              </section>
              <section className="account-section" id="hub-templates" hidden={view !== 'templates'}>
                <h2>
                  {t('Mẫu nhu cầu', 'Templates')}{' '}
                  <span className="count-badge">{data.templates.length}</span>
                </h2>
                <p>
                  {t(
                    'Trong nhu cầu đã xác nhận, chọn “Lưu mẫu nhu cầu”. Mẫu giữ nơi đi/đến, số người và ưu tiên; mỗi chuyến vẫn cần lịch và ngân sách mới.',
                    'Choose “Save requirement template” in a confirmed search. Templates keep places, party counts and preferences; each trip needs new dates and budget.',
                  )}
                </p>
                <div className="hub-grid">
                  {data.templates.map((item) => (
                    <TemplateCard
                      key={`${item.id}:${item.version}`}
                      item={item}
                      hub={hub}
                      onUse={() => onNew(templateDraft(item.value), item.value.name)}
                      onDelete={() =>
                        setDeletion({ kind: 'template', id: item.id, version: item.version })
                      }
                    />
                  ))}
                </div>
                {!data.templates.length && (
                  <div className="hub-empty">
                    <Icon name="route" size={28} />
                    <h3>{t('Lên kế hoạch nhanh hơn cho lần sau', 'Plan faster next time')}</h3>
                    <p>
                      {t(
                        'Lưu một mẫu từ nhu cầu đã xác nhận để dùng lại nơi đi, nơi đến và số người.',
                        'Save a template from confirmed requirements to reuse places and party counts.',
                      )}
                    </p>
                  </div>
                )}
              </section>
              <section className="account-section" hidden={view !== 'data'}>
                <h2>{t('Dữ liệu kế hoạch đã lưu', 'Saved planning data')}</h2>
                <p>
                  {t(
                    'Sở thích, tour lưu và mẫu nhu cầu. Bạn có thể tải bản sao hoặc xóa riêng phần này.',
                    'Preferences, saved tours and templates. Download a copy or delete this planning data.',
                  )}
                </p>
                <div className="button-row">
                  <button className="btn" onClick={exportData} disabled={hub.busy}>
                    {t('Xuất kế hoạch đã lưu', 'Export saved plans')}
                  </button>
                  <button
                    className="btn"
                    onClick={() => setDeletion('all')}
                    disabled={
                      hub.busy ||
                      (!data.preferences && !data.templates.length && !data.saved_tours.length)
                    }
                  >
                    {t('Xóa kế hoạch đã lưu', 'Delete saved plans')}
                  </button>
                </div>
              </section>
            </>
          )}
        </>
      )}
      <Dialog
        open={deletion !== null}
        onClose={() => {
          if (!hub.busy) setDeletion(null);
        }}
        title={t('Xóa dữ liệu đã chọn?', 'Delete selected data?')}
      >
        <p>
          {t(
            'Nội dung đã chọn sẽ bị xóa khỏi tài khoản. Lịch sử tìm tour và tài khoản đăng nhập vẫn được giữ.',
            'Selected content will be removed from your account. Search history and your sign-in account are retained.',
          )}
        </p>
        {hub.error && (
          <>
            <p className="notice notice-error" role="alert">
              {hub.error}
            </p>
            <button
              className="btn"
              disabled={hub.busy}
              onClick={() => {
                setDeletion(null);
                void hub.reload();
              }}
            >
              {t('Tải lại trước khi chọn xóa', 'Reload before choosing what to delete')}
            </button>
          </>
        )}
        <div className="button-row">
          <button className="btn" disabled={hub.busy} onClick={() => setDeletion(null)}>
            {t('Giữ lại', 'Keep')}
          </button>
          <button className="btn btn-danger" disabled={hub.busy} onClick={() => void remove()}>
            {t('Xóa', 'Delete')}
          </button>
        </div>
      </Dialog>
    </div>
  );
}
