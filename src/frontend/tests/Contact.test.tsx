// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ContactPage } from '../app/PublicPages';
import { PreferencesProvider } from '../app/preferences';

const server = vi.hoisted(() => ({ session: vi.fn(), contact: vi.fn() }));
vi.mock('../api/client', () => ({
  api: server,
  ApiClient: function () {
    return server;
  },
}));

function contact(requestedCategory?: string | null) {
  return (
    <PreferencesProvider>
      <ContactPage requestedCategory={requestedCategory} />
    </PreferencesProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.clearAllMocks();
  server.session.mockResolvedValue({ id: 'guest-test', token: 'test-only-token' });
  server.contact.mockResolvedValue({ ticket_id: 'ticket-test' });
});
afterEach(cleanup);

describe('contact entry intent', () => {
  it('uses feedback for an unsupported query without sending anything', () => {
    render(contact('admin'));
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('feedback');
    expect(server.session).not.toHaveBeenCalled();
    expect(server.contact).not.toHaveBeenCalled();
  });

  it('changes entry category without losing a draft, and preserves a manual choice on rerender', async () => {
    const view = render(contact('data_issue'));
    const message = screen.getByRole('textbox', {
      name: 'Bạn muốn nhắn điều gì?',
    }) as HTMLTextAreaElement;
    const email = screen.getByRole('textbox', {
      name: 'Email liên hệ (tùy chọn)',
    }) as HTMLInputElement;
    const category = screen.getByRole('combobox') as HTMLSelectElement;
    fireEvent.change(message, { target: { value: 'Kiểm tra lịch của https://example.test/tour' } });
    fireEvent.change(email, { target: { value: 'browser@example.test' } });
    view.rerender(contact('support'));
    await waitFor(() => expect(category.value).toBe('support'));
    expect(message.value).toContain('https://example.test/tour');
    expect(email.value).toBe('browser@example.test');
    fireEvent.change(category, { target: { value: 'feedback' } });
    view.rerender(contact('support'));
    expect(category.value).toBe('feedback');
    view.rerender(contact(null));
    expect(category.value).toBe('feedback');
    expect(message.value).toContain('https://example.test/tour');
    expect(server.contact).not.toHaveBeenCalled();
  });

  it('submits the report category and reuses the submission key after a failed response', async () => {
    server.contact.mockRejectedValueOnce(new Error('Không kết nối được backend.'));
    render(contact('data_issue'));
    fireEvent.change(screen.getByRole('textbox', { name: 'Bạn muốn nhắn điều gì?' }), {
      target: { value: '  Giá của https://example.test/tour cần kiểm tra.  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Gửi liên hệ' }));
    await screen.findByRole('alert');
    expect(server.contact).toHaveBeenCalledTimes(1);
    const [payload, options] = server.contact.mock.calls[0];
    expect(payload).toMatchObject({
      category: 'data_issue',
      message: 'Giá của https://example.test/tour cần kiểm tra.',
      reply_to: null,
      context: { session_id: 'guest-test' },
    });
    expect(options.idempotencyKey).toBe(payload.client_submission_id);
    fireEvent.click(screen.getByRole('button', { name: 'Gửi liên hệ' }));
    await screen.findByRole('status');
    expect(server.contact.mock.calls[1]).toEqual([payload, options]);
    expect(server.session).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('status').textContent).toContain('ticket-test');
  });
});
