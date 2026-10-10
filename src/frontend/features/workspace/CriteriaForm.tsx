import { useId, type FormEvent } from 'react';
import type { Catalog } from '../../api/types';
import type { FormValues } from '../../api/form';
import { usePreferences } from '../../app/preferences';
import { Icon } from '../../components/Icon';
import { MonthPicker } from '../../components/MonthPicker';
import { BudgetRange } from '../../components/BudgetRange';

interface Props {
  values: FormValues;
  catalog: Catalog;
  onChange: (v: FormValues) => void;
  onSubmit: () => void;
  busy: boolean;
  editing?: boolean;
  budgetLocked?: string | null;
  monthsLocked?: string | null;
}
export function CriteriaForm({
  values: v,
  catalog,
  onChange,
  onSubmit,
  busy,
  editing = false,
  budgetLocked = null,
  monthsLocked = null,
}: Props) {
  const { t } = usePreferences();
  const prefix = useId();
  const update = <K extends keyof FormValues>(key: K, value: FormValues[K]) =>
    onChange({ ...v, [key]: value });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };
  const label = (vi: string, en: string) => t(vi, en);
  const strength = (field: string) => (
    <select
      aria-label={`${t('Loại điều kiện', 'Condition type')}: ${field}`}
      value={v.strengths[field] || (field === 'transport' ? 'hard' : 'soft')}
      onChange={(e) =>
        update('strengths', { ...v.strengths, [field]: e.target.value as 'hard' | 'soft' })
      }
    >
      <option value="hard">{t('Bắt buộc', 'Required')}</option>
      <option value="soft">{t('Ưu tiên', 'Preferred')}</option>
    </select>
  );
  return (
    <form className="criteria-form" onSubmit={submit}>
      <fieldset className="form-controls" disabled={busy}>
        {!editing && (
          <div className="input-modes" aria-label={t('Cách nhập nhu cầu', 'Input method')}>
            {(['structured', 'text', 'urls'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={v.mode === mode}
                onClick={() => update('mode', mode)}
              >
                {mode === 'structured'
                  ? t('Điền nhu cầu', 'Travel preferences')
                  : mode === 'text'
                    ? t('Nhắn nhu cầu', 'Describe your trip')
                    : t('So sánh URL', 'Compare URLs')}
              </button>
            ))}
          </div>
        )}
        {v.mode === 'text' && !editing && (
          <label className="field" htmlFor={`${prefix}-text`}>
            {t('Bạn đang cân nhắc chuyến đi nào?', 'What trip are you considering?')}
            <textarea
              id={`${prefix}-text`}
              rows={5}
              required
              maxLength={catalog.limits.text_characters}
              value={v.text}
              onChange={(e) => update('text', e.target.value)}
              placeholder={t(
                'Nơi muốn đến, khoảng thời gian, số người, ngân sách và những điều bạn ưu tiên…',
                'Destination, dates, party size, budget and what matters to you…',
              )}
            />
            <small>
              {t(
                'Bạn sẽ kiểm tra và xác nhận nhu cầu trước khi tìm tour.',
                'Review and confirm the interpreted requirements before searching.',
              )}
            </small>
          </label>
        )}
        {(v.mode === 'structured' || editing) && (
          <>
            <h3 className="form-section-title">{t('Thông tin chuyến đi', 'Your trip')}</h3>
            <div className="form-grid">
              <label className="field" htmlFor={`${prefix}-destination`}>
                {label('Điểm đến', 'Destination')}
                <select
                  id={`${prefix}-destination`}
                  required={!editing}
                  value={v.destinations[0] || ''}
                  onChange={(e) => update('destinations', e.target.value ? [e.target.value] : [])}
                >
                  <option value="">{t('Chọn điểm đến', 'Choose a destination')}</option>
                  {catalog.destinations.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field" htmlFor={`${prefix}-origin`}>
                {label('Khởi hành từ', 'Departure from')}
                <select
                  id={`${prefix}-origin`}
                  required={!editing}
                  value={v.departureOrigin}
                  onChange={(e) => update('departureOrigin', e.target.value)}
                >
                  <option value="">{t('Chọn nơi khởi hành', 'Choose an origin')}</option>
                  {catalog.origins.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.label}
                    </option>
                  ))}
                </select>
              </label>
              <MonthPicker
                value={v.departureMonths}
                disabled={!!monthsLocked}
                onChange={(departureMonths) =>
                  onChange({ ...v, departureMonths, departureDate: '' })
                }
              />
              {(monthsLocked || v.departureDate) && (
                <p className="form-hint field-wide">
                  {monthsLocked ||
                    `${t('Đang giữ lịch', 'Keeping the existing date')}: ${v.departureDate}. ${t('Chọn tháng để đổi lịch này.', 'Choose months to change this date.')}`}
                </p>
              )}
              <label className="field" htmlFor={`${prefix}-adults`}>
                {label('Người lớn', 'Adults')}
                <input
                  id={`${prefix}-adults`}
                  type="number"
                  min={1}
                  max={100}
                  required={!editing}
                  value={v.adults || ''}
                  onChange={(e) => update('adults', Number(e.target.value))}
                />
              </label>
              <label className="field" htmlFor={`${prefix}-children`}>
                {label('Trẻ em', 'Children')}
                <input
                  id={`${prefix}-children`}
                  type="number"
                  min={0}
                  max={20}
                  value={v.childAges.length}
                  onChange={(e) => {
                    const count = Math.min(20, Math.max(0, Number(e.target.value)));
                    update(
                      'childAges',
                      Array.from({ length: count }, (_, i) => v.childAges[i] ?? null),
                    );
                  }}
                />
              </label>
              {v.childAges.map((age, index) => (
                <label className="field" key={index} htmlFor={`${prefix}-child-${index}`}>
                  {t('Tuổi trẻ', 'Child age')} {index + 1}
                  <input
                    id={`${prefix}-child-${index}`}
                    type="number"
                    min={0}
                    max={17}
                    required
                    value={age ?? ''}
                    onChange={(e) =>
                      update(
                        'childAges',
                        v.childAges.map((old, i) =>
                          i === index
                            ? e.target.value === ''
                              ? null
                              : Number(e.target.value)
                            : old,
                        ),
                      )
                    }
                  />
                </label>
              ))}
              <BudgetRange
                minimum={v.budgetMin}
                maximum={v.budget}
                disabled={busy || !!budgetLocked}
                required={!editing}
                onChange={(budgetMin, budget) => onChange({ ...v, budgetMin, budget })}
              />
              {budgetLocked && <p className="form-hint field-wide">{budgetLocked}</p>}
            </div>
            <details className="optional-fields" open={editing}>
              <summary>
                {t('Điều kiện và ưu tiên thêm', 'Additional conditions and preferences')}
              </summary>
              <div className="form-grid">
                <div className="field">
                  <label htmlFor={`${prefix}-duration`}>
                    {v.strengths.duration_days === 'hard'
                      ? label('Thời lượng (ngày)', 'Duration (days)')
                      : label('Thời lượng khoảng (ngày)', 'Approximate duration (days)')}
                  </label>
                  <input
                    id={`${prefix}-duration`}
                    type="number"
                    min={1}
                    max={365}
                    value={v.durationDays}
                    onChange={(e) => update('durationDays', e.target.value)}
                  />
                  {strength('duration_days')}
                </div>
                <label className="field" htmlFor={`${prefix}-hotel`}>
                  {label('Khách sạn tối thiểu', 'Minimum hotel rating')}
                  <select
                    id={`${prefix}-hotel`}
                    value={v.hotelStars}
                    onChange={(e) => update('hotelStars', e.target.value)}
                  >
                    <option value="">{t('Không giới hạn', 'No preference')}</option>
                    {[3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n} {t('sao', 'stars')}
                      </option>
                    ))}
                  </select>
                  {strength('hotel_stars_min')}
                </label>
                <label className="field" htmlFor={`${prefix}-transport`}>
                  {label('Phương tiện', 'Transport')}
                  <select
                    id={`${prefix}-transport`}
                    value={v.transport[0] || ''}
                    onChange={(e) => update('transport', e.target.value ? [e.target.value] : [])}
                  >
                    <option value="">{t('Không giới hạn', 'No preference')}</option>
                    {catalog.transports.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.label}
                      </option>
                    ))}
                  </select>
                  {strength('transport')}
                </label>
                <label className="field" htmlFor={`${prefix}-shopping`}>
                  {label('Điểm mua sắm', 'Shopping stops')}
                  <select
                    id={`${prefix}-shopping`}
                    value={v.shopping}
                    onChange={(e) => update('shopping', e.target.value as FormValues['shopping'])}
                  >
                    <option value="any">{t('Không giới hạn', 'No preference')}</option>
                    <option value="few">{t('Ưu tiên ít điểm', 'Prefer fewer stops')}</option>
                    <option value="none">{t('Bắt buộc không có', 'No stops required')}</option>
                  </select>
                </label>
              </div>
            </details>
            <PreferenceSliders values={v} catalog={catalog} onChange={onChange} disabled={busy} />
          </>
        )}
        <label className="field" htmlFor={`${prefix}-urls`}>
          {v.mode === 'urls'
            ? t('URL tour cần đối chiếu', 'Tour URLs to compare')
            : t('URL tour tham chiếu (tùy chọn)', 'Reference tour URLs (optional)')}
          <textarea
            id={`${prefix}-urls`}
            rows={2}
            required={v.mode === 'urls'}
            value={v.referenceUrls.join('\n')}
            onChange={(e) => update('referenceUrls', e.target.value.split('\n'))}
            placeholder="https://…"
          />
          <small>
            {t('Mỗi dòng một URL. Tối đa', 'One URL per line. Maximum')}{' '}
            {catalog.limits.reference_urls}.
          </small>
        </label>
        <label className="field" htmlFor={`${prefix}-notes`}>
          {t('Ghi chú', 'Notes')}
          <textarea
            id={`${prefix}-notes`}
            rows={3}
            maxLength={8000}
            value={v.notes}
            onChange={(e) => update('notes', e.target.value)}
            placeholder={t('Những điều cần lưu ý cho chuyến đi…', 'Anything else to keep in mind…')}
          />
        </label>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy
            ? t('Đang xử lý…', 'Processing…')
            : editing
              ? t('Xem thay đổi', 'Review changes')
              : t('Xem lại nhu cầu', 'Review requirements')}
          <Icon name="arrow" />
        </button>
      </fieldset>
    </form>
  );
}

export function PreferenceSliders({
  values: v,
  catalog,
  onChange,
  disabled = false,
}: {
  values: FormValues;
  catalog: Catalog;
  onChange: (v: FormValues) => void;
  disabled?: boolean;
}) {
  const { t } = usePreferences();
  const prefix = useId();
  return (
    <fieldset className="preference-sliders" disabled={disabled}>
      <legend>{t('Điều bạn ưu tiên', 'What matters to you')}</legend>
      {catalog.preference_dimensions.map((d) => (
        <label key={d.id} className="slider-field" htmlFor={`${prefix}-${d.id}`}>
          <span>
            {
              {
                cost: t('Tiết kiệm chi phí', 'Save on cost'),
                comfort: t('Khách sạn tiện nghi', 'Hotel comfort'),
                pace: t('Nhịp đi thư thả', 'Relaxed pace'),
                culture: t('Trải nghiệm văn hóa', 'Cultural experiences'),
              }[d.id]
            }{' '}
            <strong>
              {v.preferenceLevels[d.id]}/{d.max}
            </strong>
          </span>
          <input
            id={`${prefix}-${d.id}`}
            type="range"
            min={d.min}
            max={d.max}
            value={v.preferenceLevels[d.id]}
            onChange={(e) =>
              onChange({
                ...v,
                preferenceLevels: { ...v.preferenceLevels, [d.id]: Number(e.target.value) },
                preferenceOrigins: { ...v.preferenceOrigins, [d.id]: 'user' },
              })
            }
          />
          <small>
            {v.preferenceOrigins?.[d.id] !== 'user' && v.preferenceLevels[d.id] === d.default.level
              ? `${t('Mặc định', 'Default')} · `
              : ''}
            {!d.supported
              ? t('Chưa được tính trong xếp hạng', 'Not yet included in ranking')
              : t('Mức quan trọng của ưu tiên', 'Importance of this preference')}
          </small>
        </label>
      ))}
    </fieldset>
  );
}
