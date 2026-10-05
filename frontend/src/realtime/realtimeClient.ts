export type RealtimeEvent = {
  event_id?: string;
  event_type?: string;
  type?: string;
  event_version?: number;
  payload: Record<string, unknown>;
  workspace_id?: string;
  conversation_id?: string;
  sequence?: number | null;
};

export class RealtimeClient {
  private socket: WebSocket | null = null;
  private listeners = new Map<string, Set<(event: RealtimeEvent) => void>>();

  connect(url: string) {
    this.socket = new WebSocket(url);
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
  }

  on(eventType: string, handler: (event: RealtimeEvent) => void) {
    const handlers = this.listeners.get(eventType) ?? new Set();
    handlers.add(handler);
    this.listeners.set(eventType, handlers);
  }

  disconnect() {
    this.socket?.close();
    this.socket = null;
  }

  send(event: RealtimeEvent) {
    if (!this.socket) {
      return;
    }
    this.socket.send(JSON.stringify(event));
  }

  requestSync(payload: Record<string, unknown>) {
    this.send({
      event_type: 'sync.request',
      type: 'sync.request',
      payload,
    });
  }
}
