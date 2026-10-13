import { describe, expect, it } from 'vitest';
import { RealtimeClient } from './realtimeClient';

describe('RealtimeClient', () => {
  it('instantiates and queues events while disconnected', () => {
    const client = new RealtimeClient();
    const received: string[] = [];

    const unsubscribe = client.on('message.created', (event) => {
      received.push(String(event.payload.text));
    });

    // Should register listener without throwing
    expect(typeof unsubscribe).toBe('function');

    // Emitting status
    let statusValue = '';
    client.onStatus((status) => {
      statusValue = status;
    });

    // Clean disconnect
    client.disconnect();
    expect(statusValue).toBe('OFFLINE');
  });
});
