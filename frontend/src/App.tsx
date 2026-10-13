import { useEffect, useMemo, useState, useRef } from 'react';

import { queueMutationForSync, resolveDeviceId, flushPendingMutations } from './offline/syncManager';
import { readDraft, writeDraft } from './offline/indexedDb';
import { RealtimeClient, type RealtimeEvent, type ConnectionStatus } from './realtime/realtimeClient';

type UserProfile = {
  id: string;
  name: string;
  handle: string;
  role: string;
  avatarBg: string;
  status: 'online' | 'away' | 'offline';
  isBot?: boolean;
};

const TEAM_USERS: UserProfile[] = [
  { id: 'user-1', name: 'User One (You)', handle: '@user1', role: 'Fullstack Engineer', avatarBg: 'linear-gradient(135deg, #3b82f6, #6366f1)', status: 'online' },
  { id: 'user-2', name: 'Alex Rivera', handle: '@alex', role: 'Engineering Lead', avatarBg: 'linear-gradient(135deg, #10b981, #059669)', status: 'online' },
  { id: 'user-3', name: 'Sarah Chen', handle: '@sarah', role: 'Product Designer', avatarBg: 'linear-gradient(135deg, #ec4899, #8b5cf6)', status: 'online' },
  { id: 'user-4', name: 'Jordan Taylor', handle: '@jordan', role: 'DevOps & Infra', avatarBg: 'linear-gradient(135deg, #f59e0b, #d97706)', status: 'away' },
  { id: 'user-bot', name: 'Slackbot AI', handle: '@slackbot', role: 'AI Workspace Copilot', avatarBg: 'linear-gradient(135deg, #8b5cf6, #3b82f6)', status: 'online', isBot: true },
];

type Channel = {
  id: string;
  name: string;
  workspace_id: string;
  topic?: string | null;
  is_private: boolean;
  is_archived: boolean;
  created_at: string;
};

type DirectConversation = {
  id: string;
  user: UserProfile;
  unreadCount: number;
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

type ReactionItem = {
  id: string;
  workspace_id: string;
  channel_id: string;
  message_id: string;
  user_id: string;
  emoji: string;
};

type NotificationItem = {
  id: string;
  type: string;
  payload?: string | null;
  created_at: string;
};

type ActiveRailTab = 'channels' | 'dms' | 'activity' | 'ai' | 'canvas' | 'settings';

const DEFAULT_WORKSPACE_ID = 'ws-default';
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

function getRealtimeUrl(clientId: string) {
  if (import.meta.env.VITE_WS_URL) {
    const base = String(import.meta.env.VITE_WS_URL).replace(/\/+$/, '');
    return `${base}?client_id=${clientId}`;
  }
  if (API_BASE && API_BASE.startsWith('http')) {
    try {
      const url = new URL(API_BASE);
      const wsProto = url.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${wsProto}//${url.host}/ws?client_id=${clientId}`;
    } catch {
      // ignore
    }
  }
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const port = window.location.port ? `:${window.location.port}` : '';
  return `${protocol}://${window.location.hostname}${port}/ws?client_id=${clientId}`;
}

const EMOJI_LIST = ['👍', '❤️', '😂', '🚀', '🔥', '🎉', '💡', '🤖', '☕', '👀', '💯', '🙌'];

export default function App() {
  // Current active user (can be switched)
  const [currentUser, setCurrentUser] = useState<UserProfile>(TEAM_USERS[0]);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  // Layout & Rail Navigation
  const [activeRailTab, setActiveRailTab] = useState<ActiveRailTab>('channels');

  // Channels & DMs
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>('ch-general');
  const [selectedDmUser, setSelectedDmUser] = useState<UserProfile | null>(null);

  // Messages & Reactions
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [reactions, setReactions] = useState<ReactionItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);

  // Thread Drawer
  const [activeThreadMessage, setActiveThreadMessage] = useState<MessageItem | null>(null);
  const [threadReplies, setThreadReplies] = useState<MessageItem[]>([]);
  const [threadDraft, setThreadDraft] = useState('');

  // Modals & Popovers
  const [isCreateChannelOpen, setIsCreateChannelOpen] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');
  const [newChannelTopic, setNewChannelTopic] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isHuddleActive, setIsHuddleActive] = useState(false);

  // Connection & Sync
  const [connStatus, setConnStatus] = useState<ConnectionStatus>('CONNECTING');
  const [isSyncing, setIsSyncing] = useState(false);
  const [deviceId, setDeviceId] = useState('');
  const realtimeRef = useRef<RealtimeClient | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // AI Tab Chat State
  const [aiChatMessages, setAiChatMessages] = useState<Array<{ sender: 'user' | 'bot'; text: string; time: string }>>([
    {
      sender: 'bot',
      text: "👋 Hi! I'm Slackbot AI, your workspace intelligent copilot. I have full context on your Slack channels, team discussions, and Neon database architecture. How can I assist you today?",
      time: 'Just now',
    },
  ]);
  const [aiDraft, setAiDraft] = useState('');
  const [isAiGenerating, setIsAiGenerating] = useState(false);

  // Helper user lookup
  const userMap = useMemo(() => {
    const map = new Map<string, UserProfile>();
    TEAM_USERS.forEach((u) => map.set(u.id, u));
    return map;
  }, []);

  const getUser = (userId: string): UserProfile => {
    return userMap.get(userId) ?? {
      id: userId,
      name: userId,
      handle: `@${userId}`,
      role: 'Member',
      avatarBg: 'linear-gradient(135deg, #64748b, #475569)',
      status: 'offline',
    };
  };

  // Direct conversations list
  const dmList: DirectConversation[] = useMemo(() => {
    return TEAM_USERS.filter((u) => u.id !== currentUser.id).map((u) => ({
      id: `dm-${u.id}`,
      user: u,
      unreadCount: u.isBot ? 1 : 0,
    }));
  }, [currentUser.id]);

  const activeChannel = useMemo(
    () => channels.find((c) => c.id === selectedChannelId) ?? channels[0] ?? null,
    [channels, selectedChannelId],
  );

  const currentConversationId = selectedDmUser ? `dm-${selectedDmUser.id}` : (activeChannel?.id ?? 'ch-general');

  // Load Initial Data
  const loadWorkspaceData = async () => {
    try {
      setLoading(true);
      const [fetchedChannels, fetchedMessages, fetchedReactions] = await Promise.all([
        fetch(`${API_BASE}/api/v1/channels`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/api/v1/messages`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/api/v1/reactions`).then((r) => (r.ok ? r.json() : [])),
      ]);

      if (Array.isArray(fetchedChannels) && fetchedChannels.length > 0) {
        setChannels(fetchedChannels);
        if (!selectedChannelId) {
          setSelectedChannelId(fetchedChannels[0].id);
        }
      }
      if (Array.isArray(fetchedMessages)) {
        setMessages(fetchedMessages);
      }
      if (Array.isArray(fetchedReactions)) {
        setReactions(fetchedReactions);
      }
    } catch (err) {
      console.warn('Failed loading workspace data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Initialize Device & Workspace
  useEffect(() => {
    void resolveDeviceId().then((id) => setDeviceId(id));
    void loadWorkspaceData();
  }, []);

  // Connect Realtime WebSocket
  useEffect(() => {
    const client = new RealtimeClient();
    realtimeRef.current = client;

    const unsubStatus = client.onStatusChange((status) => {
      setConnStatus(status);
    });

    client.connect(getRealtimeUrl(currentUser.id));

    // Handle incoming messages
    client.on('message.created', (event: RealtimeEvent) => {
      const p = event.payload;
      const nextMsg: MessageItem = {
        id: String(p.message_id ?? `msg-${Date.now()}`),
        workspace_id: String(p.workspace_id ?? DEFAULT_WORKSPACE_ID),
        channel_id: String(p.channel_id ?? ''),
        author_id: String(p.author_id ?? currentUser.id),
        sequence: Number(p.sequence ?? 0),
        body: String(p.body ?? ''),
        thread_id: p.thread_id ? String(p.thread_id) : null,
        client_message_id: p.client_message_id ? String(p.client_message_id) : null,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => {
        if (prev.some((m) => m.id === nextMsg.id)) return prev;
        return [...prev, nextMsg];
      });

      if (activeThreadMessage && nextMsg.thread_id === activeThreadMessage.id) {
        setThreadReplies((prev) => [...prev, nextMsg]);
      }
    });

    // Handle reaction added
    client.on('reaction.created', (event: RealtimeEvent) => {
      const p = event.payload;
      const newRx: ReactionItem = {
        id: String(p.reaction_id ?? `rx-${Date.now()}`),
        workspace_id: String(p.workspace_id ?? DEFAULT_WORKSPACE_ID),
        channel_id: String(p.channel_id ?? ''),
        message_id: String(p.message_id ?? ''),
        user_id: String(p.user_id ?? ''),
        emoji: String(p.emoji ?? ''),
      };
      setReactions((prev) => {
        if (prev.some((r) => r.id === newRx.id || (r.message_id === newRx.message_id && r.user_id === newRx.user_id && r.emoji === newRx.emoji))) {
          return prev;
        }
        return [...prev, newRx];
      });
    });

    // Handle reaction deleted
    client.on('reaction.deleted', (event: RealtimeEvent) => {
      const p = event.payload;
      setReactions((prev) =>
        prev.filter((r) => !(r.message_id === p.message_id && r.user_id === p.user_id && r.emoji === p.emoji)),
      );
    });

    // Handle notifications
    client.on('notification.created', (event: RealtimeEvent) => {
      const p = event.payload;
      const notif: NotificationItem = {
        id: String(p.id ?? `notif-${Date.now()}`),
        type: String(p.type ?? 'ALERT'),
        payload: p.payload ? JSON.stringify(p.payload) : 'New workspace event',
        created_at: new Date().toISOString(),
      };
      setNotifications((prev) => [notif, ...prev]);
    });

    return () => {
      unsubStatus();
      client.disconnect();
    };
  }, [currentUser.id, activeThreadMessage?.id]);

  // Load Saved Draft on Channel / DM Change
  useEffect(() => {
    if (!deviceId) return;
    const draftKey = `${deviceId}:${currentConversationId}`;
    void readDraft(draftKey).then((saved) => setDraft(saved || ''));
  }, [deviceId, currentConversationId]);

  // Save Draft
  useEffect(() => {
    if (!deviceId) return;
    const draftKey = `${deviceId}:${currentConversationId}`;
    void writeDraft(draftKey, draft);
  }, [draft, deviceId, currentConversationId]);

  // Scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, selectedChannelId, selectedDmUser]);

  // Filter messages for current view
  const conversationMessages = useMemo(() => {
    return messages.filter((m) => {
      if (m.thread_id) return false; // don't show thread replies in main channel stream
      return m.channel_id === currentConversationId;
    });
  }, [messages, currentConversationId]);

  // Update thread replies when activeThreadMessage changes
  useEffect(() => {
    if (!activeThreadMessage) {
      setThreadReplies([]);
      return;
    }
    const replies = messages.filter((m) => m.thread_id === activeThreadMessage.id);
    setThreadReplies(replies);
  }, [activeThreadMessage, messages]);

  // Send Message in Main Stream
  const handleSendMessage = async () => {
    if (!draft.trim()) return;
    const text = draft.trim();
    const clientMessageId = `msg-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`;
    setDraft('');
    if (deviceId) {
      void writeDraft(`${deviceId}:${currentConversationId}`, '');
    }

    const optimisticMessage: MessageItem = {
      id: clientMessageId,
      workspace_id: DEFAULT_WORKSPACE_ID,
      channel_id: currentConversationId,
      author_id: currentUser.id,
      sequence: messages.length + 1,
      body: text,
      client_message_id: clientMessageId,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticMessage]);

    // If offline, queue mutation
    if (connStatus === 'OFFLINE' || !navigator.onLine) {
      await queueMutationForSync({
        id: clientMessageId,
        type: 'message',
        client_mutation_id: clientMessageId,
        payload: {
          workspace_id: DEFAULT_WORKSPACE_ID,
          channel_id: currentConversationId,
          author_id: currentUser.id,
          body: text,
          client_message_id: clientMessageId,
        },
        created_at: new Date().toISOString(),
        user_id: currentUser.id,
      });
      return;
    }

    try {
      setIsSyncing(true);
      await fetch(`${API_BASE}/api/v1/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: DEFAULT_WORKSPACE_ID,
          channel_id: currentConversationId,
          author_id: currentUser.id,
          body: text,
          client_message_id: clientMessageId,
        }),
      });

      // If chatting with Slackbot DM, simulate AI reply
      if (selectedDmUser?.isBot) {
        setTimeout(() => {
          handleBotReply(text, currentConversationId);
        }, 1000);
      }
    } catch (err) {
      console.warn('Send message error:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  // Send Thread Reply
  const handleSendThreadReply = async () => {
    if (!threadDraft.trim() || !activeThreadMessage) return;
    const text = threadDraft.trim();
    const clientMessageId = `th-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`;
    setThreadDraft('');

    const optimisticReply: MessageItem = {
      id: clientMessageId,
      workspace_id: DEFAULT_WORKSPACE_ID,
      channel_id: activeThreadMessage.channel_id,
      author_id: currentUser.id,
      sequence: messages.length + 1,
      body: text,
      thread_id: activeThreadMessage.id,
      client_message_id: clientMessageId,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticReply]);
    setThreadReplies((prev) => [...prev, optimisticReply]);

    try {
      await fetch(`${API_BASE}/api/v1/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: DEFAULT_WORKSPACE_ID,
          channel_id: activeThreadMessage.channel_id,
          author_id: currentUser.id,
          body: text,
          thread_id: activeThreadMessage.id,
          client_message_id: clientMessageId,
        }),
      });
    } catch (err) {
      console.warn('Failed to send thread reply:', err);
    }
  };

  // Toggle Reaction on a message
  const handleToggleReaction = async (messageId: string, emoji: string) => {
    const existing = reactions.find(
      (r) => r.message_id === messageId && r.user_id === currentUser.id && r.emoji === emoji,
    );

    if (existing) {
      // Remove reaction
      setReactions((prev) => prev.filter((r) => r.id !== existing.id));
      try {
        await fetch(`${API_BASE}/api/v1/reactions/${messageId}/${currentUser.id}/${encodeURIComponent(emoji)}`, {
          method: 'DELETE',
        });
      } catch (err) {
        console.warn('Failed to delete reaction:', err);
      }
    } else {
      // Add reaction
      const newRx: ReactionItem = {
        id: `rx-${messageId}-${currentUser.id}-${emoji}`,
        workspace_id: DEFAULT_WORKSPACE_ID,
        channel_id: currentConversationId,
        message_id: messageId,
        user_id: currentUser.id,
        emoji,
      };
      setReactions((prev) => [...prev, newRx]);
      try {
        await fetch(`${API_BASE}/api/v1/reactions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: DEFAULT_WORKSPACE_ID,
            channel_id: currentConversationId,
            message_id: messageId,
            user_id: currentUser.id,
            emoji,
          }),
        });
      } catch (err) {
        console.warn('Failed to add reaction:', err);
      }
    }
  };

  // Bot Smart Reply Simulation for DMs
  const handleBotReply = async (userText: string, channelId: string) => {
    let reply = `🤖 I received your message: "${userText}". All systems are operational on Render & Neon PostgreSQL!`;
    const lower = userText.toLowerCase();
    if (lower.includes('hello') || lower.includes('hi')) {
      reply = `👋 Hey ${currentUser.name}! I'm Slackbot. How can I help you today? Ask me about database migrations, branch features, or team updates!`;
    } else if (lower.includes('neon') || lower.includes('db') || lower.includes('database')) {
      reply = `⚡ Neon PostgreSQL is currently connected with SSL enabled on endpoint \`ep-withered-voice-b3h40y3k\`. Lakebase pooling and schema migrations are fully up to date!`;
    } else if (lower.includes('status') || lower.includes('health')) {
      reply = `🟢 All systems healthy! WebSocket gateway response time: ~28ms. Render backend: Live. Database: Connected.`;
    }

    const botMessage: MessageItem = {
      id: `bot-${Date.now()}`,
      workspace_id: DEFAULT_WORKSPACE_ID,
      channel_id: channelId,
      author_id: 'user-bot',
      sequence: messages.length + 2,
      body: reply,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, botMessage]);

    try {
      await fetch(`${API_BASE}/api/v1/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: DEFAULT_WORKSPACE_ID,
          channel_id: channelId,
          author_id: 'user-bot',
          body: reply,
          client_message_id: botMessage.id,
        }),
      });
    } catch {
      // ignore
    }
  };

  // AI Tab Chat Send
  const handleSendAiPrompt = (promptText: string) => {
    const text = promptText.trim();
    if (!text) return;
    setAiDraft('');
    const userMsg = { sender: 'user' as const, text, time: 'Just now' };
    setAiChatMessages((prev) => [...prev, userMsg]);
    setIsAiGenerating(true);

    setTimeout(() => {
      let botResponse = `🤖 Here is what I found regarding **"${text}"**:\n\n`;
      const lower = text.toLowerCase();
      if (lower.includes('summarize') || lower.includes('unread')) {
        botResponse += `• **#general**: Team celebrated the live deployment on Render & Neon DB.\n• **#engineering**: Branching migrations applied with sub-35ms WebSocket latency.\n• **#random**: Team coffee break & Friday board game night planned!\n\nAll threads are up to date and sync is active.`;
      } else if (lower.includes('roadmap') || lower.includes('release')) {
        botResponse += `🎉 **Slack Clone Q4 Release Notes**:\n- Realtime WebSocket gateway with automatic reconnection.\n- Neon Lakebase PostgreSQL persistent storage with SSL.\n- Thread drawers, emoji reactions, and direct messaging.\n- Offline IndexedDB draft & mutation queue.`;
      } else if (lower.includes('neon') || lower.includes('branch')) {
        botResponse += `🌿 **Neon Database Branching** creates instant, isolated copies of your Postgres database in seconds using Copy-on-Write storage. You can test schema changes or run staging environments without affecting production data!`;
      } else {
        botResponse += `Everything is functioning smoothly! You have 4 active channels, 5 teammates online, and 0 unresolved errors. Let me know if you need code snippets or draft announcements!`;
      }

      setAiChatMessages((prev) => [...prev, { sender: 'bot', text: botResponse, time: 'Just now' }]);
      setIsAiGenerating(false);
    }, 1200);
  };

  // Handle Channel Creation
  const handleCreateChannel = async () => {
    if (!newChannelName.trim()) return;
    const cleanName = newChannelName.trim().toLowerCase().replace(/\s+/g, '-');
    try {
      const response = await fetch(`${API_BASE}/api/v1/channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: DEFAULT_WORKSPACE_ID,
          name: cleanName,
          topic: newChannelTopic.trim() || `Channel for #${cleanName}`,
          is_private: false,
        }),
      });
      if (response.ok) {
        const created = (await response.json()) as Channel;
        setChannels((prev) => [...prev, created]);
        setSelectedChannelId(created.id);
        setSelectedDmUser(null);
        setActiveRailTab('channels');
        setNewChannelName('');
        setNewChannelTopic('');
        setIsCreateChannelOpen(false);
      }
    } catch (err) {
      console.warn('Failed creating channel:', err);
    }
  };

  // Keyboard shortcut Ctrl+K for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
      if (e.key === 'Escape') {
        setIsSearchOpen(false);
        setIsCreateChannelOpen(false);
        setIsUserMenuOpen(false);
        setShowEmojiPicker(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Filtered search items
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    const matchedChannels = channels
      .filter((c) => c.name.toLowerCase().includes(q))
      .map((c) => ({ type: 'channel' as const, id: c.id, title: `#${c.name}`, subtitle: c.topic || 'Channel' }));
    const matchedUsers = TEAM_USERS
      .filter((u) => u.name.toLowerCase().includes(q) || u.handle.toLowerCase().includes(q))
      .map((u) => ({ type: 'user' as const, id: u.id, title: u.name, subtitle: `${u.handle} • ${u.role}` }));
    const matchedMsgs = messages
      .filter((m) => m.body.toLowerCase().includes(q))
      .slice(0, 5)
      .map((m) => ({ type: 'message' as const, id: m.id, title: m.body, subtitle: `in #${channels.find((c) => c.id === m.channel_id)?.name ?? 'chat'}` }));
    return [...matchedChannels, ...matchedUsers, ...matchedMsgs];
  }, [searchQuery, channels, messages]);

  // Group reactions by emoji for a message
  const getGroupedReactions = (messageId: string) => {
    const msgRx = reactions.filter((r) => r.message_id === messageId);
    const groups = new Map<string, { count: number; reactedByMe: boolean }>();
    msgRx.forEach((r) => {
      const existing = groups.get(r.emoji) ?? { count: 0, reactedByMe: false };
      groups.set(r.emoji, {
        count: existing.count + 1,
        reactedByMe: existing.reactedByMe || r.user_id === currentUser.id,
      });
    });
    return Array.from(groups.entries()).map(([emoji, data]) => ({
      emoji,
      count: data.count,
      reactedByMe: data.reactedByMe,
    }));
  };

  // Count thread replies
  const getThreadRepliesCount = (messageId: string) => {
    return messages.filter((m) => m.thread_id === messageId).length;
  };

  return (
    <div className="app-container">
      {/* Top Header / Search */}
      <header className="top-header">
        <div className="top-header-left">
          <div className="workspace-badge" onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}>
            <div className="workspace-icon-box">AC</div>
            <span>Acme Corp</span>
            <small style={{ opacity: 0.6 }}>▾</small>
          </div>
        </div>

        <button className="top-search-btn" onClick={() => setIsSearchOpen(true)}>
          <span>🔍</span>
          <span>Search Acme Corp messages, channels, and team...</span>
          <span className="search-shortcut">Ctrl K</span>
        </button>

        <div className="top-header-right">
          {/* User Profile Pill */}
          <div className="user-pill" onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}>
            <div className="user-avatar-small" style={{ background: currentUser.avatarBg }}>
              {currentUser.name.charAt(0)}
              <span className={`presence-dot ${currentUser.status}`} />
            </div>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{currentUser.name.split(' ')[0]}</span>
            <span style={{ fontSize: '0.7rem', opacity: 0.6 }}>▾</span>
          </div>
        </div>
      </header>

      {/* User Switcher Dropdown */}
      {isUserMenuOpen && (
        <div className="user-menu-popover">
          <div style={{ padding: '4px 6px 8px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>Switch Active Teammate</div>
            <small style={{ color: 'var(--text-muted)' }}>Test multi-user chat, reactions & threads</small>
          </div>
          {TEAM_USERS.map((user) => (
            <button
              key={user.id}
              className={`user-option-btn ${user.id === currentUser.id ? 'active' : ''}`}
              onClick={() => {
                setCurrentUser(user);
                setIsUserMenuOpen(false);
              }}
            >
              <div className="user-avatar-small" style={{ background: user.avatarBg }}>
                {user.name.charAt(0)}
                <span className={`presence-dot ${user.status}`} />
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{user.name}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{user.role}</div>
              </div>
              {user.id === currentUser.id && <span style={{ color: '#38bdf8', fontSize: '0.8rem' }}>✓</span>}
            </button>
          ))}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Backend: Render + Neon DB</span>
            <span className={`conn-pulse ${connStatus.toLowerCase()}`} title={`Status: ${connStatus}`} />
          </div>
        </div>
      )}

      {/* Main Workspace Area */}
      <div className="main-workspace">
        {/* 1. Left Activity Rail */}
        <nav className="activity-rail">
          <button
            className={`rail-btn ${activeRailTab === 'channels' ? 'active' : ''}`}
            onClick={() => {
              setActiveRailTab('channels');
              setSelectedDmUser(null);
            }}
            title="Home / Channels"
          >
            <span className="rail-icon">🏠</span>
            <span className="rail-label">Home</span>
          </button>

          <button
            className={`rail-btn ${activeRailTab === 'dms' ? 'active' : ''}`}
            onClick={() => setActiveRailTab('dms')}
            title="Direct Messages"
          >
            <span className="rail-icon">💬</span>
            <span className="rail-label">DMs</span>
          </button>

          <button
            className={`rail-btn ${activeRailTab === 'activity' ? 'active' : ''}`}
            onClick={() => setActiveRailTab('activity')}
            title="Activity & Notifications"
          >
            <span className="rail-icon">🔔</span>
            <span className="rail-label">Activity</span>
            {notifications.length > 0 && <span className="rail-badge">{notifications.length}</span>}
          </button>

          <button
            className={`rail-btn ${activeRailTab === 'ai' ? 'active' : ''}`}
            onClick={() => setActiveRailTab('ai')}
            title="Slackbot AI Assistant"
          >
            <span className="rail-icon">🤖</span>
            <span className="rail-label">AI Copilot</span>
          </button>

          <button
            className={`rail-btn ${activeRailTab === 'canvas' ? 'active' : ''}`}
            onClick={() => setActiveRailTab('canvas')}
            title="Canvas & Files"
          >
            <span className="rail-icon">📋</span>
            <span className="rail-label">Canvas</span>
          </button>

          <div className="rail-bottom">
            {/* Live Connection Pulse Indicator */}
            <button
              className="rail-conn-indicator"
              onClick={() => void loadWorkspaceData()}
              title={`Connection: ${connStatus} • Click to reload`}
            >
              <span className={`conn-pulse ${connStatus.toLowerCase()}`} />
            </button>

            {/* Current User Avatar */}
            <div
              className="user-avatar-small"
              style={{ background: currentUser.avatarBg, cursor: 'pointer', width: '32px', height: '32px' }}
              onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
              title={`${currentUser.name} (${currentUser.role})`}
            >
              {currentUser.name.charAt(0)}
              <span className={`presence-dot ${currentUser.status}`} />
            </div>
          </div>
        </nav>

        {/* 2. Channels & Direct Messages Sidebar */}
        <aside className="channels-sidebar">
          <div className="sidebar-header">
            <span className="sidebar-header-title">
              Acme Corp
              <small style={{ color: 'var(--text-dim)', fontSize: '0.8rem', fontWeight: 400 }}>#workspace</small>
            </span>
            <button
              className="compose-icon-btn"
              onClick={() => setIsCreateChannelOpen(true)}
              title="Create new channel"
            >
              ✏️
            </button>
          </div>

          <div className="sidebar-scroll-area">
            {/* Channels Section */}
            <div>
              <div className="sidebar-section-header">
                <span>Channels</span>
                <button
                  className="sidebar-section-btn"
                  onClick={() => setIsCreateChannelOpen(true)}
                  title="Add Channel"
                >
                  +
                </button>
              </div>
              <ul className="sidebar-nav-list">
                {channels.map((ch) => (
                  <li key={ch.id}>
                    <button
                      className={`sidebar-nav-item ${!selectedDmUser && activeChannel?.id === ch.id && activeRailTab === 'channels' ? 'active' : ''}`}
                      onClick={() => {
                        setSelectedChannelId(ch.id);
                        setSelectedDmUser(null);
                        setActiveRailTab('channels');
                      }}
                    >
                      <span className="sidebar-item-prefix">{ch.is_private ? '🔒' : '#'}</span>
                      <span className="sidebar-item-name">{ch.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            {/* Direct Messages Section */}
            <div>
              <div className="sidebar-section-header">
                <span>Direct Messages</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{dmList.length}</span>
              </div>
              <ul className="sidebar-nav-list">
                {dmList.map((dm) => (
                  <li key={dm.id}>
                    <button
                      className={`sidebar-nav-item ${selectedDmUser?.id === dm.user.id ? 'active' : ''}`}
                      onClick={() => {
                        setSelectedDmUser(dm.user);
                        setActiveRailTab('dms');
                      }}
                    >
                      <div className="dm-avatar-mini" style={{ background: dm.user.avatarBg }}>
                        {dm.user.name.charAt(0)}
                        <span className={`presence-dot ${dm.user.status}`} />
                      </div>
                      <span className="sidebar-item-name">{dm.user.name}</span>
                      {dm.user.isBot && <span className="bot-badge">AI</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            {/* Quick Tips Box */}
            <div style={{ marginTop: 'auto', padding: '12px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#38bdf8', marginBottom: '4px' }}>⚡ Slack Cloud Status</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', lineHeight: 1.4 }}>
                Neon PostgreSQL & Render Live. Press <strong>Ctrl+K</strong> to search or switch users at top right.
              </div>
            </div>
          </div>
        </aside>

        {/* 3. Main Center Panel */}
        {activeRailTab === 'ai' ? (
          /* Dedicated Slackbot AI Copilot View */
          <div className="ai-view-container">
            <div className="ai-hero-header">
              <div className="ai-hero-icon">🤖</div>
              <h1 className="ai-hero-title">Slackbot AI Copilot</h1>
              <p className="ai-hero-sub">
                Ask questions about Acme Corp projects, summarize channel activities, draft announcements, or inspect your Neon database schema.
              </p>
            </div>

            {/* Suggested Prompt Chips */}
            <div className="ai-prompt-grid">
              <div className="ai-prompt-card" onClick={() => handleSendAiPrompt('Summarize unread messages in #general and #engineering')}>
                <strong>📋 Summarize Channels</strong>
                <p>Catch up on recent updates across all channels</p>
              </div>
              <div className="ai-prompt-card" onClick={() => handleSendAiPrompt('Draft a release note for our new Slack clone update')}>
                <strong>✍️ Draft Release Note</strong>
                <p>Generate announcement for the team</p>
              </div>
              <div className="ai-prompt-card" onClick={() => handleSendAiPrompt('How does Neon database branching work?')}>
                <strong>🌿 Explain Neon Branching</strong>
                <p>Understand instant branching & migration workflows</p>
              </div>
              <div className="ai-prompt-card" onClick={() => handleSendAiPrompt('Generate a code review checklist for frontend PRs')}>
                <strong>✅ Code Review Checklist</strong>
                <p>Best practices for TypeScript & WebSocket apps</p>
              </div>
            </div>

            {/* Conversational Stream */}
            <div style={{ flex: 1, maxWidth: '800px', margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {aiChatMessages.map((msg, idx) => (
                <div key={idx} className="message-item" style={{ background: msg.sender === 'user' ? 'rgba(56, 189, 248, 0.08)' : 'rgba(255, 255, 255, 0.03)' }}>
                  <div
                    className="author-avatar"
                    style={{ background: msg.sender === 'user' ? currentUser.avatarBg : 'linear-gradient(135deg, #8b5cf6, #3b82f6)' }}
                  >
                    {msg.sender === 'user' ? currentUser.name.charAt(0) : '🤖'}
                  </div>
                  <div className="message-body-wrap">
                    <div className="message-meta-row">
                      <span className="author-name">{msg.sender === 'user' ? currentUser.name : 'Slackbot AI'}</span>
                      {msg.sender === 'bot' && <span className="bot-badge">AI COPILOT</span>}
                      <span className="message-timestamp">{msg.time}</span>
                    </div>
                    <div className="message-text" style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
                  </div>
                </div>
              ))}
              {isAiGenerating && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#c084fc', fontSize: '0.85rem', padding: '8px 16px' }}>
                  <span>🤖 Slackbot is thinking...</span>
                </div>
              )}
            </div>

            {/* AI Input Composer */}
            <div style={{ maxWidth: '800px', margin: '16px auto 0', width: '100%' }}>
              <div className="composer-border-wrap">
                <textarea
                  className="composer-textarea"
                  placeholder="Ask Slackbot AI anything about your project or team..."
                  value={aiDraft}
                  onChange={(e) => setAiDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendAiPrompt(aiDraft);
                    }
                  }}
                />
                <div className="composer-footer">
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Powered by Neon AI Gateway & Knowledge Base</span>
                  <button
                    className="composer-send-btn"
                    onClick={() => handleSendAiPrompt(aiDraft)}
                    disabled={!aiDraft.trim() || isAiGenerating}
                  >
                    Ask AI ➔
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : activeRailTab === 'canvas' ? (
          /* Canvas & Notes View */
          <div style={{ flex: 1, padding: '32px', overflowY: 'auto' }}>
            <h1 style={{ fontSize: '1.6rem', fontWeight: 700, marginBottom: '8px' }}>📋 Workspace Canvas & Notes</h1>
            <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>Collaborative living documents, architectural specs, and team notes.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: '12px', padding: '20px' }}>
                <h3 style={{ fontSize: '1.1rem', marginBottom: '8px', color: '#38bdf8' }}>🚀 Deployment Architecture</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  • <strong>Frontend:</strong> Vercel (Vite + React 19)<br />
                  • <strong>Backend:</strong> Render (FastAPI + Asyncpg)<br />
                  • <strong>Database:</strong> Neon Lakebase PostgreSQL (SSL enabled)<br />
                  • <strong>Realtime:</strong> WebSockets Gateway + Outbox Event Sync
                </p>
              </div>
              <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: '12px', padding: '20px' }}>
                <h3 style={{ fontSize: '1.1rem', marginBottom: '8px', color: '#2bac76' }}>📌 Sprint Objectives</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  1. Real-time channels, direct messages & threads.<br />
                  2. Dynamic emoji reaction counters.<br />
                  3. Offline draft caching via IndexedDB.<br />
                  4. Global quick search modal (Ctrl+K).
                </p>
              </div>
            </div>
          </div>
        ) : (
          /* Main Conversation Panel (Channels & DMs) */
          <main className="conversation-panel">
            {/* Conversation Header */}
            <header className="channel-header">
              <div className="channel-header-info">
                <div className="channel-title-row">
                  <span className="channel-title">
                    {selectedDmUser ? (
                      <>💬 {selectedDmUser.name}</>
                    ) : (
                      <>{activeChannel?.is_private ? '🔒' : '#'} {activeChannel?.name ?? 'general'}</>
                    )}
                  </span>
                  <button className="channel-star-btn" title="Star conversation">⭐</button>
                  {selectedDmUser?.isBot && <span className="bot-badge">AI BOT</span>}
                </div>
                <div className="channel-topic">
                  {selectedDmUser
                    ? `${selectedDmUser.handle} • ${selectedDmUser.role}`
                    : (activeChannel?.topic || 'Welcome to this channel!')}
                </div>
              </div>

              <div className="channel-header-actions">
                <button
                  className="huddle-btn"
                  onClick={() => setIsHuddleActive(!isHuddleActive)}
                  title="Toggle voice huddle"
                >
                  <span>{isHuddleActive ? '🔊 Leave Huddle' : '🎧 Start Huddle'}</span>
                </button>

                <div className="member-stack-btn" title="View conversation members">
                  <span>👥 {selectedDmUser ? '2 members' : `${TEAM_USERS.length} members`}</span>
                </div>
              </div>
            </header>

            {/* Messages Scroll Area */}
            <div className="messages-container">
              {/* Channel Welcome Hero Banner */}
              <div className="channel-welcome-banner">
                <div className="channel-welcome-icon">
                  {selectedDmUser ? selectedDmUser.name.charAt(0) : '#'}
                </div>
                <h2 className="channel-welcome-title">
                  {selectedDmUser
                    ? `This is the start of your direct conversation with ${selectedDmUser.name}`
                    : `Welcome to #${activeChannel?.name ?? 'channel'}!`}
                </h2>
                <p className="channel-welcome-desc">
                  {selectedDmUser
                    ? `This is a private space just between you and ${selectedDmUser.name}. Say hello or share project updates!`
                    : (activeChannel?.topic || 'This is the start of this channel. Discuss, collaborate, and share ideas here.')}
                </p>
              </div>

              {loading ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  Loading conversation messages...
                </div>
              ) : conversationMessages.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                  No messages yet. Send a message below to kick off the conversation!
                </div>
              ) : (
                conversationMessages.map((msg) => {
                  const author = getUser(msg.author_id);
                  const msgReactions = getGroupedReactions(msg.id);
                  const threadCount = getThreadRepliesCount(msg.id);
                  const isAuthorBot = author.isBot || msg.author_id === 'user-bot';

                  return (
                    <div className="message-item" key={msg.id}>
                      <div className="author-avatar" style={{ background: author.avatarBg }}>
                        {author.name.charAt(0)}
                      </div>

                      <div className="message-body-wrap">
                        <div className="message-meta-row">
                          <span className="author-name">{author.name}</span>
                          {isAuthorBot && <span className="bot-badge">BOT</span>}
                          <span className="message-timestamp">
                            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>

                        <div className="message-text">{msg.body}</div>

                        {/* Reactions Row */}
                        {msgReactions.length > 0 && (
                          <div className="reactions-row">
                            {msgReactions.map((rx) => (
                              <button
                                key={rx.emoji}
                                className={`reaction-pill ${rx.reactedByMe ? 'reacted' : ''}`}
                                onClick={() => void handleToggleReaction(msg.id, rx.emoji)}
                                title={rx.reactedByMe ? 'Remove reaction' : 'Add reaction'}
                              >
                                <span>{rx.emoji}</span>
                                <span className="reaction-count">{rx.count}</span>
                              </button>
                            ))}
                          </div>
                        )}

                        {/* Thread Replies Indicator Link */}
                        {threadCount > 0 && (
                          <button
                            className="thread-indicator"
                            onClick={() => setActiveThreadMessage(msg)}
                          >
                            <span>💬</span>
                            <span>{threadCount} {threadCount === 1 ? 'reply' : 'replies'}</span>
                            <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>• View thread</span>
                          </button>
                        )}
                      </div>

                      {/* Floating Message Action Bar */}
                      <div className="message-hover-toolbar">
                        {['👍', '❤️', '🚀', '😂'].map((emoji) => (
                          <button
                            key={emoji}
                            className="toolbar-btn"
                            onClick={() => void handleToggleReaction(msg.id, emoji)}
                            title={`React ${emoji}`}
                          >
                            {emoji}
                          </button>
                        ))}
                        <button
                          className="toolbar-btn"
                          onClick={() => setActiveThreadMessage(msg)}
                          title="Reply in thread"
                        >
                          💬
                        </button>
                        <button
                          className="toolbar-btn"
                          onClick={() => {
                            void navigator.clipboard?.writeText(msg.body);
                          }}
                          title="Copy text"
                        >
                          📋
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* 4. Rich Message Composer */}
            <div className="composer-box">
              <div className="composer-border-wrap">
                {/* Formatting Toolbar */}
                <div className="composer-toolbar">
                  <button className="comp-tool-btn" onClick={() => setDraft((d) => `**${d}**`)} title="Bold">
                    <strong>B</strong>
                  </button>
                  <button className="comp-tool-btn" onClick={() => setDraft((d) => `*${d}*`)} title="Italic">
                    <em>I</em>
                  </button>
                  <button className="comp-tool-btn" onClick={() => setDraft((d) => `\`${d}\``)} title="Inline Code">
                    &lt;/&gt;
                  </button>
                  <div className="comp-tool-divider" />
                  <button className="comp-tool-btn" onClick={() => setDraft((d) => `${d}\n> `)} title="Quote">
                    ”
                  </button>
                  <button className="comp-tool-btn" onClick={() => setDraft((d) => `${d}\n- `)} title="Bulleted List">
                    •
                  </button>
                  <div className="comp-tool-divider" />
                  <button
                    className="comp-tool-btn"
                    onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                    title="Insert Emoji"
                  >
                    😀
                  </button>
                  <button
                    className="comp-tool-btn"
                    onClick={() => setDraft((d) => `${d} @`)}
                    title="Mention someone"
                  >
                    @
                  </button>
                  <button
                    className="comp-tool-btn"
                    onClick={() => {
                      setDraft('🤖 Hey Slackbot, can you summarize our latest updates?');
                    }}
                    title="Ask Slackbot"
                    style={{ color: '#c084fc', width: 'auto', padding: '0 6px', fontSize: '0.8rem' }}
                  >
                    ⚡ Slackbot
                  </button>
                </div>

                {/* Emoji Picker Popover */}
                {showEmojiPicker && (
                  <div className="emoji-popover">
                    {EMOJI_LIST.map((emoji) => (
                      <button
                        key={emoji}
                        className="emoji-choice-btn"
                        onClick={() => {
                          setDraft((d) => d + emoji);
                          setShowEmojiPicker(false);
                        }}
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                )}

                {/* Textarea Input */}
                <textarea
                  className="composer-textarea"
                  placeholder={
                    selectedDmUser
                      ? `Message ${selectedDmUser.name}...`
                      : `Message #${activeChannel?.name ?? 'channel'}...`
                  }
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void handleSendMessage();
                    }
                  }}
                />

                {/* Composer Footer */}
                <div className="composer-footer">
                  <div className="composer-footer-left">
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      Return to send • Shift+Return for new line
                    </span>
                    {isSyncing && (
                      <span style={{ fontSize: '0.75rem', color: '#38bdf8' }}>
                        • Syncing...
                      </span>
                    )}
                  </div>
                  <button
                    className="composer-send-btn"
                    onClick={() => void handleSendMessage()}
                    disabled={!draft.trim()}
                  >
                    Send ➔
                  </button>
                </div>
              </div>
            </div>
          </main>
        )}

        {/* 5. Right Drawer: Thread Panel */}
        {activeThreadMessage && (
          <aside className="thread-drawer">
            <div className="thread-header">
              <span className="thread-header-title">Thread</span>
              <button
                className="thread-close-btn"
                onClick={() => setActiveThreadMessage(null)}
                title="Close thread"
              >
                ✕
              </button>
            </div>

            <div className="thread-messages-list">
              {/* Root Message Card */}
              <div className="thread-root-card">
                <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                  <div
                    className="author-avatar"
                    style={{ background: getUser(activeThreadMessage.author_id).avatarBg, width: '28px', height: '28px', fontSize: '0.8rem' }}
                  >
                    {getUser(activeThreadMessage.author_id).name.charAt(0)}
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>{getUser(activeThreadMessage.author_id).name}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                      {new Date(activeThreadMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: '0.9rem', color: '#e2e8f0' }}>{activeThreadMessage.body}</div>
              </div>

              <div className="thread-replies-divider">
                <span>{threadReplies.length} {threadReplies.length === 1 ? 'reply' : 'replies'}</span>
              </div>

              {/* Thread Replies List */}
              {threadReplies.map((reply) => {
                const author = getUser(reply.author_id);
                return (
                  <div className="message-item" key={reply.id} style={{ padding: '6px 8px' }}>
                    <div className="author-avatar" style={{ background: author.avatarBg, width: '28px', height: '28px', fontSize: '0.8rem' }}>
                      {author.name.charAt(0)}
                    </div>
                    <div className="message-body-wrap">
                      <div className="message-meta-row">
                        <span className="author-name" style={{ fontSize: '0.85rem' }}>{author.name}</span>
                        <span className="message-timestamp">
                          {new Date(reply.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <div className="message-text" style={{ fontSize: '0.88rem' }}>{reply.body}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Thread Composer Box */}
            <div style={{ padding: '12px 16px' }}>
              <div className="composer-border-wrap">
                <textarea
                  className="composer-textarea"
                  style={{ minHeight: '44px' }}
                  placeholder="Reply in thread..."
                  value={threadDraft}
                  onChange={(e) => setThreadDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void handleSendThreadReply();
                    }
                  }}
                />
                <div className="composer-footer">
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Enter to reply</span>
                  <button
                    className="composer-send-btn"
                    style={{ padding: '4px 10px', fontSize: '0.8rem' }}
                    onClick={() => void handleSendThreadReply()}
                    disabled={!threadDraft.trim()}
                  >
                    Reply
                  </button>
                </div>
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* Global Search Modal (Ctrl+K) */}
      {isSearchOpen && (
        <div className="modal-overlay" onClick={() => setIsSearchOpen(false)}>
          <div className="search-modal-card" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>🔍</span>
              <input
                type="text"
                className="modal-input"
                placeholder="Type to search channels, teammates, or messages..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
              />
            </div>

            <div className="search-results-list">
              {searchResults.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                  {searchQuery ? 'No results found.' : 'Search across all messages, channels, and team members.'}
                </div>
              ) : (
                searchResults.map((item) => (
                  <button
                    key={`${item.type}-${item.id}`}
                    className="search-result-row"
                    onClick={() => {
                      if (item.type === 'channel') {
                        setSelectedChannelId(item.id);
                        setSelectedDmUser(null);
                        setActiveRailTab('channels');
                      } else if (item.type === 'user') {
                        const targetUser = TEAM_USERS.find((u) => u.id === item.id);
                        if (targetUser) {
                          setSelectedDmUser(targetUser);
                          setActiveRailTab('dms');
                        }
                      }
                      setIsSearchOpen(false);
                      setSearchQuery('');
                    }}
                  >
                    <span style={{ fontSize: '1.1rem' }}>
                      {item.type === 'channel' ? '#' : item.type === 'user' ? '👤' : '💬'}
                    </span>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-main)' }}>{item.title}</div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>{item.subtitle}</div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create Channel Modal */}
      {isCreateChannelOpen && (
        <div className="modal-overlay" onClick={() => setIsCreateChannelOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Create a channel</h2>
              <button
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}
                onClick={() => setIsCreateChannelOpen(false)}
              >
                ✕
              </button>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', margin: 0 }}>
              Channels are where your team communicates. They are best organized around topics like #proj-launch or #design.
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                void handleCreateChannel();
              }}
              style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}
            >
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '6px' }}>Name</label>
                <input
                  type="text"
                  className="modal-input"
                  placeholder="e.g. project-apollo"
                  value={newChannelName}
                  onChange={(e) => setNewChannelName(e.target.value)}
                  autoFocus
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '6px' }}>Topic (optional)</label>
                <input
                  type="text"
                  className="modal-input"
                  placeholder="What's this channel about?"
                  value={newChannelTopic}
                  onChange={(e) => setNewChannelTopic(e.target.value)}
                />
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="modal-btn-cancel"
                  onClick={() => setIsCreateChannelOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="modal-btn-primary"
                  disabled={!newChannelName.trim()}
                >
                  Create Channel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
