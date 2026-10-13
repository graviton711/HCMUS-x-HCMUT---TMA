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

    const action = await screen.findByRole('button', { name: 'Tạo phiên mới và gửi lại bản nháp' });
    expect(screen.getByRole('alert').textContent).toContain('Phiên khách đã hết hạn');
    expect(screen.queryByRole('button', { name: 'Thử lại' })).toBeNull();
    expect((screen.getByLabelText('Nhắn cho TourLens') as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(action);
    expect(onStart).toHaveBeenCalledWith('Đà Lạt 3 ngày');
  });
});
