// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { displaySessionTitle } from './sessionTitle';

describe('displaySessionTitle', () => {
  it('falls back for empty titles', () => {
    expect(displaySessionTitle('', 'Chuyến đi mới')).toBe('Chuyến đi mới');
    expect(displaySessionTitle('   ', 'Chuyến đi mới')).toBe('Chuyến đi mới');
    expect(displaySessionTitle(null, 'Chuyến đi mới')).toBe('Chuyến đi mới');
  });

  it('strips control characters and collapses whitespace', () => {
    expect(displaySessionTitle('Đà Lạt\u0000 3 ngày\n\n2 đêm', 'x')).toBe('Đà Lạt 3 ngày 2 đêm');
  });

  it('never splits a grapheme cluster when truncating', () => {
    const title = '👨‍👩‍👧‍👦'.repeat(20);
    const shown = displaySessionTitle(title, 'x');
    expect(shown.endsWith('…')).toBe(true);
    expect(shown).not.toMatch(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])/u);
  });

  it('collapses a repeated phrase instead of showing it twice', () => {
    expect(displaySessionTitle('Đà Lạt 3 ngày Đà Lạt 3 ngày', 'x')).toBe('Đà Lạt 3 ngày');
  });

  it('hides raw ids', () => {
    expect(displaySessionTitle('492cf6c9-c043-4fbb-9df9-2324d849f3ac', 'Chuyến đi mới')).toBe(
      'Chuyến đi mới',
    );
  });

  it('keeps a short readable title untouched', () => {
    expect(displaySessionTitle('Đà Lạt cuối tuần', 'x')).toBe('Đà Lạt cuối tuần');
  });
});
