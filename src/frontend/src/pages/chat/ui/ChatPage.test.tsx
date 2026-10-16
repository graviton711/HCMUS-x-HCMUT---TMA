// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatPage } from './ChatPage';
import { newSession } from '../../../features/session-history';
import { PreferencesProvider } from '../../../shared/preferences';

beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn() as unknown as typeof window.HTMLElement.prototype.scrollIntoView;
});

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
});

describe('ChatPage expired-session recovery', () => {
  it('offers a new session that resends the draft and does not retry the expired session', async () => {
    const session = newSession();
    session.requirementId = 'req_old';
    session.draft = { ...session.draft, text: 'Đà Lạt 3 ngày' };
    const onStart = vi.fn();
    render(
      <PreferencesProvider>
        <ChatPage session={session} onStart={onStart} onChangeSession={() => {}} />
      </PreferencesProvider>,
    );

    const action = await screen.findByRole('button', { name: 'Tạo phiên mới' });
    expect(screen.getByRole('alert').textContent).toContain('Phiên hết hạn.');
    expect(screen.queryByRole('button', { name: 'Thử lại' })).toBeNull();
    expect((screen.getByLabelText('Nhắn cho TourLens') as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(action);
    expect(onStart).toHaveBeenCalledWith('Đà Lạt 3 ngày');
  });
});

describe('ChatPage decision workspace collapse', () => {
  it('collapses the pane, persists the choice, and reopens from the rail', () => {
    const session = newSession();
    render(
      <PreferencesProvider>
        <ChatPage session={session} onStart={() => {}} onChangeSession={() => {}} />
      </PreferencesProvider>,
    );

    expect(
      screen.queryByRole('button', { name: 'Mở không gian quyết định' }),
    ).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Thu gọn không gian quyết định' }));
    expect(
      screen.getByRole('button', { name: 'Mở không gian quyết định' }),
    ).toBeDefined();
    expect(window.localStorage.getItem('tourlens:decision-open:v1')).toBe('0');
    expect(document.querySelector('[data-collapsed="true"]')).not.toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Mở không gian quyết định' }));
    expect(
      screen.queryByRole('button', { name: 'Mở không gian quyết định' }),
    ).toBeNull();
    expect(window.localStorage.getItem('tourlens:decision-open:v1')).toBe('1');
  });

  it('restores the collapsed state from storage', () => {
    window.localStorage.setItem('tourlens:decision-open:v1', '0');
    const session = newSession();
    render(
      <PreferencesProvider>
        <ChatPage session={session} onStart={() => {}} onChangeSession={() => {}} />
      </PreferencesProvider>,
    );
    expect(
      screen.getByRole('button', { name: 'Mở không gian quyết định' }),
    ).toBeDefined();
  });
});
