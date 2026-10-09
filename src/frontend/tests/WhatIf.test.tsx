import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { whatIf } from '../api/contracts';
import { analysisFixture } from './fixtures/whatIf';
import { PreferencesProvider } from '../app/preferences';
import { WhatIfPanel } from '../features/workspace/WhatIfPanel';

describe('what-if evidence and percentages', () => {
  it('accepts an unknown cohort, shows no percentage and omits unsafe source links', () => {
    const a = analysisFixture();
    expect(() => whatIf(a)).not.toThrow();
    const html = renderToStaticMarkup(
      <PreferencesProvider>
        <WhatIfPanel
          analysis={a}
          disabled={false}
          onAnalyze={() => {}}
          onApply={() => {}}
          onEvidence={() => {}}
        />
      </PreferencesProvider>,
    );
    expect(html).toContain('Chưa xác định');
    expect(html).not.toContain('javascript:');
    expect(html).toContain('Trước chưa đủ dữ liệu, nay đạt');
    expect(html).toContain('Xem đề xuất sửa nhu cầu');
  });
  it('rejects a falsely computed percentage when the original cohort was unknown', () => {
    const a = analysisFixture();
    Object.assign(a.result!.scenarios[0].restriction_ratio, {
      state: 'computed',
      percent: 100 / 3,
    });
    expect(() => whatIf(a)).toThrow();
  });
  it('rejects a fabricated ratio or witness from another cohort', () => {
    const a = analysisFixture();
    a.result!.scenarios[0].restriction_ratio.numerator = 2;
    expect(() => whatIf(a)).toThrow();
    const b = analysisFixture();
    b.result!.scenarios[0].witnesses[0].candidate_id = 'a';
    expect(() => whatIf(b)).toThrow();
  });
  it('rejects a result attached to a different analysis identity', () => {
    const a = analysisFixture();
    a.result!.id = 'other';
    expect(() => whatIf(a)).toThrow();
  });
});
