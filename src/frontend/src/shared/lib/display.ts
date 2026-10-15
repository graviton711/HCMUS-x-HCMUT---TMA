type Translate = (vi: string, en: string) => string;

/** UTC date-only label (departure dates). No timezone shift. */
export function dateOnlyText(value: string, locale: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
  ).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-GB', {
    timeZone: 'UTC',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export type EvaluationState = 'pass' | 'partial' | 'fail' | 'unknown';

/** Evaluation state badge label. */
export function evaluationStateText(state: EvaluationState, t: Translate): string {
  if (state === 'pass') return t('Đạt', 'Pass');
  if (state === 'partial') return t('Đạt một phần', 'Partial');
  if (state === 'fail') return t('Không đạt', 'Fail');
  return t('Chưa rõ', 'Unknown');
}

/** Listed price label. Null means contact-for-price. */
export function priceText(
  price: number | null,
  currency: string,
  locale: string,
  t: Translate,
): string {
  if (price == null) return t('Liên hệ', 'Contact');
  const amount = price.toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-GB');
  const currencyLabel = currency ? ` ${currency}` : t(' · chưa rõ tiền tệ', ' · currency unknown');
  return `${amount}${currencyLabel}`;
}
