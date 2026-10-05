import { describe, expect, it } from 'vitest';

import { MutationQueue, getBackoffMs } from './mutationQueue';

describe('MutationQueue', () => {
  it('queues offline mutations and retries with exponential backoff', async () => {
    const queue = new MutationQueue();
    const sent: string[] = [];

    await queue.enqueue({
      id: 'mutation-1',
      user_id: 'user-1',
      organization_id: 'org-1',
      workspace_id: 'ws-1',
      conversation_id: 'conversation-1',
      mutation_type: 'message',
      client_mutation_id: 'client-1',
      payload: { body: 'hello' },
      status: 'PENDING',
      attempt_count: 0,
      created_at: new Date().toISOString(),
    });

    await queue.flush(async (mutation) => {
      sent.push(mutation.id);
      return true;
    });

    expect(sent).toEqual(['mutation-1']);
    expect(getBackoffMs(0)).toBe(1000);
    expect(getBackoffMs(3)).toBe(8000);
  });
});
