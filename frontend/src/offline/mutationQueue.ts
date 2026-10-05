import { deleteRecord, getAllRecords, putRecord } from './database';

export type MutationStatus = 'PENDING' | 'SENDING' | 'ACKNOWLEDGED' | 'FAILED' | 'CONFLICT';

export type OfflineMutation = {
  id: string;
  user_id: string;
  organization_id?: string;
  workspace_id: string;
  conversation_id?: string;
  mutation_type: 'message' | 'read_state' | 'notification' | 'draft';
  client_mutation_id: string;
  payload: Record<string, unknown>;
  status: MutationStatus;
  attempt_count: number;
  created_at: string;
  updated_at?: string;
  last_error?: string;
};

export function getBackoffMs(attempt: number): number {
  return Math.min(16000, 1000 * 2 ** Math.max(0, attempt));
}

export function shouldRetryMutation(mutation: OfflineMutation): boolean {
  if (mutation.status === 'ACKNOWLEDGED' || mutation.status === 'CONFLICT') {
    return false;
  }
  return mutation.attempt_count < 6;
}

export class MutationQueue {
  async enqueue(mutation: OfflineMutation): Promise<OfflineMutation> {
    const nextMutation: OfflineMutation = {
      ...mutation,
      status: mutation.status ?? 'PENDING',
      attempt_count: mutation.attempt_count ?? 0,
      updated_at: mutation.updated_at ?? new Date().toISOString(),
    };

    return putRecord<OfflineMutation>('pending_mutations', nextMutation);
  }

  async list(): Promise<OfflineMutation[]> {
    return getAllRecords<OfflineMutation>('pending_mutations');
  }

  async flush(handler: (mutation: OfflineMutation) => Promise<boolean> | boolean): Promise<OfflineMutation[]> {
    const mutations = await this.list();
    const results: OfflineMutation[] = [];

    for (const mutation of mutations) {
      if (mutation.status === 'ACKNOWLEDGED') {
        await deleteRecord('pending_mutations', mutation.id);
        results.push({ ...mutation, status: 'ACKNOWLEDGED' });
        continue;
      }

      const nextMutation: OfflineMutation = {
        ...mutation,
        status: 'SENDING',
        attempt_count: mutation.attempt_count + 1,
        updated_at: new Date().toISOString(),
      };
      await putRecord<OfflineMutation>('pending_mutations', nextMutation);

      try {
        const isHandled = await handler(nextMutation);
        if (isHandled) {
          const acknowledged: OfflineMutation = {
            ...nextMutation,
            status: 'ACKNOWLEDGED',
            updated_at: new Date().toISOString(),
          };
          await deleteRecord('pending_mutations', acknowledged.id);
          results.push(acknowledged);
        } else {
          const failed: OfflineMutation = {
            ...nextMutation,
            status: shouldRetryMutation(nextMutation) ? 'PENDING' : 'FAILED',
            last_error: 'Mutation was not accepted by the server.',
            updated_at: new Date().toISOString(),
          };
          await putRecord<OfflineMutation>('pending_mutations', failed);
          results.push(failed);
        }
      } catch (error) {
        const failure: OfflineMutation = {
          ...nextMutation,
          status: shouldRetryMutation(nextMutation) ? 'PENDING' : 'FAILED',
          last_error: error instanceof Error ? error.message : 'Unknown mutation failure',
          attempt_count: nextMutation.attempt_count,
          updated_at: new Date().toISOString(),
        };
        await putRecord<OfflineMutation>('pending_mutations', failure);
        results.push(failure);
      }
    }

    return results;
  }
}
