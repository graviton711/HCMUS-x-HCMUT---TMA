import { useId, useRef, useState } from 'react';
import type { CurrentCondition, CurrentRequirement } from '../../../shared/api';
import { usePreferences } from '../../../shared/preferences';
import { display, fieldLabel } from '../lib/format';
import type { ChatMsg } from '../model/types';
import { normalizeWeights, reallocateWeight } from '../lib/weightAllocation';
import styles from './chat.module.css';

const validWeightInput = (raw: string) => /^\d+$/u.test(raw) && Number(raw) <= 100;

export function DecisionBrief({
  message,
  busy,
  onChange,
  onRun,
}: {
  message: Extract<ChatMsg, { kind: 'decision_draft' }>;
  busy: boolean;
  onChange: (requirement: CurrentRequirement, confirmedWeightIds?: string[]) => void;
  onRun: (requirement: CurrentRequirement) => void;
}) {
  const { t } = usePreferences();
  const weightHelpId = useId();
  const editStartValues = useRef<Record<string, string>>({});
  const [weightDrafts, setWeightDrafts] = useState<Record<string, string>>({});
  const requirement = message.requirement;
  const alternatives = requirement.alternatives ?? [];
  const allConditions = [
    ...requirement.conditions,
    ...alternatives.flatMap((alternative) => alternative.conditions),
  ];
  const soft = requirement.conditions.filter((condition) => condition.strength === 'soft');
  const hard = requirement.conditions.filter((condition) => condition.strength === 'hard');
  const confirmedIds = new Set((message.confirmedWeightIds ?? [])
    .filter((id) => soft.some((condition) => condition.id === id)));
  const total = soft.reduce((sum, condition) => sum + (condition.weight_percent ?? 0), 0);
  const hasPendingWeights = Object.keys(weightDrafts).length > 0;
  const pendingUpdate = prepareWeightUpdate();
  const pendingSoft = pendingUpdate?.requirement.conditions
    .filter((condition) => condition.strength === 'soft') ?? soft;
  const pendingTotal = pendingSoft.reduce((sum, condition) => sum + (condition.weight_percent ?? 0), 0);
  const pendingConfirmedIds = new Set(pendingUpdate?.confirmedWeightIds ?? confirmedIds);
  const confirmedTotal = pendingSoft.reduce((sum, condition) => sum + (
    pendingConfirmedIds.has(condition.id) ? condition.weight_percent ?? 0 : 0
  ), 0);
  const weightsValid = soft.length === 0 || (pendingUpdate !== null
    && pendingSoft.every((condition) => Number.isInteger(condition.weight_percent)
      && (condition.weight_percent ?? -1) >= 0
      && (condition.weight_percent ?? 101) <= 100)
    && pendingTotal === 100
  );
  const weightError = pendingUpdate === null
    ? t('Nhập trọng số là số nguyên từ 0 đến 100.', 'Enter whole-number weights from 0 to 100.')
    : confirmedTotal > 100
      ? t(`Các trọng số đã chốt vượt ${confirmedTotal - 100}%. Hãy giảm trọng số để tiếp tục.`,
        `Confirmed weights exceed 100% by ${confirmedTotal - 100}%. Reduce a weight to continue.`)
      : pendingTotal < 100
        ? t(`Còn thiếu ${100 - pendingTotal}% để đủ 100%. Hãy tăng trọng số để tiếp tục.`,
          `${100 - pendingTotal}% remains to reach 100%. Increase a weight to continue.`)
        : t(`Vượt ${pendingTotal - 100}%. Hãy giảm trọng số để tổng bằng 100%.`,
          `${pendingTotal - 100}% over the limit. Reduce weights to total 100%.`);
  const valuesValid =
    allConditions.every((condition) => {
      if (!condition.quote.trim() || !requirement.raw_text.includes(condition.quote)) return false;
      if (condition.field === 'destination' && condition.operator === 'any')
        return (
          Array.isArray(condition.value) &&
          condition.value.length > 1 &&
          condition.value.every((value) => typeof value === 'string' && value.trim())
        );
      if (typeof condition.value === 'string') return Boolean(condition.value.trim());
      if (typeof condition.value === 'number')
        return Number.isFinite(condition.value) && condition.value > 0;
      return Array.isArray(condition.value) && condition.value.length > 0;
    }) &&
    alternatives.every((alternative) => alternative.label.trim().length > 0) &&
    requirement.raw_text.length <= 8000;
  const canRun = weightsValid && valuesValid && !busy && message.status !== 'running';

  function withWeights(weights: Map<string, number>): CurrentRequirement {
    return {
      ...requirement,
      conditions: requirement.conditions.map((condition) => condition.strength === 'soft'
        ? { ...condition, weight_percent: weights.get(condition.id) ?? 0 }
        : condition),
    };
  }

  function prepareWeightUpdate() {
    const edits = Object.entries(weightDrafts);
    if (edits.some(([, raw]) => !validWeightInput(raw))) return null;
    if (edits.length === 0) return { requirement, confirmedWeightIds: [...confirmedIds] };
    const nextConfirmedIds = new Set([...confirmedIds, ...edits.map(([id]) => id)]);
    const edited = soft.map((condition) => weightDrafts[condition.id] === undefined
      ? condition
      : { ...condition, weight_percent: Number(weightDrafts[condition.id]) });
    return {
      requirement: withWeights(normalizeWeights(edited, nextConfirmedIds)),
      confirmedWeightIds: [...nextConfirmedIds],
    };
  }

  function patchCondition(id: string, changes: Partial<CurrentCondition>) {
    const conditions = requirement.conditions.map((condition) =>
      condition.id === id ? { ...condition, ...changes } : condition,
    );
    const nextAlternatives = alternatives.map((alternative) => ({
      ...alternative,
      conditions: alternative.conditions.map((condition) =>
        condition.id === id ? { ...condition, ...changes } : condition,
      ),
    }));
    const conditionById = new Map(
      [...conditions, ...nextAlternatives.flatMap((alternative) => alternative.conditions)].map(
        (condition) => [condition.id, condition],
      ),
    );
    onChange({
      ...requirement,
      conditions,
      alternatives: nextAlternatives,
      assumptions: requirement.assumptions?.map((assumption) => {
        if (!assumption.condition_ids.includes(id)) return assumption;
        const linked = assumption.condition_ids
          .map((conditionId) => conditionById.get(conditionId))
          .filter((condition): condition is CurrentCondition => Boolean(condition));
        const start = linked.find((condition) => condition.field === 'date_from')?.value;
        const end = linked.find((condition) => condition.field === 'date_to')?.value;
        if (typeof start !== 'string' || typeof end !== 'string')
          return { ...assumption, edited: true };
        return { ...assumption, date_from: start, date_to: end, edited: true };
      }),
    });
  }

  function patchAlternativeLabel(id: string, label: string) {
    onChange({
      ...requirement,
      alternatives: alternatives.map((alternative) =>
        alternative.id === id ? { ...alternative, label } : alternative,
      ),
    });
  }

  function removeCondition(id: string) {
    const conditions = requirement.conditions.filter((condition) => condition.id !== id);
    const nextAlternatives = alternatives
      .map((alternative) => ({
        ...alternative,
        conditions: alternative.conditions.filter((condition) => condition.id !== id),
      }))
      .filter((alternative) => alternative.conditions.length > 0);
    const remainingSoft = conditions.filter((condition) => condition.strength === 'soft');
    const nextConfirmedIds = new Set([...confirmedIds].filter((confirmedId) => confirmedId !== id));
    const normalized = requirement.conditions.find((condition) => condition.id === id)?.strength === 'soft'
      ? normalizeWeights(remainingSoft, nextConfirmedIds)
      : null;
    onChange({
      ...requirement,
      alternatives: nextAlternatives,
      assumptions: requirement.assumptions?.filter(
        (assumption) => !assumption.condition_ids.includes(id),
      ),
      conditions: conditions.map((condition) =>
        condition.strength === 'soft' && normalized
          ? { ...condition, weight_percent: normalized.get(condition.id) ?? 0 }
          : condition,
      ),
    }, [...nextConfirmedIds]);
    setWeightDrafts((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });
  }

  function divideEvenly() {
    if (soft.length === 0) return;

    const base = Math.floor(100 / soft.length);
    const remainder = 100 % soft.length;
    const weights = new Map(
      soft.map((condition, index) => [
        condition.id,
        base + Number(index < remainder),
      ]),
    );

    onChange(withWeights(weights), []);
    setWeightDrafts({});
  }

  function changeWeight(condition: CurrentCondition, raw: string) {
    setWeightDrafts((current) => ({ ...current, [condition.id]: raw }));
  }

  function finishWeightEdit(condition: CurrentCondition, explicitValue?: string) {
    const raw = explicitValue ?? weightDrafts[condition.id];
    if (raw === undefined || !validWeightInput(raw)) return;
    const weights = reallocateWeight(soft, condition.id, Number(raw), confirmedIds);
    if (!weights) return;
    onChange(withWeights(weights), [...new Set([...confirmedIds, condition.id])]);
    setWeightDrafts((current) => {
      const next = { ...current };
      delete next[condition.id];
      return next;
    });
  }

  function runComparison() {
    if (!canRun || !pendingUpdate) return;
    if (hasPendingWeights) {
      onChange(pendingUpdate.requirement, pendingUpdate.confirmedWeightIds);
      setWeightDrafts({});
    }
    onRun(pendingUpdate.requirement);
  }

  function changeValue(condition: CurrentCondition, value: string) {
    let next: unknown = value;
    if (typeof condition.value === 'number') next = value === '' ? 0 : Number(value);
    else if (Array.isArray(condition.value))
      next = value
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
    patchCondition(condition.id, { value: next });
  }

  function commitReviewedValue(
    condition: CurrentCondition,
    inputValue: string,
    initialValue: string,
  ) {
    const quote = inputValue.trim();
    if (!quote || inputValue === initialValue) return;
    let value: unknown = inputValue;
    if (typeof condition.value === 'number') value = Number(inputValue);
    else if (Array.isArray(condition.value))
      value = inputValue
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);

    const otherQuotes = allConditions
      .filter((item) => item.id !== condition.id)
      .map((item) => item.quote)
      .filter(Boolean);
    const overlapsAnotherQuote = otherQuotes.some(
      (other) => other.includes(condition.quote) || condition.quote.includes(other),
    );
    const canReplaceSourceQuote =
      condition.quote &&
      requirement.raw_text.includes(condition.quote) &&
      !overlapsAnotherQuote &&
      !(requirement.assumptions ?? []).some((assumption) => assumption.quote === condition.quote);
    const rawText = canReplaceSourceQuote
      ? requirement.raw_text.replace(condition.quote, quote)
      : `${requirement.raw_text}\n${quote}`;

    onChange({
      ...requirement,
      raw_text: rawText,
      conditions: requirement.conditions.map((item) =>
        item.id === condition.id ? { ...item, value, quote } : item,
      ),
      alternatives: alternatives.map((alternative) => ({
        ...alternative,
        conditions: alternative.conditions.map((item) =>
          item.id === condition.id ? { ...item, value, quote } : item,
        ),
      })),
    });
  }

  function conditionEditor(condition: CurrentCondition) {
    const rawWeight = weightDrafts[condition.id];
    const invalidWeight = rawWeight !== undefined && !validWeightInput(rawWeight);
    const errorId = `${weightHelpId}-${encodeURIComponent(condition.id)}`;
    const text = Array.isArray(condition.value)
      ? condition.value.map((value) => display(value)).join(', ')
      : typeof condition.value === 'number'
        ? String(condition.value)
        : display(condition.value);
    const label = `${fieldLabel(condition.field, t)} — ${
      condition.strength === 'hard' ? t('Bắt buộc', 'Required') : t('Ưu tiên', 'Preference')
    }`;
    return (
      <div className={styles['brief-condition']} key={condition.id}>
        <label className={styles['brief-condition-field']}>
          <span>{label}</span>
          {condition.field === 'transport' ? (
            <select
              value={String(condition.value)}
              disabled={busy || message.status === 'running'}
              aria-label={label}
              onFocus={() => {
                editStartValues.current[condition.id] = text;
              }}
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
                <option value={value} key={value}>
                  {optionLabel}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={
                condition.field === 'date_from' || condition.field === 'date_to'
                  ? 'date'
                  : typeof condition.value === 'number'
                    ? 'number'
                    : 'text'
              }
              min={typeof condition.value === 'number' ? 1 : undefined}
              value={text}
              disabled={busy || message.status === 'running'}
              aria-label={label}
              onFocus={() => {
                editStartValues.current[condition.id] = text;
              }}
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
                value={weightDrafts[condition.id] ?? condition.weight_percent ?? ''}
                disabled={busy || message.status === 'running'}
                aria-label={t(`Trọng số ${String(condition.value)}`, `Weight for ${String(condition.value)}`)}
                aria-invalid={invalidWeight || undefined}
                aria-describedby={invalidWeight ? `${weightHelpId} ${errorId}` : weightHelpId}
                onChange={(event) => changeWeight(condition, event.target.value)}
                onBlur={() => finishWeightEdit(condition)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    finishWeightEdit(condition, event.currentTarget.value);
                  }
                }}
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
        {invalidWeight && (
          <span id={errorId} className={styles['brief-weight-error']}>
            {t('Trọng số phải là số nguyên từ 0 đến 100.', 'Weight must be a whole number from 0 to 100.')}
          </span>
        )}
      </div>
    );
  }

  return (
    <section
      className={styles['decision-brief']}
      aria-label={t('Bản tóm tắt quyết định', 'Decision brief')}
    >
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
        <fieldset
          className={styles['brief-section']}
          disabled={busy || message.status === 'running'}
        >
          <legend>{t('Điều kiện bắt buộc', 'Must-haves')}</legend>
          {hard.map(conditionEditor)}
        </fieldset>
      )}

      {requirement.assumptions && requirement.assumptions.length > 0 && (
        <section
          className={styles['brief-assumptions']}
          aria-label={t('Giả định có thể chỉnh sửa', 'Editable assumptions')}
        >
          <h3>{t('Giả định ngày', 'Date assumptions')}</h3>
          {requirement.assumptions.map((assumption) => (
            <p key={assumption.id}>
              <strong>
                {assumption.edited
                  ? t('Khoảng ngày đã chỉnh sửa', 'Edited date range')
                  : assumption.label}
              </strong>
              <span>
                {t(
                  `Diễn giải từ: “${assumption.quote}” · ${assumption.date_from} đến ${assumption.date_to} · ${assumption.timezone}. Có thể chỉnh ngày trong bản yêu cầu.`,
                  `Interpreted from “${assumption.quote}” · ${assumption.date_from} to ${assumption.date_to} · ${assumption.timezone}. You can edit the linked dates in this brief.`,
                )}
              </span>
            </p>
          ))}
        </section>
      )}

      {alternatives.length > 0 && (
        <section
          className={styles['brief-section']}
          aria-label={t('Các phương án lựa chọn', 'Alternative options')}
        >
          <h3 className={styles['brief-section-title']}>
            {t('Các phương án · chọn sau khi so sánh', 'Options · decide after comparison')}
          </h3>
          <p className={styles['brief-empty']}>
            {t(
              'Điều kiện chung phải đạt; trong từng phương án, các tiêu chí phải cùng đạt. Chỉ cần một phương án đạt là tour đủ điều kiện.',
              'Shared criteria must pass. All criteria within one option must pass; a tour is eligible if any option passes.',
            )}
          </p>
          {alternatives.map((alternative, index) => (
            <fieldset
              key={alternative.id}
              className={styles['brief-alternative']}
              disabled={busy || message.status === 'running'}
            >
              <legend>{t(`Phương án ${index + 1}`, `Option ${index + 1}`)}</legend>
              <label className={styles['brief-alternative-label']}>
                <span>{t('Tên phương án', 'Option name')}</span>
                <input
                  value={alternative.label}
                  maxLength={160}
                  aria-label={t(`Tên phương án ${index + 1}`, `Option ${index + 1} name`)}
                  onChange={(event) => patchAlternativeLabel(alternative.id, event.target.value)}
                />
              </label>
              {alternative.conditions.map(conditionEditor)}
            </fieldset>
          ))}
        </section>
      )}

      <fieldset className={styles['brief-section']} disabled={busy || message.status === 'running'}>
        <legend>{t('Ưu tiên mềm', 'Preferences')}</legend>
        {soft.length > 0 ? (
          soft.map(conditionEditor)
        ) : (
          <p className={styles['brief-empty']}>
            {t(
              'Chưa có sở thích mềm. Bạn vẫn có thể so giá và xem các phương án cân bằng.',
              'No soft preferences yet. You can still compare prices and balanced options.',
            )}
          </p>
        )}
      </fieldset>

      {soft.length > 0 && (
        <div className={styles['brief-weight-summary']}>
          <span aria-live="polite">
            {hasPendingWeights
              ? t('Đang chỉnh trọng số', 'Editing weights')
              : t(`Đã phân bổ ${total} / 100 điểm`, `${total} / 100 points assigned`)}
          </span>
          <button
            type="button"
            disabled={busy || message.status === 'running'}
            onClick={divideEvenly}
          >
            {t('Chia đều', 'Divide evenly')}
          </button>
        </div>
      )}
      {soft.length > 0 && (
        <p id={weightHelpId} className={styles['brief-empty']}>
          {t('Nhấn Enter hoặc rời ô để chốt. Các mục đã chốt vẫn sửa được và không bị tự cân lại. “Chia đều” đặt lại tất cả trọng số.',
            'Press Enter or leave a changed field to confirm. Confirmed weights stay editable and are excluded from automatic allocation. “Divide evenly” resets all weights.')}
        </p>
      )}

      {requirement.missing.length > 0 && (
        <p className={styles['brief-empty']}>
          {t(
            `Còn thiếu: ${requirement.missing.join(', ')}`,
            `Still missing: ${requirement.missing.join(', ')}`,
          )}
        </p>
      )}

      <footer className={styles['brief-footer']}>
        <span>
          {t(
            'Điều kiện chung phải đạt; nếu có nhiều phương án thì chỉ cần đạt trọn vẹn một phương án.',
            'Shared criteria must pass; when options exist, one complete option is enough.',
          )}
        </span>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!canRun}
          onClick={runComparison}
        >
          {message.status === 'complete'
            ? t('Chạy lại so sánh', 'Run comparison again')
            : t('So sánh tour', 'Compare tours')}
        </button>
      </footer>
      {!weightsValid && (
        <p className={styles['brief-validation']} role="status">
          {weightError}
        </p>
      )}
      {!valuesValid && (
        <p className={styles['brief-validation']} role="status">
          {t(
            'Kiểm tra lại giá trị tiêu chí hoặc xóa điều kiện không dùng.',
            'Review criterion values or remove unused conditions.',
          )}
        </p>
      )}
    </section>
  );
}
