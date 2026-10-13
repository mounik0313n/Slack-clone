# API Route Coverage & Contract Audit

## Summary of Registered Endpoints
All routes are mounted under the `/api/v1` prefix with the exception of core liveness/readiness probes and the WebSocket endpoint `/ws`.

---

### 1. Health & Liveness
| Method | Path | Description | Auth Required |
|---|---|---|---|
| `GET` | `/` | Service root and API readiness metadata | No |
| `GET` | `/health` | Core health check | No |
| `GET` | `/health/live` | Kubernetes / Container liveness probe | No |
| `GET` | `/health/ready` | Dependency & database readiness probe | No |

---

### 2. Authentication & Identity (`/api/v1/auth`)
| Method | Path | Description | Request Payload | Response | Auth Required |
|---|---|---|---|---|---|
| `POST` | `/auth/register` | Register new user account | `UserRegisterRequest` | `UserResponse` | No (Rate limited) |
| `POST` | `/auth/login` | Authenticate user & issue JWT pair | `UserLoginRequest` | `TokenResponse` | No (Rate limited) |
| `POST` | `/auth/refresh` | Rotate refresh token | `RefreshRequest` | `TokenResponse` | Valid refresh token |
| `GET` | `/auth/me` | Fetch active profile | None | `UserProfile` | Yes (Access token) |
| `POST` | `/auth/logout` | Revoke current tokens | Optional `token` | `{"status": "ok"}` | Yes |
| `POST` | `/auth/password-reset/request`| Initiate password recovery | `PasswordResetRequest` | `{"status": "ok"}` | No |
| `POST` | `/auth/password-reset/confirm`| Complete password reset | `PasswordResetConfirm` | `{"status": "ok"}` | No |

---

### 3. Workspaces & Organizations (`/api/v1/workspaces`, `/api/v1/organizations`)
| Method | Path | Description | Auth Required |
|---|---|---|---|
| `GET` | `/organizations` | List organizations | Optional |
| `POST`| `/organizations` | Create organization | `workspace.manage` |
| `GET` | `/workspaces` | List accessible workspaces | Optional |
| `POST`| `/workspaces` | Create new workspace | `workspace.manage` |

---

### 4. Channels & Conversations (`/api/v1/channels`, `/api/v1/conversations`)
| Method | Path | Description | Auth Required |
|---|---|---|---|
| `GET` | `/channels` | List workspace channels | `channel.read` |
| `POST`| `/channels` | Create channel | `channel.create` |
| `GET` | `/channels/{id}`| Channel details | `channel.read` |
| `GET` | `/conversations` | List user direct & group conversations | `message.read` |
| `POST`| `/conversations` | Create DM or Group DM | `message.create` |

---

### 5. Messaging, Threads & Reactions (`/api/v1/messages`, `/api/v1/threads`, `/api/v1/reactions`)
| Method | Path | Description | Auth Required |
|---|---|---|---|
| `GET` | `/messages` | Query messages with cursor pagination | `message.read` |
| `POST`| `/messages` | Create message (idempotency key supported) | `message.create` |
| `GET` | `/threads/{id}/replies` | List thread replies | `message.read` |
| `GET` | `/reactions` | List emoji reactions | `message.read` |
| `POST`| `/reactions` | Add emoji reaction | `message.create` |
| `DELETE`| `/reactions/{msg_id}/{user_id}/{emoji}` | Remove emoji reaction | Author or admin |

---

### 6. Search, Files, Admin & AI (`/api/v1/search`, `/api/v1/files`, `/api/v1/admin`, `/api/v1/ai`)
| Method | Path | Description | Auth Required |
|---|---|---|---|
| `GET` | `/search/messages` | Search message history by query & channel | `message.read` |
| `POST`| `/files/upload` | Upload file attachment (max 50MB) | `message.create` |
| `GET` | `/files/{file_id}`| Retrieve attachment metadata & link | `message.read` |
| `GET` | `/admin/members` | List members with roles | `member.read` |
| `PATCH`| `/admin/members/{user_id}/role` | Update user role | `workspace.manage` |
| `GET` | `/admin/audit-logs` | Retrieve workspace audit trail | `audit.read` |
| `GET` | `/admin/stats` | Aggregated statistics | Admin role |
| `POST`| `/ai/summarize` | AI channel summary synthesis | Workspace member |
| `POST`| `/ai/query` | Assistant Q&A | Workspace member |

---

### 7. Real-Time Gateway
| Protocol | Path | Supported Events | Auth Required |
|---|---|---|---|
| `WS` | `/ws` | `authenticate`, `subscribe`, `unsubscribe`, `resume`, `ping`, `presence`, `typing.start`, `typing.stop` | Token param or `authenticate` frame |
