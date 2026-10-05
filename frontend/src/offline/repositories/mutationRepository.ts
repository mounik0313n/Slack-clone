import { deleteRecord, getAllRecords, getRecordById, putRecord } from '../database';
import type { OfflineMutation } from '../mutationQueue';

export async function savePendingMutation(mutation: OfflineMutation): Promise<OfflineMutation> {
  return putRecord<OfflineMutation>('pending_mutations', mutation);
}

export async function loadPendingMutations(): Promise<OfflineMutation[]> {
  return getAllRecords<OfflineMutation>('pending_mutations');
}

export async function loadPendingMutation(id: string): Promise<OfflineMutation | null> {
  return getRecordById<OfflineMutation>('pending_mutations', id);
}

export async function removePendingMutation(id: string): Promise<void> {
  await deleteRecord('pending_mutations', id);
}
