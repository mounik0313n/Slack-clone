export type PendingMutation = {
  id: string;
  type: 'message' | 'read_state' | 'notification' | 'draft';
  payload: Record<string, unknown>;
  client_mutation_id: string;
  created_at: string;
  status: 'PENDING' | 'SENDING' | 'ACKNOWLEDGED' | 'FAILED' | 'CONFLICT';
  attempt_count: number;
  last_error?: string;
  user_id?: string;
  organization_id?: string;
  workspace_id?: string;
  conversation_id?: string;
  mutation_type?: string;
  updated_at?: string;
};

import { deleteRecord, getAllRecords, putRecord } from './database';

export async function getDeviceId(): Promise<string> {
  const key = 'slack_device_id';
  const stored = window.localStorage.getItem(key);
  if (stored) {
    return stored;
  }

  const generated = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `device-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  window.localStorage.setItem(key, generated);
  return generated;
}

export async function writeDraft(key: string, draft: string): Promise<void> {
  const [workspaceId, conversationId, deviceId] = key.split(':');
  const baseId = `${workspaceId ?? 'workspace'}:${conversationId ?? 'conversation'}:${deviceId ?? 'device'}`;
  const record = { id: baseId, workspace_id: workspaceId ?? 'workspace', conversation_id: conversationId ?? 'conversation', device_id: deviceId ?? 'device', content: draft, updated_at: new Date().toISOString() };
  await putRecord('drafts', record as Record<string, unknown> & { id: string });
}

export async function readDraft(key: string): Promise<string> {
  const [workspaceId, conversationId, deviceId] = key.split(':');
  const baseId = `${workspaceId ?? 'workspace'}:${conversationId ?? 'conversation'}:${deviceId ?? 'device'}`;
  const result = await (async () => {
    try {
      const records = await getAllRecords<Record<string, unknown>>('drafts');
      const match = records.find((record) => record.id === baseId);
      return match && typeof match.content === 'string' ? match.content : '';
    } catch {
      return window.localStorage.getItem(`draft:${key}`) ?? '';
    }
  })();
  return result;
}

export async function savePendingMutation(mutation: PendingMutation): Promise<void> {
  const nextMutation: PendingMutation = {
    ...mutation,
    status: mutation.status ?? 'PENDING',
    attempt_count: mutation.attempt_count ?? 0,
    updated_at: mutation.updated_at ?? new Date().toISOString(),
  };
  await putRecord<PendingMutation>('pending_mutations', nextMutation as PendingMutation & { id: string });
}

export async function listPendingMutations(): Promise<PendingMutation[]> {
  return getAllRecords<PendingMutation>('pending_mutations');
}

export async function clearPendingMutation(id: string): Promise<void> {
  await deleteRecord('pending_mutations', id);
}
