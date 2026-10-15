/**
 * Display-only normalization for session titles. Never mutates storage or history.
 * Storage keeps whatever the model wrote; this only makes the rendered string readable.
 */

import type { CurrentRequirement } from '../api';

const MAX_GRAPHEMES = 48;

function graphemes(value: string): string[] {
  const Segmenter = (Intl as { Segmenter?: typeof Intl.Segmenter }).Segmenter;
  if (Segmenter) {
    try {
      return Array.from(
        new Segmenter('vi', { granularity: 'grapheme' }).segment(value),
        (part) => part.segment,
      );
    } catch {
      /* fall through to code units */
    }
  }
  return Array.from(value);
}

/** Drop a trailing copy of the same phrase, e.g. accumulated drafts. */
function collapseRepeat(value: string): string {
  const mid = Math.floor(value.length / 2);
  for (let cut = mid; cut >= 8; cut -= 1) {
    const head = value.slice(0, cut).trim();
    if (head && head === value.slice(cut).trim()) return head;
  }
  return value;
}

export function displaySessionTitle(raw: string | null | undefined, fallback: string): string {
  if (!raw) return fallback;
  const cleaned = raw
    .normalize('NFC')
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200d\u2060\ufeff]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!cleaned) return fallback;
  // Raw ids/hashes must never surface as a session name.
  if (/^[a-f0-9-]{20,}$/i.test(cleaned)) return fallback;

  const text = collapseRepeat(cleaned);
  const parts = graphemes(text);
  if (parts.length <= MAX_GRAPHEMES) return text;

  const kept = parts.slice(0, MAX_GRAPHEMES).join('');
  const space = kept.lastIndexOf(' ');
  return `${(space > MAX_GRAPHEMES * 0.6 ? kept.slice(0, space) : kept).trimEnd()}…`;
}

const TITLE_FALLBACK = 'New trip';

/**
 * Session name built from an interpreted requirement. Prefer the confirmed
 * destination so the sidebar never shows a mangled copy of the raw request.
 */
export function sessionTitle(requirement: CurrentRequirement, rawText: string): string {
  const destination = requirement.conditions.find(
    (condition) => condition.field === 'destination' && condition.value != null,
  );
  const alternativeDestination = requirement.alternatives
    ?.flatMap((alternative) => alternative.conditions)
    .find((condition) => condition.field === 'destination' && condition.value != null);
  const source =
    destination && typeof destination.value === 'string' && destination.value.trim()
      ? destination.value
      : alternativeDestination && typeof alternativeDestination.value === 'string'
        ? alternativeDestination.value
        : requirement.alternatives?.[0]?.label || rawText;
  return displaySessionTitle(source, TITLE_FALLBACK);
}
