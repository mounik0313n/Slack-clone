import { getAllRecords, getRecordById, putRecord } from '../database';

export type SyncStateRecord = {
  id: string;
  workspace_id: string;
  conversation_id?: string;
  last_sequence: number;
  last_event_id?: string;
  last_sync_at: string;
  sync_version: number;
};

export async function saveSyncState(record: SyncStateRecord): Promise<SyncStateRecord> {
  return putRecord<SyncStateRecord>('sync_state', record);
}

export async function getSyncState(workspaceId: string, conversationId?: string): Promise<SyncStateRecord | null> {
  const records = await getAllRecords<SyncStateRecord>('sync_state');
  const match = records.find((record) => {
    if (record.workspace_id !== workspaceId) {
      return false;
    }
    if (!conversationId) {
      return !record.conversation_id;
    }
    return record.conversation_id === conversationId;
  });
  return match ?? null;
}

export async function readSyncState(id: string): Promise<SyncStateRecord | null> {
  return getRecordById<SyncStateRecord>('sync_state', id);
}
