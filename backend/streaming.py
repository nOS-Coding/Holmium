"""SSE streaming pipeline — assemble context, stream vLLM, intercept tool calls."""

import json
from typing import Any, AsyncGenerator, Optional

import httpx

from ..tools.executor import execute_tool
from .context import ContextAssembler
from .config import HolmiumConfig
from .logger import get_logger
from .tool_integration import ToolIntegration
from .modes import MODES

logger = get_logger("streaming")


class StreamingPipeline:
    def __init__(
        self,
        config: HolmiumConfig,
        context_assembler: ContextAssembler,
        tool_integration: Optional[ToolIntegration] = None,
    ) -> None:
        self._config = config
        self._assembler = context_assembler
        self._tool_integration = tool_integration or ToolIntegration()

    async def stream_chat(self, user_message: str, session: Any, mode: str = "work") -> AsyncGenerator[str, None]:
        planner = self._assembler.planner
        active_plan = planner.get_active_plan()

        if not active_plan:
            plan_steps = await planner.detect_plan_intent(user_message)
            if plan_steps:
                plan_id = planner.create_plan(user_message, plan_steps)
                yield f"data: {json.dumps({'plan_created': {'id': plan_id, 'steps': plan_steps}})}\n\n"

        messages = self._assembler.assemble(user_message, session, mode=mode)

        mode_config = MODES.get(mode, MODES["work"])
        payload = {
            "model": self._config.vllm_model,
            "messages": messages,
            "stream": True,
            "max_tokens": 4096,
            "temperature": mode_config.temperature,
            "top_p": mode_config.top_p,
        }
        if mode_config.enable_thinking:
            payload["extra_body"] = {"enable_thinking": True}

        transport = httpx.AsyncHTTPTransport(uds=self._config.vllm_socket, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(300.0)) as client:
            async with client.stream(
                "POST",
                "http://localhost/v1/chat/completions",
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    logger.error("vLLM returned %d: %s", resp.status_code, error_body.decode())
                    yield f"data: {json.dumps({'error': f'vLLM error {resp.status_code}'})}\n\n"
                    return

                text_buffer = ""
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if not content:
                        continue

                    text_buffer += content

                    if self._tool_integration.has_pending_tool():
                        self._tool_integration.feed_chunk(content)

                        if self._tool_integration.is_tool_complete():
                            tool_call = self._tool_integration.parse_tool()
                            if tool_call:
                                yield f"data: {json.dumps({'tool_call': tool_call})}\n\n"

                                tool_result = execute_tool(tool_call["name"], tool_call["params"])
                                yield f"data: {json.dumps({'tool_result': tool_result})}\n\n"

                                if tool_result.get("success") and active_plan:
                                    next_step = planner.advance_plan(active_plan["id"])
                                    if next_step:
                                        yield f"data: {json.dumps({'plan_step': next_step})}\n\n"
                                    else:
                                        yield "data: {\"plan_completed\": true}\n\n"
                                elif not tool_result.get("success") and active_plan:
                                    planner.fail_plan(active_plan["id"], str(tool_result.get("error", "unknown")))
                                    yield f"data: {json.dumps({'plan_failed': tool_result.get('error')})}\n\n"

                                inject_msg = {
                                    "role": "tool",
                                    "content": json.dumps(tool_result),
                                    "tool_call_id": tool_call.get("id", ""),
                                }
                                messages.append(inject_msg)
                                payload["messages"] = messages

                                async for token in self._resume_stream(client, payload):
                                    yield token

                            self._tool_integration.reset_pending()

                    yield f"data: {json.dumps({'token': content})}\n\n"

                yield "data: [DONE]\n\n"

    async def _resume_stream(
        self, client: httpx.AsyncClient, payload: dict
    ) -> AsyncGenerator[str, None]:
        async with client.stream(
            "POST",
            "http://localhost/v1/chat/completions",
            json={**payload, "stream": True},
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                content = choices[0].get("delta", {}).get("content", "")
                if content:
                    yield f"data: {json.dumps({'token': content})}\n\n"
