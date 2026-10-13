import { describe, expect, it } from 'vitest';
import { overallStatus } from './status';

describe('overallStatus', () => {
  it('reports a running target before any settled one', () => {
    expect(overallStatus(['completed', 'uploading'])).toBe('uploading');
  });

  it('reports a failure over a success', () => {
    expect(overallStatus(['completed', 'failed'])).toBe('failed');
  });

  it('falls back to queued when there are no targets', () => {
    expect(overallStatus([])).toBe('queued');
  });
});
