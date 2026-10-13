export type RealtimeEvent = {
  event_id?: string;
  event_type?: string;
  type?: string;
  event_version?: number;
  payload: Record<string, unknown>;
  workspace_id?: string;
  conversation_id?: string;
  sequence?: number | null;
  channels?: string[];
};

export type ConnectionStatus = 'ONLINE' | 'CONNECTING' | 'OFFLINE';

export class RealtimeClient {
  private socket: WebSocket | null = null;
  private listeners = new Map<string, Set<(event: RealtimeEvent) => void>>();
  private statusListeners = new Set<(status: ConnectionStatus) => void>();
  private sendQueue: string[] = [];
  private url: string = '';
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private isExplicitDisconnect = false;

  connect(url: string) {
    this.url = url;
    this.isExplicitDisconnect = false;
    this.emitStatus('CONNECTING');

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    try {
      this.socket = new WebSocket(url);
    } catch (e) {
      console.warn('Failed to construct WebSocket with URL:', url, e);
      this.emitStatus('OFFLINE');
      this.scheduleReconnect();
      return;
    }

    this.socket.addEventListener('open', () => {
      this.emitStatus('ONLINE');
      this.startHeartbeat();

      while (this.sendQueue.length > 0) {
        const item = this.sendQueue.shift();
        if (item && this.socket?.readyState === WebSocket.OPEN) {
          try {
            this.socket.send(item);
          } catch {
            // ignore
          }
        }
      }
    });

    this.socket.addEventListener('message', (event) => {
      try {
        const nextEvent = JSON.parse(event.data) as RealtimeEvent;
        const eventType = nextEvent.event_type ?? nextEvent.type;
        if (!eventType) {
          return;
        }
        const handlers = this.listeners.get(eventType) ?? new Set();
        handlers.forEach((handler) => handler(nextEvent));
      } catch {
        // Ignore malformed realtime payloads.
      }
    });

    this.socket.addEventListener('close', () => {
      this.stopHeartbeat();
      if (!this.isExplicitDisconnect) {
        this.emitStatus('OFFLINE');
        this.scheduleReconnect();
      }
    });

    this.socket.addEventListener('error', (err) => {
      console.warn('Realtime socket error:', err);
      this.stopHeartbeat();
      this.emitStatus('OFFLINE');
    });
  }

  private emitStatus(status: ConnectionStatus) {
    this.statusListeners.forEach((listener) => listener(status));
  }

  onStatusChange(listener: (status: ConnectionStatus) => void) {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }

  private scheduleReconnect() {
    if (this.isExplicitDisconnect || this.reconnectTimer) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (this.url && !this.isExplicitDisconnect) {
        this.connect(this.url);
      }
    }, 3000);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        try {
          this.socket.send(JSON.stringify({ event_type: 'ping', payload: {} }));
        } catch {
          // ignore
        }
      }
    }, 25000);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  on(eventType: string, handler: (event: RealtimeEvent) => void) {
    const handlers = this.listeners.get(eventType) ?? new Set();
    handlers.add(handler);
    this.listeners.set(eventType, handlers);
  }

  disconnect() {
    this.isExplicitDisconnect = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.sendQueue = [];
    if (this.socket) {
      try {
        this.socket.close();
      } catch {
        // ignore
      }
      this.socket = null;
    }
    this.emitStatus('OFFLINE');
  }

  send(event: RealtimeEvent) {
    const payload = JSON.stringify(event);
    if (this.socket?.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(payload);
      } catch {
        // ignore
      }
    } else {
      this.sendQueue.push(payload);
    }
  }

  requestSync(payload: Record<string, unknown>) {
    this.send({
      event_type: 'sync.request',
      type: 'sync.request',
      payload,
    });
  }
}
