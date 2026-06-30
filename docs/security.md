# Security Model

## Principle

Holmium is a private, single-user system. No public ports, no cloud dependencies.
WireGuard is the only ingress.

## Network Security

- **No public ports**: All services listen on WireGuard subnet or localhost
- **WireGuard**: Only ingress. UDP port 51820. Subnet 10.0.0.0/24.
- **TLS**: HTTPS with self-signed cert over WireGuard (WG already encrypts transport)
- **DNS**: Optional local DNS via Pi at 10.0.0.4

## Authentication

### Primary Token
- `/etc/holmium/token` — 256-bit hex string, root-only
- Required on every API endpoint via `X-Holmium-Token` header
- HMAC comparison via `hmac.compare_digest` (timing-safe)
- Stored in `~/.netsh/hosts.json` (chmod 600) on macOS
- Stored in Android EncryptedSharedPreferences

### API Keys
- Secondary auth for external scripts
- SHA-256 hash stored in SQLite `api_keys` table
- Raw key shown once at creation → must be saved by user
- Works with `require_token` dependency (accepts either primary or API key)

## Transport

- **Unix socket** (`/run/holmium/backend.sock`): local TUI communication
- **HTTPS** (`0.0.0.0:8765`): remote clients over WireGuard
- **TLS**: Self-signed cert from `wireguard/gen_cert.sh` (10-year validity)
- **WebSocket**: `/ws/chat` for CLI, `/notifications/ws` for Mac daemon

## Data Storage

| Data | Storage | Encryption |
|------|---------|------------|
| Config | `/etc/holmium/config.json` | Root permissions only |
| Token | `/etc/holmium/token` | 600 permissions |
| Secrets | `/etc/holmium/secrets.env` | Root only |
| Vault | `/var/holmium/vault.enc` | Fernet + PBKDF2 |
| Android settings | EncryptedSharedPreferences | AES-256 |
| Memory | `/var/holmium/memory/` | Filesystem permissions |
| Sessions | `/var/holmium/sessions/` | Holmium user only |

## File Permissions

```
/etc/holmium/          root:holmium   750
/etc/holmium/token     root:root    600
/etc/holmium/config    root:root    600
/etc/holmium/secrets   root:root    600
/var/holmium/          holmium:holmium  750
~/.netsh/hosts.json  user:user    600
```

## Network Isolation

- Android connects over WireGuard with `AllowedIPs = 0.0.0.0/0` (full tunnel)
- macOS connects with `AllowedIPs = 10.0.0.0/24` (Holmium only)
- All traffic between client and server is inside WG tunnel

## Audit

Every request/response logged to `/var/log/holmium/holmium.log` with timestamp.
API key usage tracked (last_used timestamp).
All tool executions logged in action_history table.
