import { deleteRecord, getAllRecords, getRecordById, putRecord } from '../database';

export type DraftRecord = {
  id: string;
  workspace_id: string;
  conversation_id: string;
  device_id: string;
  content: string;
  updated_at: string;
};

export function makeDraftId(workspaceId: string, conversationId: string, deviceId: string): string {
  return `${workspaceId}:${conversationId}:${deviceId}`;
}

export async function saveDraft(record: DraftRecord): Promise<DraftRecord> {
  return putRecord<DraftRecord>('drafts', record);
}

export async function readDraft(workspaceId: string, conversationId: string, deviceId: string): Promise<DraftRecord | null> {
  return getRecordById<DraftRecord>('drafts', makeDraftId(workspaceId, conversationId, deviceId));
}

export async function listDrafts(): Promise<DraftRecord[]> {
  return getAllRecords<DraftRecord>('drafts');
}

export async function clearDraft(workspaceId: string, conversationId: string, deviceId: string): Promise<void> {
  await deleteRecord('drafts', makeDraftId(workspaceId, conversationId, deviceId));
}
