import { useRef } from 'react';
import type { CurrentCondition, CurrentRequirement } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import { display, fieldLabel } from '../lib/format';
import type { ChatMsg } from '../model/types';
import styles from './chat.module.css';

export function DecisionBrief({
  message,
  busy,
  onChange,
  onRun,
}: {
  message: Extract<ChatMsg, { kind: 'decision_draft' }>;
  busy: boolean;
  onChange: (requirement: CurrentRequirement) => void;
  onRun: (requirement: CurrentRequirement) => void;
}) {
  const { t } = usePreferences();
  const editStartValues = useRef<Record<string, string>>({});
  const requirement = message.requirement;
  const soft = requirement.conditions.filter((condition) => condition.strength === 'soft');
  const hard = requirement.conditions.filter((condition) => condition.strength === 'hard');
  const total = soft.reduce((sum, condition) => sum + (condition.weight_percent ?? 0), 0);
  const weightsValid = soft.length === 0 || (
    soft.every((condition) => Number.isInteger(condition.weight_percent)
      && (condition.weight_percent ?? -1) >= 0
      && (condition.weight_percent ?? 101) <= 100)
    && total === 100
  );
  const valuesValid = requirement.conditions.every((condition) => {
    if (!condition.quote.trim() || !requirement.raw_text.includes(condition.quote)) return false;
    if (condition.field === 'destination' && condition.operator === 'any')
      return Array.isArray(condition.value) && condition.value.length > 1
        && condition.value.every((value) => typeof value === 'string' && value.trim());
    if (typeof condition.value === 'string') return Boolean(condition.value.trim());
    if (typeof condition.value === 'number') return Number.isFinite(condition.value) && condition.value > 0;
    return Array.isArray(condition.value) && condition.value.length > 0;
  }) && requirement.raw_text.length <= 8000;
  const canRun = weightsValid && valuesValid && !busy && message.status !== 'running';

  function patchCondition(id: string, changes: Partial<CurrentCondition>) {
    onChange({
      ...requirement,
      conditions: requirement.conditions.map((condition) =>
        condition.id === id ? { ...condition, ...changes } : condition,
      ),
    });
  }

  function removeCondition(id: string) {
    onChange({
      ...requirement,
      conditions: requirement.conditions.filter((condition) => condition.id !== id),
    });
  }

  function divideEvenly() {
    const base = Math.floor(100 / soft.length);
    const remainder = 100 % soft.length;
    const weights = new Map(soft.map((condition, index) => [
      condition.id,
      base + Number(index < remainder),
    ]));
    onChange({
      ...requirement,
      conditions: requirement.conditions.map((condition) => condition.strength === 'soft'
        ? { ...condition, weight_percent: weights.get(condition.id) ?? base }
        : condition),
    });
  }

  function changeValue(condition: CurrentCondition, value: string) {
    let next: unknown = value;
    if (typeof condition.value === 'number') next = value === '' ? 0 : Number(value);
    else if (Array.isArray(condition.value))
      next = value.split(',').map((item) => item.trim()).filter(Boolean);
    patchCondition(condition.id, { value: next });
  }

  function commitReviewedValue(condition: CurrentCondition, inputValue: string, initialValue: string) {
    const quote = inputValue.trim();
    if (!quote || inputValue === initialValue) return;
    let value: unknown = inputValue;
    if (typeof condition.value === 'number') value = Number(inputValue);
    else if (Array.isArray(condition.value))
      value = inputValue.split(',').map((item) => item.trim()).filter(Boolean);

    const otherQuotes = requirement.conditions
      .filter((item) => item.id !== condition.id)
      .map((item) => item.quote)
      .filter(Boolean);
    const overlapsAnotherQuote = otherQuotes.some((other) =>
      other.includes(condition.quote) || condition.quote.includes(other),
    );
    const canReplaceSourceQuote = condition.quote
      && requirement.raw_text.includes(condition.quote)
      && !overlapsAnotherQuote;
    const rawText = canReplaceSourceQuote
      ? requirement.raw_text.replace(condition.quote, quote)
      : `${requirement.raw_text}\n${quote}`;

    onChange({
      ...requirement,
      raw_text: rawText,
      conditions: requirement.conditions.map((item) => item.id === condition.id
        ? { ...item, value, quote }
        : item),
    });
  }

  function conditionEditor(condition: CurrentCondition) {
    const text = Array.isArray(condition.value)
      ? condition.value.map((value) => display(value)).join(', ')
      : typeof condition.value === 'number'
        ? String(condition.value)
        : display(condition.value);
    const label = `${fieldLabel(condition.field, t)} — ${condition.strength === 'hard'
      ? t('Bắt buộc', 'Required')
      : t('Ưu tiên', 'Preference')}`;
    return (
      <div className={styles['brief-condition']} key={condition.id}>
        <label className={styles['brief-condition-field']}>
          <span>{label}</span>
          {condition.field === 'transport' ? (
            <select
              value={String(condition.value)}
              disabled={busy || message.status === 'running'}
              aria-label={label}
              onFocus={() => { editStartValues.current[condition.id] = text; }}
              onChange={(event) => patchCondition(condition.id, { value: event.target.value })}
              onBlur={(event) => {
                commitReviewedValue(
                  condition,
                  event.currentTarget.value,
                  editStartValues.current[condition.id] ?? text,
                );
                delete editStartValues.current[condition.id];
              }}
            >
              {[
                ['flight', t('Máy bay', 'Flight')],
                ['bus', t('Xe khách', 'Bus')],
                ['train', t('Tàu hỏa', 'Train')],
                ['cruise', t('Du thuyền', 'Cruise')],
                ['mixed', t('Kết hợp', 'Mixed')],
              ].map(([value, optionLabel]) => (
                <option value={value} key={value}>{optionLabel}</option>
              ))}
            </select>
          ) : (
            <input
              type={condition.field === 'date_from' || condition.field === 'date_to'
                ? 'date'
                : typeof condition.value === 'number' ? 'number' : 'text'}
              min={typeof condition.value === 'number' ? 1 : undefined}
              value={text}
              disabled={busy || message.status === 'running'}
              aria-label={label}
              onFocus={() => { editStartValues.current[condition.id] = text; }}
              onChange={(event) => changeValue(condition, event.target.value)}
              onBlur={(event) => {
                commitReviewedValue(
                  condition,
                  event.currentTarget.value,
                  editStartValues.current[condition.id] ?? text,
                );
                delete editStartValues.current[condition.id];
              }}
            />
          )}
        </label>
        {condition.strength === 'soft' && (
          <label className={styles['brief-weight']}>
            <span>{t('Trọng số', 'Weight')}</span>
            <span className={styles['brief-weight-input']}>
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                value={condition.weight_percent ?? ''}
                disabled={busy || message.status === 'running'}
                aria-label={t(`Trọng số ${String(condition.value)}`, `Weight for ${String(condition.value)}`)}
                onChange={(event) => patchCondition(condition.id, {
                  weight_percent: event.target.value === '' ? null : Number(event.target.value),
                })}
              />
              <span>%</span>
            </span>
          </label>
        )}
        <button
          type="button"
          className={styles['brief-remove']}
          disabled={busy || message.status === 'running'}
          aria-label={t(`Xóa ${label}`, `Remove ${label}`)}
          onClick={() => removeCondition(condition.id)}
        >
          ×
        </button>
      </div>
    );
  }

  return (
    <section className={styles['decision-brief']} aria-label={t('Bản tóm tắt quyết định', 'Decision brief')}>
      <header className={styles['brief-header']}>
        <div>
          <span className={styles['brief-eyebrow']}>{t('BƯỚC 1 · REVIEW', 'STEP 1 · REVIEW')}</span>
          <h2>{t('Kiểm tra tiêu chí chuyến đi', 'Review your trip criteria')}</h2>
        </div>
        <span className={styles['brief-state']} data-status={message.status}>
          {message.status === 'running'
            ? t('Đang so sánh', 'Comparing')
            : message.status === 'complete'
              ? t('Đã so sánh', 'Compared')
              : t('Bản nháp', 'Draft')}
        </span>
      </header>

      {hard.length > 0 && (
        <fieldset className={styles['brief-section']} disabled={busy || message.status === 'running'}>
          <legend>{t('Điều kiện bắt buộc', 'Must-haves')}</legend>
          {hard.map(conditionEditor)}
        </fieldset>
      )}

      <fieldset className={styles['brief-section']} disabled={busy || message.status === 'running'}>
        <legend>{t('Ưu tiên mềm', 'Preferences')}</legend>
        {soft.length > 0 ? soft.map(conditionEditor) : (
          <p className={styles['brief-empty']}>
            {t('Chưa có sở thích mềm. Bạn vẫn có thể so giá và xem các phương án cân bằng.',
              'No soft preferences yet. You can still compare prices and balanced options.')}
          </p>
        )}
      </fieldset>

      {soft.length > 0 && (
        <div className={styles['brief-weight-summary']}>
          <span aria-live="polite">
            {t(`Đã phân bổ ${total} / 100 điểm`, `${total} / 100 points assigned`)}
          </span>
          <button type="button" disabled={busy || message.status === 'running'} onClick={divideEvenly}>
            {t('Chia đều', 'Divide evenly')}
          </button>
        </div>
      )}

      {requirement.missing.length > 0 && (
        <p className={styles['brief-empty']}>
          {t(`Còn thiếu: ${requirement.missing.join(', ')}`, `Still missing: ${requirement.missing.join(', ')}`)}
        </p>
      )}

      <footer className={styles['brief-footer']}>
        <span>{t('Điều kiện bắt buộc quyết định tour có đạt hay không.',
          'Must-haves determine eligibility.')}</span>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!canRun}
          onClick={() => onRun(requirement)}
        >
          {message.status === 'complete'
            ? t('Chạy lại so sánh', 'Run comparison again')
            : t('So sánh tour', 'Compare tours')}
        </button>
      </footer>
      {!weightsValid && (
        <p className={styles['brief-validation']} role="status">
          {t('Phân bổ đủ đúng 100 điểm để tiếp tục.', 'Allocate exactly 100 points to continue.')}
        </p>
      )}
      {!valuesValid && (
        <p className={styles['brief-validation']} role="status">
          {t('Kiểm tra lại giá trị tiêu chí hoặc xóa điều kiện không dùng.',
            'Review criterion values or remove unused conditions.')}
        </p>
      )}
    </section>
  );
}
