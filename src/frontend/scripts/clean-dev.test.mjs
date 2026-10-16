// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { pidsForPorts } from '../scripts/clean-dev.mjs';

const SAMPLE = [
  '  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       7356',
  '  TCP    127.0.0.1:5173         0.0.0.0:0              LISTENING       14720',
  '  TCP    127.0.0.1:8000         127.0.0.1:58158        TIME_WAIT       0',
  '  TCP    127.0.0.1:80000        0.0.0.0:0              LISTENING       9999',
  '  TCP    127.0.0.1:3000         0.0.0.0:0              LISTENING       1111',
].join('\n');

describe('pidsForPorts', () => {
  it('collects only LISTENING owners of the exact dev ports', () => {
    expect(pidsForPorts(SAMPLE, [8000, 4099, 5173]).sort()).toEqual(['14720', '7356']);
  });

  it('ignores TIME_WAIT rows and port prefixes', () => {
    expect(pidsForPorts(SAMPLE, [8000])).toEqual(['7356']);
  });
});
