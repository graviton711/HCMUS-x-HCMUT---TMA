// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PreferencesProvider } from '../app/preferences';
import { MonthPicker } from '../components/MonthPicker';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
describe('future month picker', () => {
  it('disables past months while selected historical months can be removed', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-10T03:00:00Z'));
    render(
      <PreferencesProvider>
        <MonthPicker value={['2026-02']} onChange={() => undefined} />
      </PreferencesProvider>,
    );
    expect(
      (screen.getByRole('button', { name: /tháng 3 năm 2026/i }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (screen.getByRole('button', { name: /tháng 10 năm 2026/i }) as HTMLButtonElement).disabled,
    ).toBe(false);
    expect(
      (screen.getByRole('button', { name: /^tháng 2 năm 2026$/i }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });
});
