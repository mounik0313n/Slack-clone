export type OfflineStoreName =
  | 'conversations'
  | 'messages'
  | 'notifications'
  | 'drafts'
  | 'pending_mutations'
  | 'sync_state'
  | 'devices'
  | 'event_cache';

const DATABASE_NAME = 'slack-clone-offline';
const DATABASE_VERSION = 2;

const memoryStores = new Map<OfflineStoreName, Map<string, unknown>>();

function ensureMemoryStore(storeName: OfflineStoreName): Map<string, unknown> {
  if (!memoryStores.has(storeName)) {
    memoryStores.set(storeName, new Map());
  }
  return memoryStores.get(storeName) as Map<string, unknown>;
}

export async function openOfflineDatabase(): Promise<IDBDatabase> {
  if (typeof indexedDB === 'undefined') {
    return {
      transaction: () => ({
        objectStore: (storeName: string) => ({
          put: (value: { id: string }) => {
            const store = ensureMemoryStore(storeName as OfflineStoreName);
            store.set(String(value.id), value);
            return { onsuccess: null, onerror: null, result: value };
          },
          get: (id: string) => {
            const store = ensureMemoryStore(storeName as OfflineStoreName);
            const result = store.get(String(id));
            return { result, onsuccess: null, onerror: null };
          },
          getAll: () => {
            const store = ensureMemoryStore(storeName as OfflineStoreName);
            return { result: Array.from(store.values()), onsuccess: null, onerror: null };
          },
          delete: (id: string) => {
            const store = ensureMemoryStore(storeName as OfflineStoreName);
            store.delete(String(id));
            return { onsuccess: null, onerror: null, result: undefined };
          },
          clear: () => {
            const store = ensureMemoryStore(storeName as OfflineStoreName);
            store.clear();
            return { onsuccess: null, onerror: null, result: undefined };
          },
        }),
      }),
      close: () => undefined,
    } as unknown as IDBDatabase;
  }

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      const stores: OfflineStoreName[] = [
        'conversations',
        'messages',
        'notifications',
        'drafts',
        'pending_mutations',
        'sync_state',
        'devices',
        'event_cache',
      ];

      for (const storeName of stores) {
        if (!db.objectStoreNames.contains(storeName)) {
          const objectStore = db.createObjectStore(storeName, { keyPath: 'id' });
          if (storeName === 'messages') {
            objectStore.createIndex('workspace_id', 'workspace_id', { unique: false });
            objectStore.createIndex('conversation_id', 'conversation_id', { unique: false });
            objectStore.createIndex('sequence', 'sequence', { unique: false });
            objectStore.createIndex('created_at', 'created_at', { unique: false });
          }
          if (storeName === 'notifications') {
            objectStore.createIndex('workspace_id', 'workspace_id', { unique: false });
            objectStore.createIndex('recipient_user_id', 'recipient_user_id', { unique: false });
            objectStore.createIndex('created_at', 'created_at', { unique: false });
          }
          if (storeName === 'drafts') {
            objectStore.createIndex('workspace_id', 'workspace_id', { unique: false });
            objectStore.createIndex('conversation_id', 'conversation_id', { unique: false });
            objectStore.createIndex('device_id', 'device_id', { unique: false });
          }
          if (storeName === 'pending_mutations') {
            objectStore.createIndex('workspace_id', 'workspace_id', { unique: false });
            objectStore.createIndex('conversation_id', 'conversation_id', { unique: false });
            objectStore.createIndex('status', 'status', { unique: false });
            objectStore.createIndex('created_at', 'created_at', { unique: false });
          }
          if (storeName === 'sync_state') {
            objectStore.createIndex('workspace_id', 'workspace_id', { unique: false });
            objectStore.createIndex('conversation_id', 'conversation_id', { unique: false });
          }
        }
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Failed to open offline database'));
  });
}

export async function putRecord<T extends { id: string }>(storeName: OfflineStoreName, record: T): Promise<T> {
  if (typeof indexedDB === 'undefined') {
    ensureMemoryStore(storeName).set(String(record.id), record);
    return record;
  }

  const db = await openOfflineDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const request = store.put(record);
    request.onsuccess = () => resolve(record);
    request.onerror = () => reject(request.error ?? new Error(`Failed to save ${storeName}`));
    tx.oncomplete = () => db.close();
    tx.onerror = () => reject(tx.error ?? new Error(`Failed to commit ${storeName}`));
  });
}

export async function getRecordById<T>(storeName: OfflineStoreName, id: string): Promise<T | null> {
  if (typeof indexedDB === 'undefined') {
    const value = ensureMemoryStore(storeName).get(String(id)) as T | undefined;
    return value ?? null;
  }

  const db = await openOfflineDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).get(id);
    request.onsuccess = () => {
      db.close();
      resolve((request.result as T | undefined) ?? null);
    };
    request.onerror = () => {
      db.close();
      reject(request.error ?? new Error(`Could not fetch ${storeName}`));
    };
  });
}

export async function getAllRecords<T>(storeName: OfflineStoreName): Promise<T[]> {
  if (typeof indexedDB === 'undefined') {
    const values = ensureMemoryStore(storeName);
    return Array.from(values.values()) as T[];
  }

  const db = await openOfflineDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).getAll();
    request.onsuccess = () => {
      db.close();
      resolve((request.result as T[]) ?? []);
    };
    request.onerror = () => {
      db.close();
      reject(request.error ?? new Error(`Could not load ${storeName}`));
    };
  });
}

export async function deleteRecord(storeName: OfflineStoreName, id: string): Promise<void> {
  if (typeof indexedDB === 'undefined') {
    ensureMemoryStore(storeName).delete(String(id));
    return;
  }

  const db = await openOfflineDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const request = tx.objectStore(storeName).delete(id);
    request.onsuccess = () => {
      db.close();
      resolve();
    };
    request.onerror = () => {
      db.close();
      reject(request.error ?? new Error(`Could not delete ${storeName}`));
    };
  });
}

export async function clearStore(storeName: OfflineStoreName): Promise<void> {
  if (typeof indexedDB === 'undefined') {
    ensureMemoryStore(storeName).clear();
    return;
  }

  const db = await openOfflineDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const request = tx.objectStore(storeName).clear();
    request.onsuccess = () => {
      db.close();
      resolve();
    };
    request.onerror = () => {
      db.close();
      reject(request.error ?? new Error(`Could not clear ${storeName}`));
    };
  });
}
