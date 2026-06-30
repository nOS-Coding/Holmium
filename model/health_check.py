#!/usr/bin/env python3
import httpx
import time
import sys

SOCKET_PATH = "/run/holmium/vllm.sock"
TIMEOUT = 120
RETRY_INTERVAL = 2

transport = httpx.HTTPTransport(uds=SOCKET_PATH)

start = time.time()
while time.time() - start < TIMEOUT:
    try:
        with httpx.Client(transport=transport, timeout=10) as client:
            resp = client.post(
                "http://localhost/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
            )
            if resp.status_code == 200:
                print("[*] vLLM is healthy")
                sys.exit(0)
    except Exception:
        pass
    time.sleep(RETRY_INTERVAL)

print("[-] vLLM health check timed out after 120 seconds", file=sys.stderr)
sys.exit(1)
