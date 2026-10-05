import { deleteRecord, getAllRecords, getRecordById, putRecord } from '../database';

export type CachedMessage = {
  id: string;
  workspace_id: string;
  conversation_id: string;
  channel_id?: string;
  author_id: string;
  sequence: number;
  body: string;
  thread_id?: string | null;
  client_message_id?: string | null;
  created_at: string;
  updated_at?: string | null;
  status?: 'pending' | 'sent' | 'failed';
};

export async function saveMessage(record: CachedMessage): Promise<CachedMessage> {
  return putRecord<CachedMessage>('messages', record);
}

export async function readMessage(id: string): Promise<CachedMessage | null> {
  return getRecordById<CachedMessage>('messages', id);
}

export async function listMessagesForConversation(conversationId: string): Promise<CachedMessage[]> {
  const messages = await getAllRecords<CachedMessage>('messages');
  return messages.filter((message) => message.conversation_id === conversationId || message.channel_id === conversationId);
}

export async function deleteMessage(id: string): Promise<void> {
  await deleteRecord('messages', id);
}
