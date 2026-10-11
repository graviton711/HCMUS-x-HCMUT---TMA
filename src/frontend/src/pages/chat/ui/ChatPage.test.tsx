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
  it('offers a new session that keeps the draft instead of only retrying', async () => {
    const session = newSession();
    session.requirementId = 'req_old';
    session.draft = { ...session.draft, text: 'Đà Lạt 3 ngày' };
    const onStart = vi.fn();
    render(
      <PreferencesProvider>
        <ChatPage session={session} onStart={onStart} onChangeSession={() => {}} />
      </PreferencesProvider>,
    );

    const action = await screen.findByRole('button', { name: 'Tạo phiên mới và tiếp tục' });
    expect(screen.getByRole('alert').textContent).toMatch(/expired/i);
    fireEvent.click(action);
    expect(onStart).toHaveBeenCalledWith('Đà Lạt 3 ngày');
  });
});
