import { useEffect, useMemo, useState, useRef } from 'react';

import { queueMutationForSync, resolveDeviceId } from './offline/syncManager';
import { readDraft, writeDraft } from './offline/indexedDb';
import { RealtimeClient, type RealtimeEvent, type ConnectionStatus } from './realtime/realtimeClient';

type UserProfile = {
  id: string;
  name: string;
  handle: string;
  statusEmoji?: string;
  role: string;
  avatarBg: string;
  status: 'online' | 'away' | 'offline';
  isBot?: boolean;
};

const TEAM_USERS: UserProfile[] = [
  { id: 'user-1', name: 'Zoe Maxwell', handle: '@zoe', statusEmoji: '🏠', role: 'Social Media Manager', avatarBg: 'linear-gradient(135deg, #f59e0b, #d97706)', status: 'online' },
  { id: 'user-2', name: 'Lee Hao', handle: '@lee', role: 'Product Lead', avatarBg: 'linear-gradient(135deg, #8b5cf6, #6366f1)', status: 'online' },
  { id: 'user-3', name: 'Lisa Dawson', handle: '@lisa', role: 'Marketing Director', avatarBg: 'linear-gradient(135deg, #10b981, #059669)', status: 'online' },
  { id: 'user-bot', name: 'Acme Team', handle: '@acmeteam', role: 'Calendar & Status Bot', avatarBg: 'linear-gradient(135deg, #1d9bd1, #0284c7)', status: 'online', isBot: true },
  { id: 'user-slackbot', name: 'Slackbot AI', handle: '@slackbot', role: 'AI Workspace Copilot', avatarBg: 'linear-gradient(135deg, #522653, #3f0e40)', status: 'online', isBot: true },
];

type Channel = {
  id: string;
  name: string;
  workspace_id: string;
  topic?: string | null;
  is_private: boolean;
  is_archived?: boolean;
  badge?: number;
};

const DEFAULT_CHANNELS: Channel[] = [
  { id: 'ch-announcements', name: 'announcements', workspace_id: 'ws-default', topic: 'Company announcements', is_private: false },
  { id: 'ch-design-crit', name: 'design-crit', workspace_id: 'ws-default', topic: 'Design critique & reviews', is_private: true },
  { id: 'ch-media-and-pr', name: 'media-and-pr', workspace_id: 'ws-default', topic: 'Media and press relations', is_private: false, badge: 1 },
  { id: 'ch-social-media', name: 'social-media', workspace_id: 'ws-default', topic: 'Track and coordinate social media', is_private: false },
  { id: 'ch-team-marketing', name: 'team-marketing', workspace_id: 'ws-default', topic: 'Team marketing campaigns', is_private: false },
];

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
  custom_type?: 'calendar_event' | 'huddle_event' | 'canvas_event' | 'standard';
};

type ReactionItem = {
  id: string;
  workspace_id: string;
  channel_id: string;
  message_id: string;
  user_id: string;
  emoji: string;
};

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
  // Current active user (defaults to Zoe Maxwell as in screenshot)
  const [currentUser, setCurrentUser] = useState<UserProfile>(TEAM_USERS[0]);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  // Active Rail Tab: Home, DMs, Activity, More
  const [activeRailTab, setActiveRailTab] = useState<'home' | 'dms' | 'activity' | 'more'>('home');

  // Channels & Navigation
  const [channels, setChannels] = useState<Channel[]>(DEFAULT_CHANNELS);
  const [selectedChannelId, setSelectedChannelId] = useState<string>('ch-social-media');
  const [selectedDmUser, setSelectedDmUser] = useState<UserProfile | null>(null);

  // Messages & Reactions
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [reactions, setReactions] = useState<ReactionItem[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);

  // Thread Drawer
  const [activeThreadMessage, setActiveThreadMessage] = useState<MessageItem | null>(null);
  const [threadReplies, setThreadReplies] = useState<MessageItem[]>([]);
  const [threadDraft, setThreadDraft] = useState('');

  // Modals & UI Toggles
  const [isCreateChannelOpen, setIsCreateChannelOpen] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');
  const [newChannelTopic, setNewChannelTopic] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isHuddleActive, setIsHuddleActive] = useState(false);

  // Connection & Sync
  const [connStatus, setConnStatus] = useState<ConnectionStatus>('CONNECTING');
  const [deviceId, setDeviceId] = useState('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // User Map
  const userMap = useMemo(() => {
    const map = new Map<string, UserProfile>();
    TEAM_USERS.forEach((u) => map.set(u.id, u));
    return map;
  }, []);

  const getUser = (userId: string): UserProfile => {
    return userMap.get(userId) ?? {
      id: userId,
      name: userId === 'user-bot' ? 'Acme Team' : userId,
      handle: `@${userId}`,
      role: 'Member',
      avatarBg: 'linear-gradient(135deg, #64748b, #475569)',
      status: 'online',
    };
  };

  const activeChannel = useMemo(
    () => channels.find((c) => c.id === selectedChannelId) ?? channels.find((c) => c.name === 'social-media') ?? channels[0],
    [channels, selectedChannelId],
  );

  const currentConversationId = selectedDmUser ? `dm-${selectedDmUser.id}` : (activeChannel?.id ?? 'ch-social-media');

  // Load Initial Data from Backend
  const loadWorkspaceData = async () => {
    try {
      setLoading(true);
      const [fetchedChannels, fetchedMessages, fetchedReactions] = await Promise.all([
        fetch(`${API_BASE}/api/v1/channels`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/api/v1/messages`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/api/v1/reactions`).then((r) => (r.ok ? r.json() : [])),
      ]);

      if (Array.isArray(fetchedChannels) && fetchedChannels.length > 0) {
        // Merge with screenshot channels
        const map = new Map<string, Channel>();
        DEFAULT_CHANNELS.forEach((c) => map.set(c.id, c));
        fetchedChannels.forEach((c: Channel) => map.set(c.id, { ...c, badge: c.name === 'media-and-pr' ? 1 : undefined }));
        setChannels(Array.from(map.values()));
      }
      if (Array.isArray(fetchedMessages) && fetchedMessages.length > 0) {
        setMessages(fetchedMessages);
      }
      if (Array.isArray(fetchedReactions)) {
        setReactions(fetchedReactions);
      }
    } catch (err) {
      console.warn('Workspace load notice:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void resolveDeviceId().then((id) => setDeviceId(id));
    void loadWorkspaceData();
  }, []);

  // Connect Realtime Client
  useEffect(() => {
    const client = new RealtimeClient();
    const unsubStatus = client.onStatusChange((status) => setConnStatus(status));
    client.connect(getRealtimeUrl(currentUser.id));

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

    client.on('reaction.deleted', (event: RealtimeEvent) => {
      const p = event.payload;
      setReactions((prev) =>
        prev.filter((r) => !(r.message_id === p.message_id && r.user_id === p.user_id && r.emoji === p.emoji)),
      );
    });

    return () => {
      unsubStatus();
      client.disconnect();
    };
  }, [currentUser.id, activeThreadMessage?.id]);

  // Read saved draft on conversation change
  useEffect(() => {
    if (!deviceId) return;
    void readDraft(`${deviceId}:${currentConversationId}`).then((saved) => setDraft(saved || ''));
  }, [deviceId, currentConversationId]);

  // Auto-save draft
  useEffect(() => {
    if (!deviceId) return;
    void writeDraft(`${deviceId}:${currentConversationId}`, draft);
  }, [draft, deviceId, currentConversationId]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, selectedChannelId, selectedDmUser]);

  // Current conversation messages
  const conversationMessages = useMemo(() => {
    return messages.filter((m) => {
      if (m.thread_id) return false;
      return m.channel_id === currentConversationId;
    });
  }, [messages, currentConversationId]);

  // Update thread replies
  useEffect(() => {
    if (!activeThreadMessage) {
      setThreadReplies([]);
      return;
    }
    const replies = messages.filter((m) => m.thread_id === activeThreadMessage.id);
    setThreadReplies(replies);
  }, [activeThreadMessage, messages]);

  // Send Main Stream Message
  const handleSendMessage = async () => {
    if (!draft.trim()) return;
    const text = draft.trim();
    const clientMessageId = `msg-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`;
    setDraft('');
    if (deviceId) void writeDraft(`${deviceId}:${currentConversationId}`, '');

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
    } catch (err) {
      console.warn('Failed to send message:', err);
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

  // Toggle Reaction
  const handleToggleReaction = async (messageId: string, emoji: string) => {
    const existing = reactions.find(
      (r) => r.message_id === messageId && r.user_id === currentUser.id && r.emoji === emoji,
    );

    if (existing) {
      setReactions((prev) => prev.filter((r) => r.id !== existing.id));
      try {
        await fetch(`${API_BASE}/api/v1/reactions/${messageId}/${currentUser.id}/${encodeURIComponent(emoji)}`, {
          method: 'DELETE',
        });
      } catch (err) {
        console.warn('Failed to remove reaction:', err);
      }
    } else {
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

  // Create Channel
  const handleCreateChannel = async () => {
    if (!newChannelName.trim()) return;
    const clean = newChannelName.trim().toLowerCase().replace(/\s+/g, '-');
    try {
      const response = await fetch(`${API_BASE}/api/v1/channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: DEFAULT_WORKSPACE_ID,
          name: clean,
          topic: newChannelTopic.trim() || `Channel for #${clean}`,
          is_private: false,
        }),
      });
      if (response.ok) {
        const created = (await response.json()) as Channel;
        setChannels((prev) => [...prev, created]);
        setSelectedChannelId(created.id);
        setSelectedDmUser(null);
        setNewChannelName('');
        setNewChannelTopic('');
        setIsCreateChannelOpen(false);
      }
    } catch {
      // fallback
    }
  };

  // Keyboard shortcut Ctrl+K
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

  // Search Results
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    const matchedChannels = channels
      .filter((c) => c.name.toLowerCase().includes(q))
      .map((c) => ({ type: 'channel' as const, id: c.id, title: `#${c.name}`, subtitle: c.topic || 'Channel' }));
    const matchedUsers = TEAM_USERS
      .filter((u) => u.name.toLowerCase().includes(q))
      .map((u) => ({ type: 'user' as const, id: u.id, title: u.name, subtitle: `${u.handle} • ${u.role}` }));
    return [...matchedChannels, ...matchedUsers];
  }, [searchQuery, channels]);

  // Grouped Reactions
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

  return (
    <div className="app-container">
      {/* =========================================================
         1. TOP BAR (Dusty Mauve Slack Header)
      ========================================================= */}
      <header className="top-header">
        <div className="top-header-left">
          <button className="top-nav-btn" title="Menu">☰</button>
          <div className="top-arrows-group">
            <button className="top-nav-btn" title="Back">←</button>
            <button className="top-nav-btn" title="Forward">→</button>
          </div>
        </div>

        <div className="top-search-center">
          <div className="top-search-pill" onClick={() => setIsSearchOpen(true)}>
            <span className="search-icon-svg">🔍</span>
            <span className="search-text">Search Acme Inc</span>
          </div>
        </div>

        <div className="top-header-right">
          <button className="top-nav-btn" title="Help">?</button>
          <div className="window-controls-group">
            <span className="window-control-icon">—</span>
            <span className="window-control-icon">▢</span>
            <span className="window-control-icon">✕</span>
          </div>
        </div>
      </header>

      {/* =========================================================
         2. MAIN WORKSPACE ROW
      ========================================================= */}
      <div className="main-workspace">
        {/* Activity Rail (Leftmost Deep Purple #3f0e40) */}
        <nav className="activity-rail">
          {/* Yellow Acme Logo Box */}
          <div className="workspace-logo-box" title="Acme Inc">
            <span>😊</span>
          </div>

          <button
            className={`rail-btn ${activeRailTab === 'home' ? 'active' : ''}`}
            onClick={() => {
              setActiveRailTab('home');
              setSelectedDmUser(null);
            }}
            title="Home"
          >
            <div className="rail-icon-box">🏠</div>
            <span className="rail-label">Home</span>
          </button>

          <button
            className={`rail-btn ${activeRailTab === 'dms' ? 'active' : ''}`}
            onClick={() => setActiveRailTab('dms')}
            title="DMs"
          >
            <div className="rail-icon-box">💬</div>
            <span className="rail-label">DMs</span>
          </button>

          <button
            className={`rail-btn ${activeRailTab === 'activity' ? 'active' : ''}`}
            onClick={() => setActiveRailTab('activity')}
            title="Activity"
          >
            <div className="rail-icon-box">🔔</div>
            <span className="rail-label">Activity</span>
          </button>

          <button
            className={`rail-btn ${activeRailTab === 'more' ? 'active' : ''}`}
            onClick={() => setActiveRailTab('more')}
            title="More"
          >
            <div className="rail-icon-box">···</div>
            <span className="rail-label">More</span>
          </button>

          <div className="rail-bottom">
            <button className="rail-add-btn" onClick={() => setIsCreateChannelOpen(true)} title="Add Channel or Teammate">+</button>

            {/* Current User Avatar with Status Indicator */}
            <div
              className="user-avatar-rail"
              onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
              title={`${currentUser.name} • Click to switch user`}
            >
              <span>{currentUser.name.charAt(0)}</span>
              <span className={`user-presence-dot ${currentUser.status}`} />
            </div>
          </div>
        </nav>

        {/* Channels & DMs Sidebar (Pale Lavender #f3ecf1) */}
        <aside className="channels-sidebar">
          <div className="sidebar-header">
            <div className="workspace-name-wrap" onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}>
              <span>Acme Inc</span>
              <small style={{ fontSize: '0.75rem', opacity: 0.7 }}>▾</small>
            </div>
            <button className="sidebar-filter-btn" title="Filter list">≡▾</button>
          </div>

          <div className="sidebar-scroll-area">
            {/* Quick Navigation Items */}
            <ul className="quick-nav-list">
              <li>
                <button className="quick-nav-item">
                  <span className="quick-nav-icon">≡</span>
                  <span>Unreads</span>
                </button>
              </li>
              <li>
                <button className="quick-nav-item">
                  <span className="quick-nav-icon">💬</span>
                  <span>Threads</span>
                </button>
              </li>
              <li>
                <button className="quick-nav-item muted">
                  <span className="quick-nav-icon">✈</span>
                  <span>Drafts & sent</span>
                </button>
              </li>
            </ul>

            {/* Channels Section */}
            <div>
              <div className="sidebar-section-header">
                <span>Channels</span>
                <button className="sidebar-section-btn" onClick={() => setIsCreateChannelOpen(true)} title="Create Channel">+</button>
              </div>
              <ul className="sidebar-nav-list">
                {channels.map((ch) => {
                  const isActive = !selectedDmUser && activeChannel?.id === ch.id;
                  return (
                    <li key={ch.id}>
                      <button
                        className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedChannelId(ch.id);
                          setSelectedDmUser(null);
                        }}
                      >
                        <span className="sidebar-item-prefix">{ch.is_private ? '🔒' : '#'}</span>
                        <span className="sidebar-item-name">{ch.name}</span>
                        {ch.badge && <span className="sidebar-unread-badge">{ch.badge}</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>

            {/* Direct Messages Section */}
            <div>
              <div className="sidebar-section-header">
                <span>Direct messages</span>
              </div>
              <ul className="sidebar-nav-list">
                <li>
                  <button
                    className={`sidebar-nav-item ${selectedDmUser?.id === 'user-2' ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedDmUser(TEAM_USERS[1]); // Lee Hao
                    }}
                  >
                    <div className="dm-avatar-mini" style={{ background: TEAM_USERS[1].avatarBg, display: 'grid', placeItems: 'center', color: '#fff', fontSize: '0.7rem' }}>
                      {TEAM_USERS[1].name.charAt(0)}
                    </div>
                    <span className="sidebar-item-name">Lee Hao</span>
                    <span className="sidebar-unread-badge">2</span>
                  </button>
                </li>
                {TEAM_USERS.filter((u) => u.id !== 'user-1' && u.id !== 'user-2').map((u) => (
                  <li key={u.id}>
                    <button
                      className={`sidebar-nav-item ${selectedDmUser?.id === u.id ? 'active' : ''}`}
                      onClick={() => setSelectedDmUser(u)}
                    >
                      <div className="dm-avatar-mini" style={{ background: u.avatarBg, display: 'grid', placeItems: 'center', color: '#fff', fontSize: '0.7rem' }}>
                        {u.name.charAt(0)}
                      </div>
                      <span className="sidebar-item-name">{u.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </aside>

        {/* Main Conversation Pane (#ffffff) */}
        <main className="conversation-panel">
          {/* Channel Header */}
          <header className="channel-header">
            <div className="channel-header-left">
              <div className="channel-title-row">
                <span>{selectedDmUser ? selectedDmUser.name : `# ${activeChannel?.name ?? 'social-media'}`}</span>
                <small style={{ fontSize: '0.8rem', opacity: 0.6 }}>▾</small>
              </div>
              <div className="channel-topic-text">
                {selectedDmUser ? `${selectedDmUser.handle} • ${selectedDmUser.role}` : (activeChannel?.topic || 'Track and coordinate social media')}
              </div>
            </div>

            <div className="channel-header-right">
              {/* Stacked Avatars + 58 */}
              <div className="members-stack-group" title="58 Members">
                <div className="avatar-stack-img" style={{ background: '#f59e0b', display: 'grid', placeItems: 'center', color: '#fff', fontSize: '0.65rem' }}>Z</div>
                <div className="avatar-stack-img" style={{ background: '#8b5cf6', display: 'grid', placeItems: 'center', color: '#fff', fontSize: '0.65rem' }}>L</div>
                <div className="avatar-stack-img" style={{ background: '#10b981', display: 'grid', placeItems: 'center', color: '#fff', fontSize: '0.65rem' }}>D</div>
                <span className="member-count-num">58</span>
              </div>

              {/* Huddle Button */}
              <button
                className={`huddle-pill-btn ${isHuddleActive ? 'active' : ''}`}
                onClick={() => setIsHuddleActive(!isHuddleActive)}
                title="Start a huddle"
              >
                <span>🎧</span>
                <span>▾</span>
              </button>

              {/* Canvas Toggle */}
              <button className="canvas-toggle-btn" title="Canvas notes">
                ⧉
              </button>
            </div>
          </header>

          {/* Messages Stream */}
          <div className="messages-container">
            {/* 1. Acme Team Calendar Event Message */}
            <div className="message-item">
              <div className="calendar-app-badge">
                <span style={{ fontSize: '0.55rem', opacity: 0.9 }}>OCT</span>
                <span>31</span>
              </div>
              <div className="msg-body-wrap">
                <div className="msg-meta-row">
                  <span className="msg-author-name">Acme Team</span>
                  <span className="app-badge">APP</span>
                  <span className="msg-timestamp">12:45 PM</span>
                </div>
                <div className="msg-content-text">Event starting in 15 minutes:</div>
                {/* Cyan Border Card */}
                <div className="attachment-card-cyan">
                  <div className="attach-title">Team Status Meeting 📝</div>
                  <div className="attach-time">Today from 1:00 PM to 1:30 PM</div>
                </div>
              </div>
            </div>

            {/* 2. Zoe Maxwell Message */}
            <div className="message-item">
              <div className="msg-avatar" style={{ background: 'linear-gradient(135deg, #f59e0b, #d97706)' }}>
                Z
              </div>
              <div className="msg-body-wrap">
                <div className="msg-meta-row">
                  <span className="msg-author-name">Zoe Maxwell</span>
                  <span>🏠</span>
                  <span className="msg-timestamp">12:55 PM</span>
                </div>
                <div className="msg-content-text">
                  Today <span className="mention-pill">@Lisa</span> will join our team huddle to provide updates on the launch. If you have questions, bring 'em. See you all soon!
                </div>
              </div>
              <div className="message-hover-toolbar">
                {['👍', '❤️', '🚀'].map((emoji) => (
                  <button key={emoji} className="toolbar-btn" onClick={() => void handleToggleReaction('msg-sm-2', emoji)}>{emoji}</button>
                ))}
                <button className="toolbar-btn" onClick={() => setActiveThreadMessage({ id: 'msg-sm-2', workspace_id: DEFAULT_WORKSPACE_ID, channel_id: currentConversationId, author_id: 'user-1', sequence: 2, body: 'Today @Lisa will join our team huddle to provide updates on the launch.', created_at: new Date().toISOString() })}>💬</button>
              </div>
            </div>

            {/* 3. Huddle Event Message */}
            <div className="huddle-event-row">
              <div className="huddle-event-icon-circle">🎧</div>
              <div className="msg-body-wrap">
                <div className="msg-meta-row">
                  <span className="msg-author-name" style={{ fontWeight: 700 }}>A huddle happened</span>
                  <span className="msg-timestamp">1:00 PM</span>
                </div>
                <div className="msg-content-text" style={{ color: 'var(--text-muted)' }}>
                  Lisa Dawson and 5 others were in the huddle for 28 minutes.
                </div>
              </div>
            </div>

            {/* 4. Lee Hao Message with Canvas */}
            <div className="message-item">
              <div className="msg-avatar" style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}>
                L
              </div>
              <div className="msg-body-wrap">
                <div className="msg-meta-row">
                  <span className="msg-author-name">Lee Hao</span>
                  <span className="msg-timestamp">1:45 PM</span>
                </div>
                <div className="msg-content-text">
                  Please add any other notes from our sync today!
                </div>
                {/* Canvas Sub-card */}
                <div className="canvas-embed-box">
                  <div className="canvas-label-pill">Canvas ▾</div>
                  <div className="canvas-inner-card">
                    <div className="canvas-icon-box">📄</div>
                    <div>
                      <div className="canvas-card-title">1/9 Meeting notes</div>
                      <div className="canvas-card-sub">Canvas</div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="message-hover-toolbar">
                {['👍', '❤️', '🚀'].map((emoji) => (
                  <button key={emoji} className="toolbar-btn" onClick={() => void handleToggleReaction('msg-sm-4', emoji)}>{emoji}</button>
                ))}
                <button className="toolbar-btn" onClick={() => setActiveThreadMessage({ id: 'msg-sm-4', workspace_id: DEFAULT_WORKSPACE_ID, channel_id: currentConversationId, author_id: 'user-2', sequence: 4, body: 'Please add any other notes from our sync today!', created_at: new Date().toISOString() })}>💬</button>
              </div>
            </div>

            {/* Dynamic Messages */}
            {conversationMessages
              .filter((m) => !['msg-sm-1', 'msg-sm-2', 'msg-sm-3', 'msg-sm-4'].includes(m.id))
              .map((msg) => {
                const author = getUser(msg.author_id);
                const msgRx = getGroupedReactions(msg.id);
                return (
                  <div className="message-item" key={msg.id}>
                    <div className="msg-avatar" style={{ background: author.avatarBg }}>
                      {author.name.charAt(0)}
                    </div>
                    <div className="msg-body-wrap">
                      <div className="msg-meta-row">
                        <span className="msg-author-name">{author.name}</span>
                        {author.statusEmoji && <span>{author.statusEmoji}</span>}
                        {author.isBot && <span className="app-badge">APP</span>}
                        <span className="msg-timestamp">
                          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <div className="msg-content-text">{msg.body}</div>

                      {/* Reactions */}
                      {msgRx.length > 0 && (
                        <div className="reactions-row">
                          {msgRx.map((rx) => (
                            <button
                              key={rx.emoji}
                              className={`reaction-pill ${rx.reactedByMe ? 'reacted' : ''}`}
                              onClick={() => void handleToggleReaction(msg.id, rx.emoji)}
                            >
                              <span>{rx.emoji}</span>
                              <span className="reaction-count">{rx.count}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="message-hover-toolbar">
                      {['👍', '❤️', '🚀'].map((emoji) => (
                        <button key={emoji} className="toolbar-btn" onClick={() => void handleToggleReaction(msg.id, emoji)}>{emoji}</button>
                      ))}
                      <button className="toolbar-btn" onClick={() => setActiveThreadMessage(msg)}>💬</button>
                    </div>
                  </div>
                );
              })}
            <div ref={messagesEndRef} />
          </div>

          {/* =========================================================
             7. COMPOSER BOX
          ========================================================= */}
          <div className="composer-box">
            <div className="composer-border-wrap">
              <textarea
                className="composer-textarea"
                placeholder={`Message #${activeChannel?.name ?? 'social-media'}`}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    void handleSendMessage();
                  }
                }}
              />

              {/* Bottom Toolbar: +, 😀, @, Aa, 🎥, 🎙️, 📝 and Send Button */}
              <div className="composer-bottom-toolbar">
                <div className="composer-tools-left">
                  <button className="comp-icon-btn" title="Add attachment">+</button>
                  <button className="comp-icon-btn" onClick={() => setShowEmojiPicker(!showEmojiPicker)} title="Add emoji">😀</button>
                  <button className="comp-icon-btn" onClick={() => setDraft((d) => `${d} @`)} title="Mention someone">@</button>
                  <button className="comp-icon-btn" onClick={() => setDraft((d) => `**${d}**`)} title="Text formatting">Aa</button>
                  <button className="comp-icon-btn" title="Record video clip">🎥</button>
                  <button className="comp-icon-btn" title="Record audio clip">🎙️</button>
                  <button className="comp-icon-btn" title="Create canvas or note">📝</button>
                </div>

                <div className="composer-tools-right">
                  <button
                    className="comp-send-btn"
                    onClick={() => void handleSendMessage()}
                    disabled={!draft.trim()}
                    title="Send message (Enter)"
                  >
                    <span>✈</span>
                    <span style={{ fontSize: '0.65rem' }}>▾</span>
                  </button>
                </div>
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
            </div>
          </div>
        </main>

        {/* Right Thread Drawer */}
        {activeThreadMessage && (
          <aside className="thread-drawer">
            <div className="thread-header">
              <span className="thread-header-title">Thread</span>
              <button className="thread-close-btn" onClick={() => setActiveThreadMessage(null)}>✕</button>
            </div>
            <div className="thread-messages-list">
              <div className="thread-root-card">
                <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                  <div className="msg-avatar" style={{ background: getUser(activeThreadMessage.author_id).avatarBg, width: '28px', height: '28px', fontSize: '0.8rem' }}>
                    {getUser(activeThreadMessage.author_id).name.charAt(0)}
                  </div>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: '0.88rem' }}>{getUser(activeThreadMessage.author_id).name}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                      {new Date(activeThreadMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: '0.92rem' }}>{activeThreadMessage.body}</div>
              </div>

              {threadReplies.map((reply) => (
                <div className="message-item" key={reply.id}>
                  <div className="msg-avatar" style={{ background: getUser(reply.author_id).avatarBg, width: '28px', height: '28px', fontSize: '0.8rem' }}>
                    {getUser(reply.author_id).name.charAt(0)}
                  </div>
                  <div className="msg-body-wrap">
                    <div className="msg-meta-row">
                      <span className="msg-author-name">{getUser(reply.author_id).name}</span>
                      <span className="msg-timestamp">
                        {new Date(reply.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="msg-content-text">{reply.body}</div>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ padding: '12px 16px' }}>
              <div className="composer-border-wrap">
                <textarea
                  className="composer-textarea"
                  style={{ minHeight: '44px' }}
                  placeholder="Reply..."
                  value={threadDraft}
                  onChange={(e) => setThreadDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void handleSendThreadReply();
                    }
                  }}
                />
                <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '6px 10px' }}>
                  <button className="comp-send-btn" onClick={() => void handleSendThreadReply()} disabled={!threadDraft.trim()}>
                    Reply
                  </button>
                </div>
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* User Switcher Dropdown */}
      {isUserMenuOpen && (
        <div className="user-menu-popover">
          <div style={{ padding: '4px 6px 8px', borderBottom: '1px solid var(--slack-border)' }}>
            <div style={{ fontWeight: 800, fontSize: '0.92rem' }}>Switch Active Teammate</div>
            <small style={{ color: 'var(--text-muted)' }}>Test chat from different perspectives</small>
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
              <div className="dm-avatar-mini" style={{ background: user.avatarBg, display: 'grid', placeItems: 'center', color: '#fff' }}>
                {user.name.charAt(0)}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>{user.name}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>{user.role}</div>
              </div>
              {user.id === currentUser.id && <span style={{ color: 'var(--badge-unread)', fontWeight: 800 }}>✓</span>}
            </button>
          ))}
        </div>
      )}

      {/* Global Search Modal (Ctrl+K) */}
      {isSearchOpen && (
        <div className="modal-overlay" onClick={() => setIsSearchOpen(false)}>
          <div className="modal-card" style={{ maxWidth: '580px' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🔍</span>
              <input
                type="text"
                className="modal-input"
                placeholder="Search messages, channels, or team members..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
              />
            </div>
            <div style={{ maxHeight: '300px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {searchResults.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                  {searchQuery ? 'No results found.' : 'Type to search channels and team members.'}
                </div>
              ) : (
                searchResults.map((item) => (
                  <button
                    key={`${item.type}-${item.id}`}
                    className="user-option-btn"
                    onClick={() => {
                      if (item.type === 'channel') {
                        setSelectedChannelId(item.id);
                        setSelectedDmUser(null);
                      } else if (item.type === 'user') {
                        const target = TEAM_USERS.find((u) => u.id === item.id);
                        if (target) setSelectedDmUser(target);
                      }
                      setIsSearchOpen(false);
                      setSearchQuery('');
                    }}
                  >
                    <span>{item.type === 'channel' ? '#' : '👤'}</span>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>{item.title}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{item.subtitle}</div>
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
            <h2 className="modal-title">Create a channel</h2>
            <input
              type="text"
              className="modal-input"
              placeholder="e.g. team-marketing"
              value={newChannelName}
              onChange={(e) => setNewChannelName(e.target.value)}
              autoFocus
            />
            <input
              type="text"
              className="modal-input"
              placeholder="Channel topic (optional)"
              value={newChannelTopic}
              onChange={(e) => setNewChannelTopic(e.target.value)}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button className="user-option-btn" style={{ width: 'auto' }} onClick={() => setIsCreateChannelOpen(false)}>Cancel</button>
              <button className="comp-send-btn" onClick={() => void handleCreateChannel()} disabled={!newChannelName.trim()}>Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
