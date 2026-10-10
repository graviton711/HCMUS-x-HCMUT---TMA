import type { SearchDraft } from '../../../entities/search-draft';
import type { LocalSession } from '../../../features/session-history';
import type { CurrentCatalog, CurrentRequirement } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';

export function RequirementForm({
  session,
  destinations,
  catalog,
  requirement,
  busy,
  writeDraft,
  interpret,
  search,
}: {
  session: LocalSession;
  destinations: string[];
  catalog: CurrentCatalog | null;
  requirement: CurrentRequirement | null;
  busy: boolean;
  writeDraft: (changes: Partial<SearchDraft>) => void;
  interpret: () => void;
  search: () => void;
}) {
  const { t } = usePreferences();
  return (
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
        {busy && <span role="status">{t('Đang kết nối backend…', 'Connecting to backend…')}</span>}
      </div>
    </div>
  );
}
