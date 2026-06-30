# backend — FastAPI Python Backend

Hybrid-transport FastAPI server serving on Unix socket (`/run/holmium/backend.sock`) for local TUI and HTTPS (`0.0.0.0:8765`) for remote clients over WireGuard.

- `server.py` — FastAPI app entrypoint
- `routes/` — API route handlers
- `middleware/` — auth, CORS, error handling
- Self-signed TLS cert for HTTPS
