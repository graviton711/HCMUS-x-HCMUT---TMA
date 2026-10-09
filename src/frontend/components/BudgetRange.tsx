import { useId, type CSSProperties, type KeyboardEvent } from 'react';
import { usePreferences } from '../app/preferences';

export function BudgetRange({
  minimum,
  maximum,
  onChange,
  disabled = false,
  required = false,
}: {
  minimum: string;
  maximum: string;
  onChange: (minimum: string, maximum: string) => void;
  disabled?: boolean;
  required?: boolean;
}) {
  const { t, locale } = usePreferences();
  const id = useId();
  const lower = Number(minimum) || 0;
  const upper = maximum === '' ? 50_000_000 : Number(maximum);
  const ceiling = Math.max(100_000_000, Math.ceil(Math.max(lower, upper) / 500_000) * 500_000);
  const money = (amount: number) => amount.toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB');
  const lowerLabel = t('Giá tối thiểu (VND/người lớn)', 'Minimum price (VND/adult)');
  const upperLabel = t('Giá tối đa (VND/người lớn)', 'Maximum price (VND/adult)');
  const changeLower = (value: number) => onChange(String(Math.min(value, upper)), String(upper));
  const changeUpper = (value: number) => onChange(String(lower), String(Math.max(value, lower)));
  const sliderKeys = (
    event: KeyboardEvent<HTMLInputElement>,
    value: number,
    change: (value: number) => void,
  ) => {
    const next: Record<string, number> = {
      ArrowLeft: value - 500_000,
      ArrowDown: value - 500_000,
      ArrowRight: value + 500_000,
      ArrowUp: value + 500_000,
      PageDown: value - 5_000_000,
      PageUp: value + 5_000_000,
      Home: 0,
      End: ceiling,
    };
    if (!(event.key in next)) return;
    event.preventDefault();
    change(Math.max(0, Math.min(ceiling, next[event.key])));
  };
  const snap = (value: number) => Math.round(value / 500_000) * 500_000;
  return (
    <fieldset className="budget-range field field-wide" disabled={disabled}>
      <legend>{t('Khoảng ngân sách / người lớn', 'Budget range / adult')}</legend>
      <output className="budget-output" htmlFor={`${id}-minimum ${id}-maximum`}>
        {maximum === ''
          ? t('Chưa chọn ngân sách', 'Choose your budget')
          : `${money(lower)} – ${money(upper)} VND`}
      </output>
      <div
        className="budget-track"
        style={
          {
            '--range-start': `${(lower / ceiling) * 100}%`,
            '--range-end': `${(upper / ceiling) * 100}%`,
          } as CSSProperties
        }
        onPointerDown={(event) => {
          if (disabled || event.target !== event.currentTarget) return;
          const box = event.currentTarget.getBoundingClientRect();
          const value =
            Math.round(
              (Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)) * ceiling) /
                500_000,
            ) * 500_000;
          if (Math.abs(value - lower) < Math.abs(value - upper)) changeLower(value);
          else changeUpper(value);
        }}
      >
        <div className="budget-track-line">
          <span />
        </div>
        <input
          type="range"
          min={0}
          max={ceiling}
          step={lower % 500_000 === 0 ? 500_000 : 1}
          value={lower}
          aria-label={t('Kéo giá tối thiểu', 'Minimum price slider')}
          aria-valuetext={`${money(lower)} VND`}
          onKeyDown={(event) => sliderKeys(event, lower, changeLower)}
          onChange={(event) => changeLower(snap(Number(event.target.value)))}
        />
        <input
          type="range"
          min={0}
          max={ceiling}
          step={upper % 500_000 === 0 ? 500_000 : 1}
          value={upper}
          aria-label={t('Kéo giá tối đa', 'Maximum price slider')}
          aria-valuetext={`${money(upper)} VND`}
          onKeyDown={(event) => sliderKeys(event, upper, changeUpper)}
          onChange={(event) => changeUpper(snap(Number(event.target.value)))}
        />
      </div>
      <div className="budget-inputs">
        <label htmlFor={`${id}-minimum`}>
          {t('Từ', 'From')}
          <input
            id={`${id}-minimum`}
            aria-label={lowerLabel}
            type="number"
            min={0}
            max={10 ** 15}
            step={1}
            value={minimum}
            placeholder="0"
            onChange={(event) => onChange(event.target.value, maximum)}
          />
        </label>
        <label htmlFor={`${id}-maximum`}>
          {t('Đến', 'To')}
          <input
            id={`${id}-maximum`}
            aria-label={upperLabel}
            type="number"
            min={0}
            max={10 ** 15}
            step={1}
            required={required}
            value={maximum}
            placeholder="50000000"
            onChange={(event) => onChange(minimum || '0', event.target.value)}
          />
        </label>
      </div>
      <small>
        {t(
          'Kéo hai đầu hoặc nhập khoảng giá chính xác. Chỉ tính giá tour.',
          'Drag either end or enter exact amounts. Tour price only.',
        )}
      </small>
    </fieldset>
  );
}
