# API

The backend exposes the public API under `/api/v1`.

## Routes

- `/api/v1/auth`
- `/api/v1/organizations`
- `/api/v1/workspaces`
- `/api/v1/channels`
- `/api/v1/messages`
- `/api/v1/search`
- `/api/v1/notifications`
- `/api/v1/apps`
- `/api/v1/admin`
- `/api/v1/ai`

## Error format

```json
{
  "error": {
    "code": "MESSAGE_NOT_FOUND",
    "message": "Message not found",
    "details": {}
  }
}
```

## Pagination

High-volume endpoints use cursor-based pagination with `limit` and `cursor` semantics instead of large offset queries.
