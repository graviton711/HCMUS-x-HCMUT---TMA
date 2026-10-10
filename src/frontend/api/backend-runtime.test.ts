import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import * as contracts from './contracts';

describe('Actual backend route contracts', () => {
  it('validates real FastAPI responses from an isolated fixture backend with no real NIM calls', () => {
    const root = resolve(import.meta.dirname, '../../..');
    const python =
      process.platform === 'win32'
        ? resolve(root, '.venv/Scripts/python.exe')
        : resolve(root, '.venv/bin/python');
    expect(
      existsSync(python),
      'Run uv sync in the repository before backend integration tests.',
    ).toBe(true);
    const output = execFileSync(python, [resolve(import.meta.dirname, 'verify_backend.py')], {
      cwd: root,
      encoding: 'utf8',
      timeout: 30_000,
      maxBuffer: 4 * 1024 * 1024,
    });
    const raw: unknown = JSON.parse(output);
    expect(Array.isArray(raw)).toBe(true);
    if (!Array.isArray(raw)) throw new Error('Invalid contract verification output');
    const validators: Record<string, contracts.Validator> = {
      history: contracts.history,
      historyDetail: contracts.historyDetail,
      historyMetadata: contracts.historyMetadata,
      acceptedWhatIf: contracts.acceptedWhatIf,
      whatIf: contracts.whatIf,
      health: contracts.health,
      session: contracts.session,
      catalog: contracts.catalog,
      requirement: contracts.requirement,
      createRequirement: contracts.createRequirement,
      proposal: contracts.proposal,
      createProposal: contracts.createProposal,
      cancelProposal: contracts.cancelProposal,
      acceptedComparison: contracts.acceptedComparison,
      comparison: contracts.comparison,
      job: contracts.job,
      events: contracts.events,
      evidence: contracts.evidence,
      acceptedMessage: contracts.acceptedMessage,
      message: contracts.message,
      contact: contracts.contact,
      cancelJob: contracts.cancelJob,
      errorPayload: contracts.errorPayload,
    };
    for (const entry of raw) {
      const item = contracts.record(entry);
      if (typeof item.validator !== 'string' || typeof item.name !== 'string')
        throw new Error('Invalid verification entry');
      const validator = validators[item.validator];
      if (!validator) throw new Error(`Unknown validator ${item.validator}`);
      const data =
        item.validator === 'health' || item.validator === 'errorPayload'
          ? item.response
          : contracts.envelope(item.response).data;
      expect(() => validator(data), item.name).not.toThrow();
    }
    expect(raw.length).toBeGreaterThanOrEqual(25);
  }, 35_000);
});
