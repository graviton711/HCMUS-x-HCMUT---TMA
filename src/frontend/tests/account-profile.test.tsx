// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PreferencesProvider } from '../app/preferences';
import { AccountPage } from '../app/profile/AccountHub';
import { Avatar, prepareAvatar } from '../app/profile/Avatar';
import { clearAuth, readAuthProfile, saveAuth, type AuthProfile } from '../app/auth';
import { ProfileHub } from '../app/profile/ProfileHub';
import { ProfileEditor } from '../app/profile/ProfileEditor';
const profile: AuthProfile = {
  id: 'owner',
  name: 'Test Person',
  username: 'person@example.test',
  phone: '',
  home_city: '',
  bio: '',
};
afterEach(() => {
  cleanup();
  clearAuth();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState(null, '', '/account');
});
function setup(fail = false) {
  saveAuth({
    access_token: 'test',
    refresh_token: 'test-r',
    expires_at: Date.now() / 1000 + 3600,
    user: profile,
  });
  const fetcher = vi
    .fn()
    .mockImplementation((_url: string, init?: RequestInit) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            init?.method === 'PATCH'
              ? fail
                ? { error: { message: 'Save failed' } }
                : { user: { ...profile, ...JSON.parse(String(init.body)) } }
              : { user: profile },
          ),
          { status: init?.method === 'PATCH' && fail ? 503 : 200 },
        ),
      ),
    );
  vi.stubGlobal('fetch', fetcher);
  const hub = {
    data: {
      schema_version: '1' as const,
      preferences: null,
      preferences_version: 0,
      templates: [],
      saved_tours: [],
    },
    error: '',
    busy: false,
    mutate: vi.fn(),
    remove: vi.fn(),
    reload: vi.fn(),
  };
  render(
    <PreferencesProvider>
      <AccountPage
        onContinue={vi.fn()}
        onProfileChanged={vi.fn()}
        hub={(view) => (
          <ProfileHub
            view={view}
            owner="owner"
            hub={hub}
            sessions={[]}
            retention={7}
            historyBusy={false}
            onNew={vi.fn()}
            onOpen={vi.fn()}
            onPin={vi.fn()}
            onArchive={vi.fn()}
            onSignIn={vi.fn()}
          />
        )}
      />
    </PreferencesProvider>,
  );
  return fetcher;
}
it('uses one navigation, selected views and retains edits when switching between profile/preferences', async () => {
  setup();
  await waitFor(() => expect(screen.getByText('Test Person')).toBeTruthy());
  expect(screen.getAllByRole('navigation')).toHaveLength(1);
  expect(screen.queryByRole('heading', { name: 'Hồ sơ cá nhân' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Hồ sơ' }));
  fireEvent.change(screen.getByLabelText('Tên hiển thị'), { target: { value: 'New Person' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sở thích' }));
  fireEvent.change(screen.getByLabelText('Khách sạn mong muốn'), { target: { value: '4' } });
  fireEvent.click(screen.getByRole('button', { name: 'Cài đặt' }));
  expect(screen.getAllByRole('button', { name: 'Chọn ngôn ngữ' })).toHaveLength(1);
  expect(screen.getAllByRole('button', { name: 'Xuất kế hoạch đã lưu' })).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Hồ sơ' }));
  expect((screen.getByLabelText('Tên hiển thị') as HTMLInputElement).value).toBe('New Person');
  fireEvent.click(screen.getByRole('button', { name: 'Sở thích' }));
  expect((screen.getByLabelText('Khách sạn mong muốn') as HTMLSelectElement).value).toBe('4');
  expect(window.location.search).toContain('section=preferences');
});
it('persists public personal fields immediately without another GET and keeps email readonly', async () => {
  const fetcher = setup();
  fireEvent.click(screen.getByRole('button', { name: 'Hồ sơ' }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText('Tên hiển thị'), { target: { value: 'New Person' } });
  fireEvent.change(screen.getByLabelText('Thành phố bạn sống'), { target: { value: 'Huế' } });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu hồ sơ' }));
  await screen.findByText('Đã lưu hồ sơ.');
  expect(readAuthProfile()).toMatchObject({ name: 'New Person', home_city: 'Huế' });
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect((screen.getByLabelText('Email đăng nhập') as HTMLInputElement).readOnly).toBe(true);
});
it('keeps failed profile edits for retry', async () => {
  setup(true);
  fireEvent.click(screen.getByRole('button', { name: 'Hồ sơ' }));
  fireEvent.change(screen.getByLabelText('Tên hiển thị'), { target: { value: 'Keep this' } });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu hồ sơ' }));
  await screen.findByText('Save failed');
  expect((screen.getByLabelText('Tên hiển thị') as HTMLInputElement).value).toBe('Keep this');
});
it('falls back to initials on failed image and retries when its URL changes', () => {
  const view = render(
    <Avatar profile={{ ...profile, avatar_url: 'https://example.test/one.jpg' }} />,
  );
  fireEvent.error(view.container.querySelector('img')!);
  expect(view.container.textContent).toBe('TP');
  view.rerender(<Avatar profile={{ ...profile, avatar_url: 'https://example.test/two.jpg' }} />);
  expect(view.container.querySelector('img')?.src).toBe('https://example.test/two.jpg');
});
it('hydrates current personal information while preserving already edited fields', () => {
  const view = render(
    <PreferencesProvider>
      <ProfileEditor profile={profile} onChanged={vi.fn()} />
    </PreferencesProvider>,
  );
  view.rerender(
    <PreferencesProvider>
      <ProfileEditor profile={{ ...profile, home_city: 'Huế' }} onChanged={vi.fn()} />
    </PreferencesProvider>,
  );
  expect((screen.getByLabelText('Thành phố bạn sống') as HTMLInputElement).value).toBe('Huế');
  fireEvent.change(screen.getByLabelText('Thành phố bạn sống'), { target: { value: 'Đà Nẵng' } });
  view.rerender(
    <PreferencesProvider>
      <ProfileEditor profile={{ ...profile, home_city: 'Hà Nội' }} onChanged={vi.fn()} />
    </PreferencesProvider>,
  );
  expect((screen.getByLabelText('Thành phố bạn sống') as HTMLInputElement).value).toBe('Đà Nẵng');
});
it('rejects SVG and large original uploads before image decoding', async () => {
  await expect(
    prepareAvatar(new File(['<svg/>'], 'image.svg', { type: 'image/svg+xml' })),
  ).rejects.toThrow('5 MB');
  await expect(
    prepareAvatar(
      new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'photo.jpg', { type: 'image/jpeg' }),
    ),
  ).rejects.toThrow('5 MB');
});
