import { getAllRecords, putRecord } from '../database';

export type CachedConversation = {
  id: string;
  workspace_id: string;
  type: 'channel' | 'dm' | 'group';
  name?: string;
  created_at: string;
  updated_at?: string;
};

export async function saveConversation(record: CachedConversation): Promise<CachedConversation> {
  return putRecord<CachedConversation>('conversations', record);
}

export async function listConversations(): Promise<CachedConversation[]> {
  return getAllRecords<CachedConversation>('conversations');
}
