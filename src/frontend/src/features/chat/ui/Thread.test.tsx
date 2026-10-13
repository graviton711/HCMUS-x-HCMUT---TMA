// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { PreferencesProvider } from '../../../shared/preferences';
import type { ChatMsg } from '../model/types';
import { Thread } from './Thread';

afterEach(cleanup);

describe('Thread tool activity', () => {
  it('keeps progress to one line and expands the ordered tool timeline', () => {
    const message: ChatMsg = {
      id: 'activity',
      kind: 'tool_activity',
      tools: [
        {
          id: 'call-1',
          name: 'query_tours',
          message: 'Đã lọc tour theo điểm đến Đà Lạt',
          status: 'completed',
        },
        {
          id: 'call-2',
          name: 'catalog_facets',
          message: 'Đang kiểm tra các điểm đến trong danh mục',
          status: 'running',
        },
        {
          id: 'call-3',
          name: 'tour_detail',
          message: 'Chưa đọc được chi tiết tour',
          status: 'error',
        },
        {
          id: 'call-4',
          name: 'query_tours',
          message: 'Đã đối chiếu giá tour',
          status: 'completed',
        },
      ],
    };

    render(
      <PreferencesProvider>
        <Thread messages={[message]} busy onSend={() => {}} onRelax={() => {}} />
      </PreferencesProvider>,
    );

    const details = document.querySelector('details');
    expect(details).not.toBeNull();
    expect(details?.open).toBe(false);
    expect(details?.querySelector('summary')?.textContent).toContain(
      'Đang kiểm tra các điểm đến trong danh mục',
    );

    fireEvent.click(details?.querySelector('summary') as HTMLElement);

    const rows = within(details as HTMLElement).getAllByRole('listitem');
    expect(rows).toHaveLength(4);
    expect(rows[0].textContent).toContain('Đã lọc tour theo điểm đến Đà Lạt');
    expect(rows[0].textContent).toContain('Hoàn tất');
    expect(rows[1].textContent).toContain('Đang kiểm tra các điểm đến trong danh mục');
    expect(rows[1].textContent).toContain('Đang chạy');
    expect(rows[2].textContent).toContain('Chưa đọc được chi tiết tour');
    expect(rows[2].textContent).toContain('Chưa hoàn tất');
    expect(rows[3].textContent).toContain('Đã đối chiếu giá tour');
  });

  it('uses a single synthesis line after tool calls and summarizes the completed steps', () => {
    const message: ChatMsg = {
      id: 'activity',
      kind: 'tool_activity',
      tools: [
        { id: 'call-1', name: 'query_tours', message: 'Đã lọc tour', status: 'completed' },
        { id: 'call-2', name: 'tour_detail', message: 'Đã đọc chi tiết tour', status: 'completed' },
      ],
    };

    const { rerender } = render(
      <PreferencesProvider>
        <Thread messages={[message]} busy onSend={() => {}} onRelax={() => {}} />
      </PreferencesProvider>,
    );
    expect(screen.getByText('Đang tổng hợp kết quả')).toBeTruthy();

    rerender(
      <PreferencesProvider>
        <Thread messages={[message]} busy={false} onSend={() => {}} onRelax={() => {}} />
      </PreferencesProvider>,
    );
    expect(screen.getByText('Đã kiểm tra 2 bước')).toBeTruthy();
  });
});
