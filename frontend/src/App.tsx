import { useEffect, useMemo, useState } from 'react';

import { queueMutationForSync, requestSyncFromServer, resolveDeviceId, getConnectionState, flushPendingMutations } from './offline/syncManager';
import { readDraft, writeDraft } from './offline/indexedDb';
import { RealtimeClient, type RealtimeEvent } from './realtime/realtimeClient';

type Channel = {
  id: string;
  name: string;
  workspace_id: string;
  topic?: string | null;
  is_private: boolean;
  is_archived: boolean;
  created_at: string;
};

type MessageItem = {
  id: string;
  workspace_id: string;
  channel_id: string;
  author_id: string;
  sequence: number;
  body: string;
  thread_id?: string | null;
  client_message_id?: string | null;
  created_at: string;
  updated_at?: string | null;
};

type NotificationItem = {
  id: string;
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

const DEFAULT_USER_ID = 'user-1';
const DEFAULT_WORKSPACE_ID = 'ws-default';
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

function getRealtimeUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${window.location.hostname}:8000/ws?client_id=${DEFAULT_USER_ID}`;
}

function App() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>('');
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<'ONLINE' | 'OFFLINE' | 'RECONNECTING' | 'SYNCING' | 'CONNECTING'>(getConnectionState());
  const [deviceId, setDeviceId] = useState<string>('');

  const selectedChannel = useMemo(
    () => channels.find((channel) => channel.id === selectedChannelId) ?? channels[0] ?? null,
    [channels, selectedChannelId],
  );

  const loadChannels = async () => {
    const nextChannels = await fetchJson<Channel[]>(`${API_BASE}/api/v1/channels`);
    if (nextChannels.length === 0) {
      setChannels([]);
      setSelectedChannelId('');
      return;
    }
    setChannels(nextChannels);
    setSelectedChannelId((current) => current || nextChannels[0].id);
  };

  const loadMessages = async (channelId: string) => {
    try {
      const nextMessages = await fetchJson<MessageItem[]>(`${API_BASE}/api/v1/messages`);
      setMessages(nextMessages.filter((message) => message.channel_id === channelId));
    } catch {
      setMessages([]);
    }
  };

  const loadNotifications = async () => {
    try {
      const nextNotifications = await fetchJson<NotificationItem[]>(
        `${API_BASE}/api/v1/notifications?user_id=${DEFAULT_USER_ID}`,
      );
      setNotifications(nextNotifications);
    } catch {
      setNotifications([]);
    }
  };

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const nextDeviceId = await resolveDeviceId();
        setDeviceId(nextDeviceId);
        await Promise.all([loadChannels(), loadNotifications()]);
      } catch (loadError) {
        console.error(loadError);
        setError('Could not load workspace data from the API yet.');
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  useEffect(() => {
    const updateConnectionState = () => {
      const nextState = getConnectionState();
      setConnectionState(nextState === 'ONLINE' ? 'ONLINE' : nextState === 'CONNECTING' ? 'CONNECTING' : nextState === 'RECONNECTING' ? 'RECONNECTING' : nextState === 'SYNCING' ? 'SYNCING' : 'OFFLINE');
    };

    window.addEventListener('online', updateConnectionState);
    window.addEventListener('offline', updateConnectionState);

    return () => {
      window.removeEventListener('online', updateConnectionState);
      window.removeEventListener('offline', updateConnectionState);
    };
  }, []);

  useEffect(() => {
    if (connectionState !== 'ONLINE' || !selectedChannel) {
      return;
    }

    const flushQueuedMutations = async () => {
      setConnectionState('SYNCING');
      await flushPendingMutations(async (mutationId, payload) => {
        const record = payload as Record<string, unknown>;
        const channelId = typeof record.channel_id === 'string' ? record.channel_id : selectedChannel.id;
        const body = typeof record.body === 'string' ? record.body : '';
        const clientMessageId = typeof record.client_message_id === 'string' ? record.client_message_id : mutationId;

        if (!channelId || !body) {
          return false;
        }

        const response = await fetch(`${API_BASE}/api/v1/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: record.workspace_id ?? DEFAULT_WORKSPACE_ID,
            channel_id: channelId,
            author_id: DEFAULT_USER_ID,
            body,
            client_message_id: clientMessageId,
          }),
        });

        if (!response.ok) {
          throw new Error(`Queued message failed: ${response.status}`);
        }

        return true;
      });
      await loadMessages(selectedChannel.id);
      setConnectionState('ONLINE');
    };

    void flushQueuedMutations();
  }, [connectionState, selectedChannel?.id]);

  useEffect(() => {
    if (!selectedChannel) {
      return;
    }
    void readDraft(`${deviceId}:${selectedChannel.id}`).then((savedDraft) => setDraft(savedDraft));
  }, [deviceId, selectedChannel?.id]);

  useEffect(() => {
    if (!selectedChannel) {
      return;
    }
    void loadMessages(selectedChannel.id);
  }, [selectedChannel?.id]);

  useEffect(() => {
    if (!selectedChannel || !deviceId) {
      return;
    }
    void writeDraft(`${deviceId}:${selectedChannel.id}`, draft);
  }, [draft, deviceId, selectedChannel?.id]);

  useEffect(() => {
    const client = new RealtimeClient();
    client.connect(getRealtimeUrl());

    client.on('message.created', (event: RealtimeEvent) => {
      const payload = event.payload as Record<string, unknown>;
      const channelId = String(payload.channel_id ?? '');
      if (!channelId) {
        return;
      }

      const nextMessage = {
        id: String(payload.message_id ?? `live-${Date.now()}`),
        workspace_id: String(payload.workspace_id ?? DEFAULT_WORKSPACE_ID),
        channel_id: channelId,
        author_id: String(payload.author_id ?? DEFAULT_USER_ID),
        sequence: Number(payload.sequence ?? 0),
        body: String(payload.body ?? ''),
        thread_id: payload.thread_id ? String(payload.thread_id) : null,
        client_message_id: payload.client_message_id ? String(payload.client_message_id) : null,
        created_at: new Date().toISOString(),
      } satisfies MessageItem;

      setMessages((current) => {
        if (current.some((message) => message.id === nextMessage.id)) {
          return current;
        }
        if (channelId !== selectedChannel?.id) {
          return current;
        }
        return [...current, nextMessage];
      });
    });

    client.on('notification.created', (event: RealtimeEvent) => {
      const payload = event.payload as Record<string, unknown>;
      const nextItem = {
        id: String(payload.id ?? `notification-${Date.now()}`),
        recipient_user_id: String(payload.recipient_user_id ?? DEFAULT_USER_ID),
        actor_user_id: payload.actor_user_id ? String(payload.actor_user_id) : null,
        type: String(payload.type ?? 'MENTION'),
        conversation_id: payload.conversation_id ? String(payload.conversation_id) : null,
        message_id: payload.message_id ? String(payload.message_id) : null,
        thread_id: payload.thread_id ? String(payload.thread_id) : null,
        payload: payload.payload ? JSON.stringify(payload.payload) : null,
        created_at: new Date().toISOString(),
      } satisfies NotificationItem;

      setNotifications((current) => [nextItem, ...current]);
    });

    client.on('sync.required', async (event: RealtimeEvent) => {
      const payload = (event.payload ?? {}) as Record<string, unknown>;
      try {
        setConnectionState('SYNCING');
        const sync = await requestSyncFromServer({
          userId: DEFAULT_USER_ID,
          workspaceId: String(payload.workspace_id ?? DEFAULT_WORKSPACE_ID),
          cursor: typeof payload.cursor === 'string' ? payload.cursor : undefined,
          conversations: Array.isArray(payload.channels) ? payload.channels.map(String) : undefined,
        });
        const syncPayload = (sync as Record<string, unknown>);
        const nextMessages = Array.isArray(syncPayload.messages) ? (syncPayload.messages as Record<string, unknown>[]) : [];
        const nextNotifications = Array.isArray(syncPayload.notifications) ? (syncPayload.notifications as Record<string, unknown>[]) : [];

        setMessages((current) => {
          const merged = new Map(current.map((message) => [message.id, message]));
          for (const item of nextMessages) {
            const messageId = String(item.id ?? `sync-${Date.now()}-${Math.random()}`);
            const nextMessage = {
              id: messageId,
              workspace_id: String(item.workspace_id ?? DEFAULT_WORKSPACE_ID),
              channel_id: String(item.channel_id ?? selectedChannel?.id ?? ''),
              author_id: String(item.author_id ?? DEFAULT_USER_ID),
              sequence: Number(item.sequence ?? 0),
              body: String(item.body ?? ''),
              thread_id: item.thread_id ? String(item.thread_id) : null,
              client_message_id: item.client_message_id ? String(item.client_message_id) : null,
              created_at: typeof item.created_at === 'string' ? item.created_at : new Date().toISOString(),
            } satisfies MessageItem;
            merged.set(messageId, nextMessage);
          }
          return [...merged.values()];
        });

        setNotifications((current) => {
          const merged = new Map(current.map((item) => [item.id, item]));
          for (const item of nextNotifications) {
            const id = String(item.id ?? `notification-${Date.now()}-${Math.random()}`);
            merged.set(id, {
              id,
              recipient_user_id: String(item.recipient_user_id ?? DEFAULT_USER_ID),
              actor_user_id: item.actor_user_id ? String(item.actor_user_id) : null,
              type: String(item.type ?? 'MENTION'),
              conversation_id: item.conversation_id ? String(item.conversation_id) : null,
              message_id: item.message_id ? String(item.message_id) : null,
              thread_id: item.thread_id ? String(item.thread_id) : null,
              payload: item.payload ? JSON.stringify(item.payload) : null,
              created_at: typeof item.created_at === 'string' ? item.created_at : new Date().toISOString(),
            });
          }
          return [...merged.values()];
        });
      } catch {
        setError('Could not sync your workspace after reconnect.');
      } finally {
        setConnectionState(getConnectionState());
      }
    });

    client.on('sync.response', (event: RealtimeEvent) => {
      const payload = (event.payload ?? {}) as Record<string, unknown>;
      const syncPayload = payload as Record<string, unknown>;
      const messages = Array.isArray(syncPayload.messages) ? (syncPayload.messages as Record<string, unknown>[]) : [];
      const notifications = Array.isArray(syncPayload.notifications) ? (syncPayload.notifications as Record<string, unknown>[]) : [];
      if (messages.length > 0) {
        setMessages((current) => {
          const merged = new Map(current.map((item) => [item.id, item]));
          for (const item of messages) {
            const messageId = String(item.id ?? `sync-${Date.now()}-${Math.random()}`);
            merged.set(messageId, {
              id: messageId,
              workspace_id: String(item.workspace_id ?? DEFAULT_WORKSPACE_ID),
              channel_id: String(item.channel_id ?? selectedChannel?.id ?? ''),
              author_id: String(item.author_id ?? DEFAULT_USER_ID),
              sequence: Number(item.sequence ?? 0),
              body: String(item.body ?? ''),
              thread_id: item.thread_id ? String(item.thread_id) : null,
              client_message_id: item.client_message_id ? String(item.client_message_id) : null,
              created_at: typeof item.created_at === 'string' ? item.created_at : new Date().toISOString(),
            });
          }
          return [...merged.values()];
        });
      }
      if (notifications.length > 0) {
        setNotifications((current) => {
          const merged = new Map(current.map((item) => [item.id, item]));
          for (const item of notifications) {
            const id = String(item.id ?? `notification-${Date.now()}-${Math.random()}`);
            merged.set(id, {
              id,
              recipient_user_id: String(item.recipient_user_id ?? DEFAULT_USER_ID),
              actor_user_id: item.actor_user_id ? String(item.actor_user_id) : null,
              type: String(item.type ?? 'MENTION'),
              conversation_id: item.conversation_id ? String(item.conversation_id) : null,
              message_id: item.message_id ? String(item.message_id) : null,
              thread_id: item.thread_id ? String(item.thread_id) : null,
              payload: item.payload ? JSON.stringify(item.payload) : null,
              created_at: typeof item.created_at === 'string' ? item.created_at : new Date().toISOString(),
            });
          }
          return [...merged.values()];
        });
      }
    });

    const requestInitialSync = () => {
      client.requestSync({
        user_id: DEFAULT_USER_ID,
        workspace_id: DEFAULT_WORKSPACE_ID,
        cursor: '0',
        conversations: channels.map((channel) => channel.id),
      });
    };

    requestInitialSync();

    return () => client.disconnect();
  }, [selectedChannel?.id, channels]);

  const handleSend = async () => {
    if (!draft.trim() || !selectedChannel) {
      return;
    }

    const body = draft.trim();
    const clientMessageId = `client-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    if (!navigator.onLine) {
      const pendingEntry = {
        id: clientMessageId,
        type: 'message',
        client_mutation_id: clientMessageId,
        payload: {
          workspace_id: selectedChannel.workspace_id || DEFAULT_WORKSPACE_ID,
          channel_id: selectedChannel.id,
          author_id: DEFAULT_USER_ID,
          body,
          client_message_id: clientMessageId,
        },
        created_at: new Date().toISOString(),
        status: 'PENDING',
        attempt_count: 0,
      };
      await queueMutationForSync(pendingEntry);
      setMessages((current) => [
        {
          id: clientMessageId,
          workspace_id: selectedChannel.workspace_id || DEFAULT_WORKSPACE_ID,
          channel_id: selectedChannel.id,
          author_id: DEFAULT_USER_ID,
          sequence: 0,
          body,
          client_message_id: clientMessageId,
          created_at: new Date().toISOString(),
        },
        ...current,
      ]);
      setDraft('');
      await writeDraft(`${deviceId}:${selectedChannel.id}`, '');
      return;
    }

    await fetch(`${API_BASE}/api/v1/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: selectedChannel.workspace_id || DEFAULT_WORKSPACE_ID,
        channel_id: selectedChannel.id,
        author_id: DEFAULT_USER_ID,
        body,
        client_message_id: clientMessageId,
      }),
    });

    setDraft('');
    await writeDraft(`${deviceId}:${selectedChannel.id}`, '');
    await loadMessages(selectedChannel.id);
  };

  return (
    <div className="app-shell">
      <aside className="workspace-sidebar">
        <div className="brand">Slack Platform</div>
        <nav>
          <button type="button">Overview</button>
          <button type="button">Channels</button>
          <button type="button">Messages</button>
          <button type="button">AI</button>
          <button type="button">Admin</button>
        </nav>
      </aside>

      <aside className="channel-sidebar">
        <div className="panel-header">
          <span>Workspace</span>
          <small className="status-badge">{connectionState}</small>
        </div>
        <ul>
          {channels.map((channel) => (
            <li key={channel.id}>
              <button
                type="button"
                className={channel.id === selectedChannel?.id ? 'channel-button active' : 'channel-button'}
                onClick={() => setSelectedChannelId(channel.id)}
              >
                # {channel.name}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <main className="conversation-panel">
        <header className="conversation-header">
          {selectedChannel ? `# ${selectedChannel.name}` : 'Conversation'}
        </header>

        {error ? <div className="notice error">{error}</div> : null}

        <div className="messages">
          {loading ? (
            <div className="empty-state">Loading messages…</div>
          ) : messages.length === 0 ? (
            <div className="empty-state">No messages yet in this conversation.</div>
          ) : (
            messages.map((message) => (
              <div className="message-row" key={message.id}>
                <div className="avatar">{message.author_id.charAt(0).toUpperCase()}</div>
                <div>
                  <div className="meta">
                    <strong>{message.author_id}</strong>
                    <span>{new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  <p>{message.body}</p>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="composer">
          <textarea
            rows={3}
            placeholder={selectedChannel ? `Message #${selectedChannel.name}` : 'Select a channel'}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={!selectedChannel}
          />
          <button type="button" onClick={() => void handleSend()} disabled={!selectedChannel || !draft.trim()}>
            Send
          </button>
        </div>
      </main>

      <aside className="thread-panel">
        <div className="panel-header">Notifications</div>
        <div className="notification-list">
          {notifications.length === 0 ? (
            <div className="empty-state compact">No notifications yet.</div>
          ) : (
            notifications.map((notification) => (
              <div className="notification-card" key={notification.id}>
                <strong>{notification.type}</strong>
                <p>{notification.payload ?? 'New activity'}</p>
                <small>{new Date(notification.created_at).toLocaleString()}</small>
              </div>
            ))
          )}
        </div>
      </aside>
    </div>
  );
}

export default App;
