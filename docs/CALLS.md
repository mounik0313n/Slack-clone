# Calls and media

Audio and video traffic uses WebRTC with LiveKit or a compatible self-hosted media stack. FastAPI handles authorization and room lifecycle rather than relaying media itself.

## Call features

- audio and video rooms
- screen sharing
- moderation controls
- recording metadata
- participant state synchronization
- room permissions and security boundaries

The signaling and room orchestration remain server-authoritative while media is proxied by the WebRTC stack.
