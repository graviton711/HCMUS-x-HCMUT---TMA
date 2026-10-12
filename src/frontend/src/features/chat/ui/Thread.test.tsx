// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { PreferencesProvider } from '../../../shared/preferences';
import type { ChatMsg } from '../model/types';
import { Thread } from './Thread';

afterEach(cleanup);

describe('Thread tool activity', () => {
  it('groups repeated identical operations and keeps distinct summaries visible', () => {
    const message: ChatMsg = {
      id: 'activity',
      kind: 'tool_activity',
      tools: [
        {
          id: 'call-1',
          name: 'query_tours',
          message: 'Đối chiếu tour theo: điểm đến Đà Lạt',
          status: 'completed',
        },
        {
          id: 'call-2',
          name: 'query_tours',
          message: 'Đối chiếu tour theo: điểm đến Đà Lạt',
          status: 'running',
        },
        {
          id: 'call-3',
          name: 'query_tours',
          message: 'Đối chiếu tour theo: điểm đến Phú Quốc',
          status: 'completed',
        },
      ],
    };

    render(
      <PreferencesProvider>
        <Thread messages={[message]} busy onSend={() => {}} onRelax={() => {}} />
      </PreferencesProvider>,
    );

    const rows = screen.getAllByRole('listitem');
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain('Đối chiếu tour theo: điểm đến Đà Lạt');
    expect(rows[0].textContent).toContain('×2');
    expect(rows[0].getAttribute('data-state')).toBe('running');
    expect(rows[1].textContent).toContain('Đối chiếu tour theo: điểm đến Phú Quốc');
    expect(rows[1].textContent).not.toContain('×');
  });
});
