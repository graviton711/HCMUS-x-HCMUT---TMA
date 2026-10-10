import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function record(value: unknown, label = 'data'): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error(`Expected object at ${label}`);
  return value as Record<string, unknown>;
}

function session(value: unknown) {
  const response = record(value, 'session');
  for (const key of ['id', 'session_id', 'token', 'expires_at'])
    expect(typeof response[key]).toBe('string');
  expect(response.token_type).toBe('Bearer');
}

describe('Current FastAPI contracts', () => {
  it('validates real current-backend responses using SQLite fixture data only', () => {
    const root = resolve(import.meta.dirname, '../../../..');
    const python =
      process.platform === 'win32'
        ? resolve(root, '.venv/Scripts/python.exe')
        : resolve(root, '.venv/bin/python');
    expect(existsSync(python), 'Run uv sync in the repository before backend contract tests.').toBe(
      true,
    );
    const output = execFileSync(python, [resolve(import.meta.dirname, 'verify_backend.py')], {
      cwd: root,
      encoding: 'utf8',
      timeout: 30_000,
      maxBuffer: 4 * 1024 * 1024,
    });
    const raw: unknown = JSON.parse(output);
    expect(Array.isArray(raw)).toBe(true);
    if (!Array.isArray(raw)) throw new Error('Invalid contract verification output');

    for (const entry of raw) {
      const item = record(entry);
      expect(typeof item.name).toBe('string');
      const response = record(item.response, String(item.name));
      switch (item.validator) {
        case 'health':
          expect(response.status).toBe('ok');
          expect(typeof response.version).toBe('string');
          break;
        case 'session':
          session(response);
          break;
        case 'catalog':
          expect(Array.isArray(response.destinations)).toBe(true);
          expect(
            (response.destinations as unknown[]).every((item) => typeof item === 'string'),
          ).toBe(true);
          break;
        case 'requirement': {
          const requirement = record(response.requirement, 'requirement');
          expect(typeof requirement.id).toBe('string');
          expect(Array.isArray(requirement.conditions)).toBe(true);
          expect(Array.isArray(requirement.missing)).toBe(true);
          break;
        }
        case 'comparison': {
          const comparison = record(response.comparison, 'comparison');
          expect(typeof comparison.id).toBe('string');
          expect(Array.isArray(comparison.ranked)).toBe(true);
          expect(Array.isArray(comparison.tour_snapshots)).toBe(true);
          expect(Array.isArray(comparison.evaluations)).toBe(true);
          expect(record(comparison.analysis, 'comparison.analysis')).toBeTruthy();
          break;
        }
        case 'history':
          expect(Array.isArray(response.items)).toBe(true);
          expect(response.next_cursor === null || typeof response.next_cursor === 'string').toBe(
            true,
          );
          break;
        case 'history_detail':
          expect(typeof response.id).toBe('string');
          expect(['requirement', 'comparison']).toContain(response.kind);
          expect(typeof record(response.resource).id).toBe('string');
          break;
        default:
          throw new Error(`Unknown current-backend validator: ${String(item.validator)}`);
      }
    }
    expect(raw).toHaveLength(9);
  }, 35_000);
});
