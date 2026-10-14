import { useEffect, useMemo, useState, useRef } from 'react';

import { queueMutationForSync, resolveDeviceId } from './offline/syncManager';
import { readDraft, writeDraft } from './offline/indexedDb';
import { RealtimeClient, type RealtimeEvent, type ConnectionStatus } from './realtime/realtimeClient';

export type UserProfile = {
  id: string;
  email?: string;
  name: string;
  handle: string;
  statusEmoji?: string;
  role: string;
  avatarBg: string;
  status: 'online' | 'away' | 'offline';
  isBot?: boolean;
};

const DEFAULT_USERS: UserProfile[] = [
  { id: 'user-1', email: 'zoe@acme.com', name: 'Zoe Maxwell', handle: '@zoe', statusEmoji: '🏠', role: 'admin', avatarBg: 'linear-gradient(135deg, #f59e0b, #d97706)', status: 'online' },
  { id: 'user-2', email: 'lee@acme.com', name: 'Lee Hao', handle: '@lee', role: 'member', avatarBg: 'linear-gradient(135deg, #8b5cf6, #6366f1)', status: 'online' },
  { id: 'user-3', email: 'lisa@acme.com', name: 'Lisa Dawson', handle: '@lisa', role: 'member', avatarBg: 'linear-gradient(135deg, #10b981, #059669)', status: 'online' },
  { id: 'user-bot', email: 'bot@acme.com', name: 'Acme Team', handle: '@acmeteam', role: 'member', avatarBg: 'linear-gradient(135deg, #1d9bd1, #0284c7)', status: 'online', isBot: true },
  { id: 'user-slackbot', email: 'slackbot@acme.com', name: 'Slackbot AI', handle: '@slackbot', role: 'member', avatarBg: 'linear-gradient(135deg, #522653, #3f0e40)', status: 'online', isBot: true },
];

export type Channel = {
  id: string;
  name: string;
  workspace_id: string;
  topic?: string | null;
  is_private: boolean;
  is_archived?: boolean;
  badge?: number;
};

export type MessageItem = {
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

export type ReactionItem = {
  id: string;
  workspace_id: string;
  channel_id: string;
  message_id: string;
  user_id: string;
  emoji: string;
};

export type AuditLogEntry = {
  id: string;
  action: string;
  actor_id: string;
  target_id?: string | null;
  timestamp: string;
  details: Record<string, unknown>;
};

export type AdminStats = {
  total_users: number;
  total_channels: number;
  total_messages: number;
  total_files: number;
};

export type MemberItem = {
  id: string;
  email: string;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
};

const DEFAULT_WORKSPACE_ID = 'ws-default';
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

function getRealtimeUrl(clientId: string, token?: string | null) {
  const tokenQuery = token ? `&token=${encodeURIComponent(token)}` : '';
  if (import.meta.env.VITE_WS_URL) {
    const base = String(import.meta.env.VITE_WS_URL).replace(/\/+$/, '');
    return `${base}?client_id=${clientId}${tokenQuery}`;
  }
  if (API_BASE && API_BASE.startsWith('http')) {
    try {
      const url = new URL(API_BASE);
      const wsProto = url.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${wsProto}//${url.host}/ws?client_id=${clientId}${tokenQuery}`;
    } catch {
      // ignore
    }
  }
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const port = window.location.port ? `:${window.location.port}` : '';
  return `${protocol}://${window.location.hostname}${port}/ws?client_id=${clientId}${tokenQuery}`;
}

const EMOJI_LIST = ['👍', '❤️', '😂', '🚀', '🔥', '🎉', '💡', '🤖', '☕', '👀', '💯', '🙌'];

export default function App() {
  // Authentication State
  const [currentUser, setCurrentUser] = useState<UserProfile>(DEFAULT_USERS[0]);
  const [accessToken, setAccessToken] = useState<string | null>(() => localStorage.getItem('access_token'));
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authTab, setAuthTab] = useState<'login' | 'register'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authUsername, setAuthUsername] = useState('');
  const [authDisplayName, setAuthDisplayName] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);

  // Active Rail Tab: Home, DMs, Activity, More
  const [activeRailTab, setActiveRailTab] = useState<'home' | 'dms' | 'activity' | 'more'>('home');
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  // Channels & Navigation
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>('ch-social-media');
  const [selectedDmUser, setSelectedDmUser] = useState<UserProfile | null>(null);
  const [currentDmConversationId, setCurrentDmConversationId] = useState<string | null>(null);

  // Messages & Reactions
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [reactions, setReactions] = useState<ReactionItem[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingBody, setEditingBody] = useState('');

  // Thread Drawer
  const [activeThreadMessage, setActiveThreadMessage] = useState<MessageItem | null>(null);
  const [threadReplies, setThreadReplies] = useState<MessageItem[]>([]);
  const [threadDraft, setThreadDraft] = useState('');

  // Modals & UI Toggles
  const [isCreateChannelOpen, setIsCreateChannelOpen] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');
  const [newChannelTopic, setNewChannelTopic] = useState('');
  const [newChannelIsPrivate, setNewChannelIsPrivate] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<{ id: string; type: string; title: string; subtitle: string; channel_id?: string }[]>([]);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isHuddleActive, setIsHuddleActive] = useState(false);

  // Admin Console Modal
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [adminTab, setAdminTab] = useState<'stats' | 'members' | 'audit'>('stats');
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [adminMembers, setAdminMembers] = useState<MemberItem[]>([]);
  const [adminAuditLogs, setAdminAuditLogs] = useState<AuditLogEntry[]>([]);
  const [adminNotice, setAdminNotice] = useState<string | null>(null);

  // AI Copilot
  const [aiSummary, setAiSummary] = useState<{ summary?: string; key_points?: string[]; action_items?: string[] } | null>(null);
  const [isAiLoading, setIsAiLoading] = useState(false);

  // Typing & Presence
  const [typingUsers, setTypingUsers] = useState<Map<string, string>>(new Map());
  const [connStatus, setConnStatus] = useState<ConnectionStatus>('CONNECTING');
  const [deviceId, setDeviceId] = useState('');

  // Refs
  const realtimeClientRef = useRef<RealtimeClient | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const typingTimerRef = useRef<number | null>(null);

  // User Map
  const userMap = useMemo(() => {
    const map = new Map<string, UserProfile>();
    DEFAULT_USERS.forEach((u) => map.set(u.id, u));
    return map;
  }, []);

  const getUser = (userId: string): UserProfile => {
    return userMap.get(userId) ?? {
      id: userId,
      name: userId === 'user-bot' ? 'Acme Team' : userId,
      handle: `@${userId}`,
      role: 'member',
      avatarBg: 'linear-gradient(135deg, #64748b, #475569)',
      status: 'online',
    };
  };

  const activeChannel = useMemo(
    () => channels.find((c) => c.id === selectedChannelId) ?? channels[0],
    [channels, selectedChannelId],
  );

  const currentConversationId = selectedDmUser ? (currentDmConversationId ?? `dm-${selectedDmUser.id}`) : (activeChannel?.id ?? 'ch-social-media');

  // Authenticated API Fetch Helper
  const apiFetch = async (endpoint: string, options: RequestInit = {}): Promise<{ ok: boolean; status: number; data: unknown }> => {
    const token = accessToken ?? localStorage.getItem('access_token');
    const headers = new Headers(options.headers || {});
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    let res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    if (res.status === 401 && localStorage.getItem('refresh_token')) {
      // Attempt token rotation refresh
      try {
        const refreshRes = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: localStorage.getItem('refresh_token') }),
        });
        if (refreshRes.ok) {
          const tokens = await refreshRes.json();
          localStorage.setItem('access_token', tokens.access_token);
          localStorage.setItem('refresh_token', tokens.refresh_token);
          setAccessToken(tokens.access_token);
          headers.set('Authorization', `Bearer ${tokens.access_token}`);
          res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
        } else {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setAccessToken(null);
        }
      } catch {
        // failed refresh
      }
    }

    let data: unknown = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    return { ok: res.ok, status: res.status, data };
  };

  // Perform Login
  const performLogin = async (email: string, pass: string) => {
    setAuthError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: pass }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Authentication failed' }));
        setAuthError(err.detail || 'Login failed');
        return false;
      }
      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      setAccessToken(data.access_token);

      // Find user
      const matched = DEFAULT_USERS.find((u) => u.email === email);
      if (matched) {
        setCurrentUser(matched);
      }
      setIsAuthModalOpen(false);
      return true;
    } catch (err) {
      setAuthError('Connection error contacting server');
      return false;
    }
  };

  // Switch Teammate (1-click test authentication)
  const switchTeammate = async (user: UserProfile) => {
    setCurrentUser(user);
    setIsUserMenuOpen(false);
    if (user.email) {
      await performLogin(user.email, 'password123');
    }
  };

  // Perform Registration
  const performRegister = async () => {
    setAuthError(null);
    if (!authEmail || !authPassword || !authUsername) {
      setAuthError('All fields required');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: authEmail,
          username: authUsername.toLowerCase(),
          display_name: authDisplayName || authUsername,
          password: authPassword,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
        setAuthError(err.detail || 'Registration failed');
        return;
      }
      await performLogin(authEmail, authPassword);
    } catch {
      setAuthError('Error communicating with server');
    }
  };

  // Handle Logout
  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setAccessToken(null);
    setIsUserMenuOpen(false);
    setIsAuthModalOpen(true);
  };

  // Ensure default login on initial mount if not authenticated
  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        // Auto-login Zoe Maxwell for initial seamless experience
        await performLogin('zoe@acme.com', 'password123');
      }
    };
    void initAuth();
    void resolveDeviceId().then((id) => setDeviceId(id));
  }, []);

  // Load Channels & Messages from Backend
  const loadWorkspaceData = async () => {
    try {
      setLoading(true);
      const [chRes, msgRes, rxRes] = await Promise.all([
        apiFetch('/api/v1/channels'),
        apiFetch('/api/v1/messages'),
        apiFetch('/api/v1/reactions'),
      ]);

      if (chRes.ok && Array.isArray(chRes.data) && chRes.data.length > 0) {
        setChannels(chRes.data as Channel[]);
        if (!selectedChannelId && chRes.data.length > 0) {
          setSelectedChannelId((chRes.data[0] as Channel).id);
        }
      }
      if (msgRes.ok && Array.isArray(msgRes.data)) {
        setMessages(msgRes.data as MessageItem[]);
      }
      if (rxRes.ok && Array.isArray(rxRes.data)) {
        setReactions(rxRes.data as ReactionItem[]);
      }
    } catch (err) {
      console.warn('Workspace load notice:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (accessToken) {
      void loadWorkspaceData();
    }
  }, [accessToken]);

  // Connect Realtime Client
  useEffect(() => {
    const client = new RealtimeClient();
    realtimeClientRef.current = client;
    const unsubStatus = client.onStatusChange((status) => setConnStatus(status));
    const token = accessToken ?? localStorage.getItem('access_token');
    client.connect(getRealtimeUrl(currentUser.id, token));

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
        created_at: p.created_at ? String(p.created_at) : new Date().toISOString(),
      };

      setMessages((prev) => {
        if (prev.some((m) => m.id === nextMsg.id || (nextMsg.client_message_id && m.client_message_id === nextMsg.client_message_id))) {
          return prev.map((m) => (m.client_message_id === nextMsg.client_message_id ? nextMsg : m));
        }
        return [...prev, nextMsg];
      });

      if (activeThreadMessage && nextMsg.thread_id === activeThreadMessage.id) {
        setThreadReplies((prev) => {
          if (prev.some((m) => m.id === nextMsg.id)) return prev;
          return [...prev, nextMsg];
        });
      }
    });

    client.on('message.updated', (event: RealtimeEvent) => {
      const p = event.payload;
      setMessages((prev) =>
        prev.map((m) => (m.id === p.message_id ? { ...m, body: String(p.body), updated_at: p.updated_at ? String(p.updated_at) : new Date().toISOString() } : m)),
      );
    });

    client.on('message.deleted', (event: RealtimeEvent) => {
      const p = event.payload;
      setMessages((prev) => prev.filter((m) => m.id !== p.message_id));
      setThreadReplies((prev) => prev.filter((m) => m.id !== p.message_id));
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

    client.on('typing.started', (event: RealtimeEvent) => {
      const p = event.payload;
      if (p.client_id && p.client_id !== currentUser.id) {
        const author = getUser(String(p.client_id));
        setTypingUsers((prev) => new Map(prev).set(String(p.client_id), author.name));
      }
    });

    client.on('typing.stopped', (event: RealtimeEvent) => {
      const p = event.payload;
      if (p.client_id) {
        setTypingUsers((prev) => {
          const next = new Map(prev);
          next.delete(String(p.client_id));
          return next;
        });
      }
    });

    return () => {
      unsubStatus();
      client.disconnect();
    };
  }, [currentUser.id, accessToken, activeThreadMessage?.id]);

  // Read / Write Saved Drafts
  useEffect(() => {
    if (!deviceId) return;
    void readDraft(`${deviceId}:${currentConversationId}`).then((saved) => setDraft(saved || ''));
  }, [deviceId, currentConversationId]);

  useEffect(() => {
    if (!deviceId) return;
    void writeDraft(`${deviceId}:${currentConversationId}`, draft);
  }, [draft, deviceId, currentConversationId]);

  // Auto Scroll
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
      await apiFetch('/api/v1/messages', {
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
      await apiFetch('/api/v1/messages', {
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
        await apiFetch(`/api/v1/reactions/${messageId}/${currentUser.id}/${encodeURIComponent(emoji)}`, {
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
        await apiFetch('/api/v1/reactions', {
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

  // Edit Message
  const handleSaveEdit = async (messageId: string) => {
    if (!editingBody.trim()) return;
    try {
      await apiFetch(`/api/v1/messages/${messageId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: editingBody.trim() }),
      });
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, body: editingBody.trim(), updated_at: new Date().toISOString() } : m)),
      );
      setEditingMessageId(null);
    } catch (err) {
      console.warn('Failed to edit message:', err);
    }
  };

  // Delete Message
  const handleDeleteMessage = async (messageId: string) => {
    if (!confirm('Are you sure you want to delete this message?')) return;
    try {
      await apiFetch(`/api/v1/messages/${messageId}`, { method: 'DELETE' });
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
    } catch (err) {
      console.warn('Failed to delete message:', err);
    }
  };

  // Create Channel
  const handleCreateChannel = async () => {
    if (!newChannelName.trim()) return;
    const clean = newChannelName.trim().toLowerCase().replace(/\s+/g, '-');
    try {
      const response = await apiFetch('/api/v1/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: DEFAULT_WORKSPACE_ID,
          name: clean,
          topic: newChannelTopic.trim() || `Channel for #${clean}`,
          is_private: newChannelIsPrivate,
        }),
      });
      if (response.ok) {
        const created = response.data as Channel;
        setChannels((prev) => [...prev, created]);
        setSelectedChannelId(created.id);
        setSelectedDmUser(null);
        setNewChannelName('');
        setNewChannelTopic('');
        setNewChannelIsPrivate(false);
        setIsCreateChannelOpen(false);
      }
    } catch (err) {
      console.warn('Create channel error:', err);
    }
  };

  // File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('workspace_id', DEFAULT_WORKSPACE_ID);

    try {
      const token = accessToken ?? localStorage.getItem('access_token');
      const res = await fetch(`${API_BASE}/api/v1/files/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (res.ok) {
        const fileData = await res.json();
        // Post message with file reference
        const fileMsg = `📎 **Attachment:** [${fileData.filename}] (${(fileData.size_bytes / 1024).toFixed(1)} KB)`;
        setDraft(fileMsg);
      } else {
        alert('File upload failed: File exceeds limit or invalid format.');
      }
    } catch (err) {
      console.warn('Upload error:', err);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Direct Message Selection
  const selectDm = async (user: UserProfile) => {
    setSelectedDmUser(user);
    try {
      const res = await apiFetch('/api/v1/conversations/direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: DEFAULT_WORKSPACE_ID,
          recipient_id: user.id,
        }),
      });
      if (res.ok) {
        const conv = res.data as { id: string };
        setCurrentDmConversationId(conv.id);
      }
    } catch {
      setCurrentDmConversationId(`dm-${user.id}`);
    }
  };

  // Typing Emitter
  const handleTyping = (text: string) => {
    setDraft(text);
    if (!realtimeClientRef.current) return;
    realtimeClientRef.current.send({ event_type: 'typing.start', payload: { channel_id: currentConversationId } });

    if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
    typingTimerRef.current = window.setTimeout(() => {
      realtimeClientRef.current?.send({ event_type: 'typing.stop', payload: { channel_id: currentConversationId } });
    }, 1500);
  };

  // AI Summarize
  const handleAiSummarize = async () => {
    setIsAiLoading(true);
    setAiSummary(null);
    try {
      const res = await apiFetch('/api/v1/ai/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_id: activeChannel?.id ?? 'ch-social-media' }),
      });
      if (res.ok) {
        setAiSummary(res.data as { summary?: string; key_points?: string[]; action_items?: string[] });
      }
    } catch {
      // AI summary notice
    } finally {
      setIsAiLoading(false);
    }
  };

  // Load Admin Data
  const loadAdminData = async () => {
    setIsAdminOpen(true);
    setAdminNotice(null);
    const [statsRes, memRes, auditRes] = await Promise.all([
      apiFetch('/api/v1/admin/stats'),
      apiFetch('/api/v1/admin/members'),
      apiFetch('/api/v1/admin/audit-logs'),
    ]);

    if (statsRes.ok) setAdminStats(statsRes.data as AdminStats);
    if (memRes.ok) setAdminMembers(memRes.data as MemberItem[]);
    if (auditRes.ok) setAdminAuditLogs(auditRes.data as AuditLogEntry[]);
  };

  // Update Member Role (Admin)
  const handleRoleChange = async (targetUserId: string, newRole: string) => {
    setAdminNotice(null);
    try {
      const res = await apiFetch(`/api/v1/admin/members/${targetUserId}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      });
      if (res.ok) {
        setAdminNotice(`Role updated to ${newRole}`);
        setAdminMembers((prev) => prev.map((m) => (m.id === targetUserId ? { ...m, role: newRole } : m)));
      } else {
        const err = res.data as { detail?: string };
        setAdminNotice(`Error: ${err.detail || 'Could not update role'}`);
      }
    } catch {
      setAdminNotice('Error contacting admin API');
    }
  };

  // Search Execute
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      const q = searchQuery.toLowerCase();
      const localChannels = channels
        .filter((c) => c.name.toLowerCase().includes(q))
        .map((c) => ({ id: c.id, type: 'channel', title: `#${c.name}`, subtitle: c.topic || 'Channel' }));

      const localUsers = DEFAULT_USERS
        .filter((u) => u.name.toLowerCase().includes(q) || u.handle.toLowerCase().includes(q))
        .map((u) => ({ id: u.id, type: 'user', title: u.name, subtitle: `${u.handle} • ${u.role}` }));

      let apiMsgResults: { id: string; type: string; title: string; subtitle: string; channel_id?: string }[] = [];
      try {
        const res = await apiFetch(`/api/v1/search/messages?query=${encodeURIComponent(searchQuery)}`);
        if (res.ok && res.data && typeof res.data === 'object' && 'results' in res.data) {
          const resObj = res.data as { results: { message_id: string; snippet: string; channel_id: string }[] };
          apiMsgResults = resObj.results.map((r) => ({
            id: r.message_id,
            type: 'message',
            title: r.snippet,
            subtitle: `In channel: ${r.channel_id}`,
            channel_id: r.channel_id,
          }));
        }
      } catch {
        // fallback to local matches
      }

      setSearchResults([...localChannels, ...localUsers, ...apiMsgResults]);
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, channels]);

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
        setIsAdminOpen(false);
        setIsAuthModalOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

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
      {/* Hidden file input */}
      <input type="file" ref={fileInputRef} style={{ display: 'none' }} onChange={(e) => void handleFileUpload(e)} />

      {/* =========================================================
         1. TOP BAR (Dusty Mauve Slack Header)
      ========================================================= */}
      <header className="top-header">
        <div className="top-header-left">
          <button className="top-nav-btn" title="Menu" onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}>☰</button>
          <div className="top-arrows-group">
            <button className="top-nav-btn" title="Back">←</button>
            <button className="top-nav-btn" title="Forward">→</button>
          </div>
        </div>

        <div className="top-search-center">
          <div className="top-search-pill" onClick={() => setIsSearchOpen(true)}>
            <span className="search-icon-svg">🔍</span>
            <span className="search-text">Search Acme Inc (Ctrl+K)</span>
          </div>
        </div>

        <div className="top-header-right">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginRight: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: '#fff', opacity: 0.9 }}>
              {connStatus === 'ONLINE' ? '🟢 Online' : connStatus === 'CONNECTING' ? '🟡 Connecting' : '🔴 Offline'}
            </span>
          </div>
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
            onClick={() => void loadAdminData()}
            title="Admin & More"
          >
            <div className="rail-icon-box">⚙️</div>
            <span className="rail-label">Admin</span>
          </button>

          <div className="rail-bottom">
            <button className="rail-add-btn" onClick={() => setIsCreateChannelOpen(true)} title="Add Channel">+</button>

            {/* Current User Avatar with Status Indicator */}
            <div
              className="user-avatar-rail"
              onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
              title={`${currentUser.name} (${currentUser.role}) • Click to manage account`}
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
            <button className="sidebar-filter-btn" onClick={() => void loadWorkspaceData()} title="Refresh data">🔄</button>
          </div>

          <div className="sidebar-scroll-area">
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
                {DEFAULT_USERS.map((u) => {
                  const isSelected = selectedDmUser?.id === u.id;
                  return (
                    <li key={u.id}>
                      <button
                        className={`sidebar-nav-item ${isSelected ? 'active' : ''}`}
                        onClick={() => void selectDm(u)}
                      >
                        <div className="dm-avatar-mini" style={{ background: u.avatarBg, display: 'grid', placeItems: 'center', color: '#fff', fontSize: '0.7rem' }}>
                          {u.name.charAt(0)}
                        </div>
                        <span className="sidebar-item-name">{u.name}</span>
                        {u.id === currentUser.id && <span style={{ fontSize: '0.7rem', opacity: 0.6 }}>(you)</span>}
                      </button>
                    </li>
                  );
                })}
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
                {activeChannel?.is_private && <span style={{ fontSize: '0.8rem' }}>🔒</span>}
              </div>
              <div className="channel-topic-text">
                {selectedDmUser ? `${selectedDmUser.handle} • ${selectedDmUser.role}` : (activeChannel?.topic || 'Track and coordinate social media')}
              </div>
            </div>

            <div className="channel-header-right">
              {/* AI Copilot Button */}
              <button
                className="comp-icon-btn"
                style={{ width: 'auto', padding: '0 10px', height: '28px', borderRadius: '14px', background: '#f5eff7', border: '1px solid #d9c7d7', fontWeight: 600, fontSize: '0.8rem' }}
                onClick={() => void handleAiSummarize()}
                title="Summarize channel with AI Copilot"
              >
                ✨ AI Summarize
              </button>

              {/* Huddle Button */}
              <button
                className={`huddle-pill-btn ${isHuddleActive ? 'active' : ''}`}
                onClick={() => setIsHuddleActive(!isHuddleActive)}
                title="Start or join a live huddle"
              >
                <span>🎧</span>
                <span>{isHuddleActive ? 'In Huddle' : 'Huddle'}</span>
              </button>
            </div>
          </header>

          {/* AI Summary Banner if present */}
          {isAiLoading && (
            <div className="ai-summary-card" style={{ margin: '12px 20px 0' }}>
              <div className="ai-summary-title">✨ AI Copilot is analyzing channel conversations...</div>
            </div>
          )}
          {aiSummary && (
            <div className="ai-summary-card" style={{ margin: '12px 20px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="ai-summary-title">✨ AI Channel Summary</div>
                <button className="top-nav-btn" style={{ color: '#522653' }} onClick={() => setAiSummary(null)}>✕</button>
              </div>
              <p style={{ fontSize: '0.88rem', marginBottom: '8px' }}>{aiSummary.summary}</p>
              {aiSummary.key_points && (
                <div>
                  <strong style={{ fontSize: '0.8rem' }}>Key Points:</strong>
                  <ul style={{ paddingLeft: '18px', fontSize: '0.82rem', marginTop: '4px' }}>
                    {aiSummary.key_points.map((pt, i) => <li key={i}>{pt}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Messages Stream */}
          <div className="messages-container">
            {loading ? (
              <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading real conversation data...</div>
            ) : conversationMessages.length === 0 ? (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-dim)' }}>
                <h3>No messages here yet!</h3>
                <p style={{ marginTop: '6px', fontSize: '0.9rem' }}>Say hello to start the conversation.</p>
              </div>
            ) : (
              conversationMessages.map((msg) => {
                const author = getUser(msg.author_id);
                const msgRx = getGroupedReactions(msg.id);
                const isAuthorOrAdmin = msg.author_id === currentUser.id || currentUser.role === 'admin';
                const isEditing = editingMessageId === msg.id;

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
                        {msg.updated_at && <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>(edited)</span>}
                      </div>

                      {isEditing ? (
                        <div className="msg-edit-wrap">
                          <textarea
                            className="msg-edit-textarea"
                            value={editingBody}
                            onChange={(e) => setEditingBody(e.target.value)}
                            rows={2}
                          />
                          <div className="msg-edit-actions">
                            <button className="comp-send-btn" onClick={() => void handleSaveEdit(msg.id)}>Save</button>
                            <button className="user-option-btn" style={{ width: 'auto' }} onClick={() => setEditingMessageId(null)}>Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <div className="msg-content-text">{msg.body}</div>
                      )}

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
                      <button className="toolbar-btn" onClick={() => setActiveThreadMessage(msg)} title="Reply in thread">💬</button>
                      {isAuthorOrAdmin && (
                        <>
                          <button className="toolbar-btn" onClick={() => { setEditingMessageId(msg.id); setEditingBody(msg.body); }} title="Edit message">✎</button>
                          <button className="toolbar-btn" onClick={() => void handleDeleteMessage(msg.id)} title="Delete message">🗑</button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Typing Indicator */}
          <div className="typing-indicator-bar">
            {typingUsers.size > 0 && `${Array.from(typingUsers.values()).join(', ')} is typing...`}
          </div>

          {/* =========================================================
             3. COMPOSER BOX
          ========================================================= */}
          <div className="composer-box">
            <div className="composer-border-wrap">
              <textarea
                className="composer-textarea"
                placeholder={selectedDmUser ? `Message ${selectedDmUser.name}` : `Message #${activeChannel?.name ?? 'social-media'}`}
                value={draft}
                onChange={(e) => handleTyping(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    void handleSendMessage();
                  }
                }}
              />

              {/* Bottom Toolbar: +, 😀, @, Aa, Upload, Send Button */}
              <div className="composer-bottom-toolbar">
                <div className="composer-tools-left">
                  <button className="comp-icon-btn" onClick={() => fileInputRef.current?.click()} title="Upload file attachment">+</button>
                  <button className="comp-icon-btn" onClick={() => setShowEmojiPicker(!showEmojiPicker)} title="Add emoji">😀</button>
                  <button className="comp-icon-btn" onClick={() => setDraft((d) => `${d} @`)} title="Mention someone">@</button>
                  <button className="comp-icon-btn" onClick={() => setDraft((d) => `**${d}**`)} title="Bold formatting">Aa</button>
                </div>

                <div className="composer-tools-right">
                  <button
                    className="comp-send-btn"
                    onClick={() => void handleSendMessage()}
                    disabled={!draft.trim()}
                    title="Send message (Enter)"
                  >
                    <span>✈</span>
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

      {/* User Switcher / Account Dropdown */}
      {isUserMenuOpen && (
        <div className="user-menu-popover">
          <div style={{ padding: '4px 6px 8px', borderBottom: '1px solid var(--slack-border)' }}>
            <div style={{ fontWeight: 800, fontSize: '0.92rem' }}>Active: {currentUser.name}</div>
            <small style={{ color: 'var(--text-muted)' }}>Role: {currentUser.role}</small>
          </div>

          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', margin: '4px 0 2px' }}>SWITCH USER (AUTO-LOGIN)</div>
          {DEFAULT_USERS.map((user) => (
            <button
              key={user.id}
              className={`user-option-btn ${user.id === currentUser.id ? 'active' : ''}`}
              onClick={() => void switchTeammate(user)}
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

          <div style={{ borderTop: '1px solid var(--slack-border)', paddingTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <button className="user-option-btn" onClick={() => { setIsUserMenuOpen(false); void loadAdminData(); }}>
              <span>⚙️</span>
              <span>Workspace Administration</span>
            </button>
            <button className="user-option-btn" onClick={() => { setIsUserMenuOpen(false); setIsAuthModalOpen(true); }}>
              <span>🔑</span>
              <span>Sign In with another Account</span>
            </button>
            <button className="user-option-btn" style={{ color: '#e11d48' }} onClick={handleLogout}>
              <span>🚪</span>
              <span>Log out</span>
            </button>
          </div>
        </div>
      )}

      {/* Authentication Modal */}
      {isAuthModalOpen && (
        <div className="modal-overlay" onClick={() => setIsAuthModalOpen(false)}>
          <div className="modal-card" style={{ maxWidth: '440px' }} onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">{authTab === 'login' ? 'Sign In to Acme Inc' : 'Create an Account'}</h2>
            <div className="auth-tabs">
              <button className={`auth-tab-btn ${authTab === 'login' ? 'active' : ''}`} onClick={() => setAuthTab('login')}>Sign In</button>
              <button className={`auth-tab-btn ${authTab === 'register' ? 'active' : ''}`} onClick={() => setAuthTab('register')}>Register</button>
            </div>

            {authError && (
              <div style={{ background: '#fee2e2', color: '#b91c1c', padding: '8px 12px', borderRadius: '4px', fontSize: '0.85rem' }}>
                {authError}
              </div>
            )}

            {authTab === 'login' ? (
              <form className="auth-form" onSubmit={(e) => { e.preventDefault(); void performLogin(authEmail, authPassword); }}>
                <span className="auth-form-label">Email</span>
                <input
                  type="email"
                  className="modal-input"
                  placeholder="name@work-email.com"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  required
                />
                <span className="auth-form-label">Password</span>
                <input
                  type="password"
                  className="modal-input"
                  placeholder="Enter your password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  required
                />
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
                  <button type="button" className="user-option-btn" style={{ width: 'auto' }} onClick={() => setIsAuthModalOpen(false)}>Cancel</button>
                  <button type="submit" className="comp-send-btn">Sign In</button>
                </div>
              </form>
            ) : (
              <form className="auth-form" onSubmit={(e) => { e.preventDefault(); void performRegister(); }}>
                <span className="auth-form-label">Email</span>
                <input
                  type="email"
                  className="modal-input"
                  placeholder="name@work-email.com"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  required
                />
                <span className="auth-form-label">Username</span>
                <input
                  type="text"
                  className="modal-input"
                  placeholder="username"
                  value={authUsername}
                  onChange={(e) => setAuthUsername(e.target.value)}
                  required
                />
                <span className="auth-form-label">Display Name</span>
                <input
                  type="text"
                  className="modal-input"
                  placeholder="Full Name"
                  value={authDisplayName}
                  onChange={(e) => setAuthDisplayName(e.target.value)}
                />
                <span className="auth-form-label">Password</span>
                <input
                  type="password"
                  className="modal-input"
                  placeholder="Choose password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  required
                />
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
                  <button type="button" className="user-option-btn" style={{ width: 'auto' }} onClick={() => setIsAuthModalOpen(false)}>Cancel</button>
                  <button type="submit" className="comp-send-btn">Create Account</button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Global Search Modal (Ctrl+K) */}
      {isSearchOpen && (
        <div className="modal-overlay" onClick={() => setIsSearchOpen(false)}>
          <div className="modal-card" style={{ maxWidth: '620px' }} onClick={(e) => e.stopPropagation()}>
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
            <div style={{ maxHeight: '340px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '10px' }}>
              {searchResults.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                  {searchQuery ? 'No results found.' : 'Type to search across channels, messages, and teammates.'}
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
                        const target = DEFAULT_USERS.find((u) => u.id === item.id);
                        if (target) void selectDm(target);
                      } else if (item.type === 'message' && item.channel_id) {
                        setSelectedChannelId(item.channel_id);
                        setSelectedDmUser(null);
                      }
                      setIsSearchOpen(false);
                      setSearchQuery('');
                    }}
                  >
                    <span>{item.type === 'channel' ? '#' : item.type === 'message' ? '💬' : '👤'}</span>
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
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.88rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={newChannelIsPrivate}
                onChange={(e) => setNewChannelIsPrivate(e.target.checked)}
              />
              <span>Make private (restricted to invited members)</span>
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
              <button className="user-option-btn" style={{ width: 'auto' }} onClick={() => setIsCreateChannelOpen(false)}>Cancel</button>
              <button className="comp-send-btn" onClick={() => void handleCreateChannel()} disabled={!newChannelName.trim()}>Create</button>
            </div>
          </div>
        </div>
      )}

      {/* Admin Console Modal */}
      {isAdminOpen && (
        <div className="modal-overlay" onClick={() => setIsAdminOpen(false)}>
          <div className="modal-card admin-modal-card" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="modal-title">Workspace Administration</h2>
              <button className="thread-close-btn" onClick={() => setIsAdminOpen(false)}>✕</button>
            </div>

            {adminNotice && (
              <div style={{ padding: '8px 12px', background: '#f3e8ff', color: '#6b21a8', borderRadius: '4px', fontSize: '0.85rem' }}>
                {adminNotice}
              </div>
            )}

            <div className="auth-tabs">
              <button className={`auth-tab-btn ${adminTab === 'stats' ? 'active' : ''}`} onClick={() => setAdminTab('stats')}>Overview Stats</button>
              <button className={`auth-tab-btn ${adminTab === 'members' ? 'active' : ''}`} onClick={() => setAdminTab('members')}>Members & Roles</button>
              <button className={`auth-tab-btn ${adminTab === 'audit' ? 'active' : ''}`} onClick={() => setAdminTab('audit')}>Audit Logs</button>
            </div>

            {adminTab === 'stats' && adminStats && (
              <div className="admin-stats-grid">
                <div className="admin-stat-card">
                  <div className="admin-stat-val">{adminStats.total_users}</div>
                  <div className="admin-stat-label">Active Users</div>
                </div>
                <div className="admin-stat-card">
                  <div className="admin-stat-val">{adminStats.total_channels}</div>
                  <div className="admin-stat-label">Channels</div>
                </div>
                <div className="admin-stat-card">
                  <div className="admin-stat-val">{adminStats.total_messages}</div>
                  <div className="admin-stat-label">Messages</div>
                </div>
                <div className="admin-stat-card">
                  <div className="admin-stat-val">{adminStats.total_files}</div>
                  <div className="admin-stat-label">Files Uploaded</div>
                </div>
              </div>
            )}

            {adminTab === 'members' && (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Current Role</th>
                      <th>Change Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adminMembers.map((m) => (
                      <tr key={m.id}>
                        <td><strong>{m.display_name}</strong> (@{m.username})</td>
                        <td>{m.email}</td>
                        <td><span className="app-badge" style={{ background: m.role === 'admin' ? '#7d5277' : '#616061' }}>{m.role}</span></td>
                        <td>
                          <select
                            className="admin-role-select"
                            value={m.role}
                            onChange={(e) => void handleRoleChange(m.id, e.target.value)}
                            disabled={currentUser.role !== 'admin'}
                          >
                            <option value="admin">admin</option>
                            <option value="member">member</option>
                            <option value="guest">guest</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {adminTab === 'audit' && (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Action</th>
                      <th>Actor</th>
                      <th>Target</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adminAuditLogs.length === 0 ? (
                      <tr><td colSpan={4} style={{ textAlign: 'center', padding: '20px' }}>No audit logs recorded yet.</td></tr>
                    ) : (
                      adminAuditLogs.map((log) => (
                        <tr key={log.id}>
                          <td>{new Date(log.timestamp).toLocaleString()}</td>
                          <td><code>{log.action}</code></td>
                          <td>{log.actor_id}</td>
                          <td>{log.target_id || '—'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
