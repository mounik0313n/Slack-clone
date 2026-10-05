import { getAllRecords, putRecord } from '../database';

export type CachedNotification = {
  id: string;
  workspace_id: string;
  recipient_user_id: string;
  actor_user_id?: string | null;
  type: string;
  conversation_id?: string | null;
  message_id?: string | null;
  thread_id?: string | null;
  payload?: string | null;
  read_at?: string | null;
  created_at: string;
};

export async function saveNotification(record: CachedNotification): Promise<CachedNotification> {
  return putRecord<CachedNotification>('notifications', record);
}

export async function listNotificationsForUser(userId: string): Promise<CachedNotification[]> {
  const notifications = await getAllRecords<CachedNotification>('notifications');
  return notifications.filter((notification) => notification.recipient_user_id === userId);
}
