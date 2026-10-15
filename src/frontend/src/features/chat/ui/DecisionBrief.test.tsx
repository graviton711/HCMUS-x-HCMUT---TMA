// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CurrentRequirement } from '../../../shared/api';
import { PreferencesProvider } from '../../../shared/preferences';
import type { ChatMsg } from '../model/types';
import { DecisionBrief } from './DecisionBrief';

type Draft = Extract<ChatMsg, { kind: 'decision_draft' }>;
const names = ['nhẹ nhàng', 'văn hóa lịch sử', 'uy tín'];

function makeDraft(weights = [50, 30, 20], confirmedWeightIds: string[] = []): Draft {
  return {
    id: 'brief-weights',
    kind: 'decision_draft',
    status: 'draft',
    confirmedWeightIds,
    requirement: {
      id: 'req-weights',
      raw_text: `Đà Lạt ${names.join(' ')}`,
      travelers: 1,
      missing: [],
      conditions: [
        { id: 'destination', field: 'destination', operator: 'contains', value: 'Đà Lạt',
          quote: 'Đà Lạt', strength: 'hard' },
        ...weights.map((weight_percent, index) => ({
          id: `s${index}`, field: 'preference', operator: 'contains', value: names[index],
          quote: names[index], strength: 'soft' as const, weight_percent,
        })),
      ],
    },
  };
}

function setup(initial = makeDraft()) {
  const onChange = vi.fn();
  const onRun = vi.fn();
  function Editor() {
    const [message, setMessage] = useState(initial);
    return (
      <PreferencesProvider>
        <DecisionBrief
          key={message.id}
          message={message}
          busy={false}
          onChange={(requirement, confirmedWeightIds) => {
            onChange(requirement, confirmedWeightIds);
            setMessage((previous) => ({ ...previous, requirement,
              confirmedWeightIds: confirmedWeightIds ?? previous.confirmedWeightIds }));
          }}
          onRun={onRun}
        />
      </PreferencesProvider>
    );
  }
  render(<Editor />);
  return { onChange, onRun };
}

function weight(index: number) {
  return screen.getByRole('spinbutton', { name: `Trọng số ${names[index]}` }) as HTMLInputElement;
}

function values(count = 3) {
  return names.slice(0, count).map((_, index) => Number(weight(index).value));
}

function commit(index: number, value: string, enter = false) {
  fireEvent.change(weight(index), { target: { value } });
  if (enter) fireEvent.keyDown(weight(index), { key: 'Enter' });
  else fireEvent.blur(weight(index));
}

const runButton = () => screen.getByRole('button', { name: 'So sánh tour' }) as HTMLButtonElement;

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe('DecisionBrief weight editing', () => {
  it('waits until Enter or blur, retains earlier confirmations, and permits repeated edits', () => {
    const { onChange } = setup();
    fireEvent.change(weight(0), { target: { value: '3' } });
    fireEvent.change(weight(0), { target: { value: '30' } });
    expect(values()).toEqual([30, 30, 20]);
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.keyDown(weight(0), { key: 'Enter' });
    expect(values()).toEqual([30, 42, 28]);
    expect(onChange).toHaveBeenCalledTimes(1);
    fireEvent.blur(weight(0));
    expect(onChange).toHaveBeenCalledTimes(1);

    commit(1, '40');
    expect(values()).toEqual([30, 40, 30]);
    expect(weight(0).disabled).toBe(false);
    commit(0, '20', true);
    expect(values()).toEqual([20, 40, 40]);
    expect(onChange.mock.calls.at(-1)?.[1]).toEqual(['s0', 's1']);
  });

  it('does not confirm an unchanged focus/blur but accepts an explicit Enter confirmation', () => {
    const { onChange } = setup();
    fireEvent.focus(weight(1));
    fireEvent.blur(weight(1));
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.keyDown(weight(1), { key: 'Enter' });
    expect(onChange.mock.calls.at(-1)?.[1]).toEqual(['s1']);
    commit(0, '40');
    expect(values()).toEqual([40, 30, 30]);
  });

  it('keeps fully confirmed totals editable and reports the exact missing or excess amount', () => {
    setup(makeDraft([50, 30, 20], ['s0', 's1', 's2']));
    commit(2, '15');
    expect(values()).toEqual([50, 30, 15]);
    expect(screen.getByRole('status').textContent).toContain('Còn thiếu 5%');
    expect(runButton().disabled).toBe(true);
    commit(2, '30');
    expect(values()).toEqual([50, 30, 30]);
    expect(screen.getByRole('status').textContent).toContain('vượt 10%');
    expect(runButton().disabled).toBe(true);
    commit(2, '20');
    expect(runButton().disabled).toBe(false);
  });

  it('reports an over-budget confirmed subset and resumes balancing when corrected', () => {
    setup(makeDraft([70, 20, 10], ['s0']));
    commit(1, '40');
    expect(values()).toEqual([70, 40, 10]);
    expect(screen.getByRole('status').textContent).toContain('vượt 10%');
    expect(runButton().disabled).toBe(true);
    commit(0, '50');
    expect(values()).toEqual([50, 40, 10]);
    expect(runButton().disabled).toBe(false);
  });

  it.each(['', '-1', '1.5', '101'])('preserves invalid input %j on blur without committing', (raw) => {
    const { onChange, onRun } = setup();
    commit(0, raw);
    expect(weight(0).value).toBe(raw);
    expect(weight(0).getAttribute('aria-invalid')).toBe('true');
    expect(onChange).not.toHaveBeenCalled();
    expect(runButton().disabled).toBe(true);
    fireEvent.click(runButton());
    expect(onRun).not.toHaveBeenCalled();
  });

  it('resets confirmations and invalid input when the user chooses Divide evenly', () => {
    const { onChange } = setup(makeDraft([40, 35, 25], ['s0', 's1']));
    fireEvent.change(weight(0), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Chia đều' }));
    expect(values()).toEqual([34, 33, 33]);
    expect(onChange.mock.calls.at(-1)?.[1]).toEqual([]);
    expect(screen.queryByText('Đã chốt')).toBeNull();
    commit(0, '50');
    expect(values()).toEqual([50, 25, 25]);
  });

  it('does not rebalance confirmed weights when a soft or hard criterion is removed', () => {
    setup(makeDraft([40, 30, 25], ['s0', 's1', 's2']));
    fireEvent.click(screen.getByRole('button', { name: 'Xóa điểm đến — Bắt buộc' }));
    expect(values()).toEqual([40, 30, 25]);
    const remove = screen.getAllByRole('button', { name: 'Xóa sở thích — Ưu tiên' });
    fireEvent.click(remove[2]);
    expect(values(2)).toEqual([40, 30]);
    expect(screen.getByRole('status').textContent).toContain('Còn thiếu 30%');
    commit(0, '70');
    expect(values(2)).toEqual([70, 30]);
    expect(runButton().disabled).toBe(false);
  });

  it('allows a single confirmed criterion to be corrected without silently replacing its value', () => {
    setup(makeDraft([100], ['s0']));
    commit(0, '95');
    expect(weight(0).value).toBe('95');
    expect(runButton().disabled).toBe(true);
    commit(0, '100');
    expect(runButton().disabled).toBe(false);
  });

  it('sends the latest valid pending weights, with editor metadata kept outside the requirement', () => {
    const { onRun, onChange } = setup();
    fireEvent.change(weight(0), { target: { value: '30' } });
    fireEvent.click(runButton());
    const sent = onRun.mock.calls[0]?.[0] as CurrentRequirement;
    expect(sent.conditions.filter((condition) => condition.strength === 'soft')
      .map((condition) => condition.weight_percent)).toEqual([30, 42, 28]);
    expect(sent).not.toHaveProperty('confirmedWeightIds');
    expect(onChange.mock.calls.at(-1)?.[1]).toEqual(['s0']);
  });
});
