# Realtime and WebSocket

The realtime layer authenticates clients, manages subscriptions, and replays missed events on reconnect. The protocol supports heartbeat, ack, resubscribe, replay, deduplication, and backpressure handling.

## Core concepts

- subscription-based delivery
- per-conversation sequence tracking
- replay after reconnect
- durable event ids for deduplication
- server-authoritative ordering

The frontend uses a dedicated realtime client wrapper with backoff and resume support.
