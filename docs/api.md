# External API Key System

Holmium supports API keys for external scripts to authenticate without the primary token.

## Creating an API Key

```bash
holmium --key create my-script
# Output: API key created: tmy_abc123def456...
# Save this key — it will not be shown again.
```

Via FastAPI:
```bash
curl -X POST https://10.0.0.1:8765/keys/create \
  -H "X-Holmium-Token: <primary-token>" \
  -H "Content-Type: application/json" \
  -d '{"label": "my-script"}'
```

Response:
```json
{"label": "my-script", "key": "tmy_abc123def456...", "created_at": "2026-06-28T12:00:00"}
```

## Using an API Key

Include the API key in the `X-Holmium-Token` header (same as primary token):

```bash
curl https://10.0.0.1:8765/status \
  -H "X-Holmium-Token: tmy_abc123def456..."
```

## Listing Keys

```bash
holmium --key list
```

Via API:
```bash
curl https://10.0.0.1:8765/keys/list \
  -H "X-Holmium-Token: <primary-token>"
```

Response:
```json
[
  {"label": "my-script", "created_at": "2026-06-28T12:00:00", "last_used": "2026-06-28T14:00:00", "enabled": true}
]
```

## Revoking a Key

```bash
holmium --key revoke my-script
```

Via API:
```bash
curl -X DELETE https://10.0.0.1:8765/keys/my-script \
  -H "X-Holmium-Token: <primary-token>"
```

## Storage

- Keys stored as SHA-256 hashes in SQLite `api_keys` table
- Raw key shown once at creation time
- `last_used` timestamp updated on each request
- Revoked keys are deleted from the database

## Authentication Flow

`require_token` FastAPI dependency:
1. Check `X-Holmium-Token` header
2. Compare with primary token via `hmac.compare_digest`
3. If no match, hash the provided key and check `api_keys` table
4. If match found, update `last_used` timestamp
5. If no match, return 403 Forbidden

## Use Cases

- CI/CD pipelines sending data to Holmium
- cron scripts querying Holmium's status
- Home Assistant automations
- Custom automation scripts
