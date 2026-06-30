# tools — Tool System

JSON TOOL_CALL format tool system. Every capability Holmium has is a tool. Tools are stateless, registered in a registry, and parsed from vLLM stream output.

- `registry.py` — tool registration and dispatch
- `file_ops.py` — file read/write/list tools
- `shell.py` — shell execution tool
- `search.py` — web search tool (DuckDuckGo + SearXNG)
- `image_gen.py` — FLUX.1-schnell image generation
- `media.py` — media control stub (coming soon)
