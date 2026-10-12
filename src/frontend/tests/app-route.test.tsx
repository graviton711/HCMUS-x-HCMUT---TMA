// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PreferencesProvider } from '../src/shared/preferences';
import { App } from '../src/app/App';

afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  vi.stubGlobal('scrollTo', vi.fn());
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  );
});

describe('App route transitions', () => {
  it('resets the document scroll after navigating from chat to support', () => {
    render(
      <PreferencesProvider>
        <App />
      </PreferencesProvider>,
    );

    fireEvent.click(screen.getAllByRole('link', { name: 'Hỗ trợ' })[0]);

    expect(window.location.pathname).toBe('/support');
    expect(window.scrollTo).toHaveBeenLastCalledWith({ left: 0, top: 0, behavior: 'instant' });
  });
});
