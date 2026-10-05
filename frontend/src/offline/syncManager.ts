import { getDeviceId, listPendingMutations, savePendingMutation, clearPendingMutation } from './indexedDb';
import { getConnectionStatus, type NetworkState } from './connectivity';
import { saveSyncState, type SyncStateRecord } from './repositories/syncRepository';
import { saveMessage, type CachedMessage } from './repositories/messageRepository';

export type { NetworkState };

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function resolveDeviceId() {
  return getDeviceId();
}

export function getConnectionState(): NetworkState {
  return getConnectionStatus();
}

export async function queueMutationForSync(mutation: {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  client_mutation_id: string;
  created_at: string;
  status?: string;
  attempt_count?: number;
  last_error?: string;
  user_id?: string;
  organization_id?: string;
  workspace_id?: string;
  conversation_id?: string;
}) {
  await savePendingMutation({
    id: mutation.id,
    type: mutation.type as 'message' | 'read_state' | 'notification' | 'draft',
    payload: mutation.payload,
    client_mutation_id: mutation.client_mutation_id,
    created_at: mutation.created_at,
    status: (mutation.status as 'PENDING' | 'SENDING' | 'ACKNOWLEDGED' | 'FAILED' | 'CONFLICT') ?? 'PENDING',
    attempt_count: mutation.attempt_count ?? 0,
    last_error: mutation.last_error,
    user_id: mutation.user_id,
    organization_id: mutation.organization_id,
    workspace_id: mutation.workspace_id,
    conversation_id: mutation.conversation_id,
  });
}

export async function flushPendingMutations(handler: (mutationId: string, payload: Record<string, unknown>) => Promise<boolean> | boolean) {
  const mutations = await listPendingMutations();
  for (const mutation of mutations) {
    if (mutation.status === 'ACKNOWLEDGED') {
      await clearPendingMutation(mutation.id);
      continue;
    }

    try {
      await handler(mutation.id, mutation.payload);
      await clearPendingMutation(mutation.id);
    } catch (error) {
      mutation.status = 'FAILED';
      mutation.last_error = error instanceof Error ? error.message : 'unknown';
      mutation.attempt_count += 1;
      await savePendingMutation(mutation);
    }
  }
}

export async function requestSyncFromServer(params: { userId: string; workspaceId: string; cursor?: string; conversations?: string[] }) {
  const query = new URLSearchParams({
    user_id: params.userId,
    workspace_id: params.workspaceId,
  });
  if (params.cursor) {
    query.set('cursor', params.cursor);
  }
  if (params.conversations && params.conversations.length > 0) {
    query.set('conversations', params.conversations.join(','));
  }

  const response = await fetch(`${API_BASE}/api/v1/sync?${query.toString()}`);
  if (!response.ok) {
    throw new Error(`Sync request failed: ${response.status}`);
  }
  return response.json() as Promise<Record<string, unknown>>;
}

export async function persistSyncState(state: Omit<SyncStateRecord, 'id'> & { id?: string }): Promise<SyncStateRecord> {
  const record: SyncStateRecord = {
    id: state.id ?? `${state.workspace_id}:${state.conversation_id ?? 'global'}`,
    workspace_id: state.workspace_id,
    conversation_id: state.conversation_id,
    last_sequence: state.last_sequence,
    last_event_id: state.last_event_id,
    last_sync_at: state.last_sync_at,
    sync_version: state.sync_version,
  };
  return saveSyncState(record);
}

export function hasSequenceGap(currentSequence: number, nextSequence: number): boolean {
  return nextSequence > currentSequence + 1;
}

export async function cacheServerMessage(message: CachedMessage): Promise<CachedMessage> {
  return saveMessage({
    ...message,
    conversation_id: message.conversation_id ?? message.channel_id ?? 'unknown',
    status: 'sent',
  });
}
