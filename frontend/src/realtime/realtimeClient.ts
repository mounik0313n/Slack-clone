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

export class RealtimeClient {
  private socket: WebSocket | null = null;
  private listeners = new Map<string, Set<(event: RealtimeEvent) => void>>();
  private sendQueue: string[] = [];

  connect(url: string) {
    try {
      this.socket = new WebSocket(url);
    } catch (e) {
      console.warn('Failed to construct WebSocket with URL:', url, e);
      return;
    }

    this.socket.addEventListener('open', () => {
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

    this.socket.addEventListener('error', (err) => {
      console.warn('Realtime socket error:', err);
    });
  }

  on(eventType: string, handler: (event: RealtimeEvent) => void) {
    const handlers = this.listeners.get(eventType) ?? new Set();
    handlers.add(handler);
    this.listeners.set(eventType, handlers);
  }

  disconnect() {
    this.sendQueue = [];
    if (this.socket) {
      try {
        this.socket.close();
      } catch {
        // ignore
      }
      this.socket = null;
    }
  }

  send(event: RealtimeEvent) {
    if (!this.socket) {
      return;
    }
    const payload = JSON.stringify(event);
    if (this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(payload);
      } catch {
        // ignore
      }
    } else if (this.socket.readyState === WebSocket.CONNECTING) {
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
