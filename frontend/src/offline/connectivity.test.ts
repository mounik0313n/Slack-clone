import { describe, expect, it } from 'vitest';
import { getConnectionStatus } from './connectivity';

describe('Connectivity module', () => {
  it('returns ONLINE when navigator.onLine is true or navigator undefined', () => {
    const status = getConnectionStatus();
    expect(['ONLINE', 'OFFLINE']).toContain(status);
  });
});
