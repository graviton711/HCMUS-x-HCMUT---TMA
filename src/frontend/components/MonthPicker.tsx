import { useState } from 'react';
import { usePreferences } from '../app/preferences';
import { Icon } from './Icon';

export function MonthPicker({
  value,
  onChange,
  disabled = false,
}: {
  value: string[];
  onChange: (months: string[]) => void;
  disabled?: boolean;
}) {
  const { t, locale } = usePreferences();
  const [year, setYear] = useState(
    () =>
      Number(value[0]?.slice(0, 4)) ||
      Number(
        new Intl.DateTimeFormat('en', { year: 'numeric', timeZone: 'Asia/Ho_Chi_Minh' }).format(
          new Date(),
        ),
      ),
  );
  const name = (month: string) =>
    new Date(`${month}-01T12:00:00Z`).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-GB', {
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC',
    });
  return (
    <fieldset className="month-picker field field-wide" disabled={disabled}>
      <legend>{t('Tháng khởi hành', 'Departure months')}</legend>
      <div className="month-year">
        <button
          type="button"
          className="icon-button"
          aria-label={t('Năm trước', 'Previous year')}
          disabled={year <= 1000}
          onClick={() => setYear(year - 1)}
        >
          <Icon name="left" />
        </button>
        <output aria-live="polite">{year}</output>
        <button
          type="button"
          className="icon-button"
          aria-label={t('Năm tiếp theo', 'Next year')}
          disabled={year >= 9999}
          onClick={() => setYear(year + 1)}
        >
          <Icon name="arrow" />
        </button>
      </div>
      <div className="month-grid">
        {Array.from({ length: 12 }, (_, index) => {
          const month = `${year}-${String(index + 1).padStart(2, '0')}`;
          const selected = value.includes(month);
          return (
            <button
              type="button"
              key={month}
              aria-label={name(month)}
              aria-pressed={selected}
              disabled={!selected && value.length >= 12}
              onClick={() =>
                onChange(
                  selected ? value.filter((item) => item !== month) : [...value, month].sort(),
                )
              }
            >
              {locale === 'vi'
                ? `Tháng ${index + 1}`
                : new Date(`${month}-01T12:00:00Z`).toLocaleDateString('en-GB', {
                    month: 'short',
                    timeZone: 'UTC',
                  })}
            </button>
          );
        })}
      </div>
      {!!value.length && (
        <div className="selected-months" aria-label={t('Các tháng đã chọn', 'Selected months')}>
          {value.map((month) => (
            <button
              type="button"
              key={month}
              aria-label={`${t('Bỏ', 'Remove')} ${name(month)}`}
              onClick={() => onChange(value.filter((item) => item !== month))}
            >
              {name(month)}
              <Icon name="close" size={14} />
            </button>
          ))}
        </div>
      )}
      <small>
        {t('Chọn một hoặc nhiều tháng, tối đa 12 tháng.', 'Choose one or more months, up to 12.')}
      </small>
    </fieldset>
  );
}
