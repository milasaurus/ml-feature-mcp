"""
MCP Client — connects to the Feast MCP server, discovers tools,
and wires them into a Claude conversation loop with streaming and
extended thinking.

This module is pure MCP + Claude plumbing. It does not handle user
interaction — see chat.py for the REPL interface.

How the client-server-Claude flow works:

    1. CONNECT: Client spawns the MCP server as a subprocess over stdio.
       The server registers Feast SDK operations as MCP tools.

    2. DISCOVER: Client calls session.list_tools() to learn what tools
       the server offers. These get converted from MCP format to
       Anthropic's tool format (name, description, input_schema).

    3. CHAT LOOP (per user message):
       a. User message + tool definitions are sent to Claude via the
          streaming API with extended thinking enabled.
       b. Claude reasons about which tools to call (thinking block),
          then returns either a text response or tool_use blocks.
       c. If tool_use: client routes each call through MCP
          (session.call_tool), collects results, appends them to
          conversation history, and calls Claude again.
       d. If text: return the response to the caller.
       e. Repeat up to MAX_ITERATIONS to handle multi-step tool chains.

    4. HISTORY: Conversation history persists across chat() calls,
       enabling multi-turn context. Thinking blocks are stripped from
       history because the API rejects them in subsequent requests.
"""

from contextlib import AsyncExitStack

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from system_prompt import SYSTEM_PROMPT, TOOL_PROMPT

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 16_000
THINKING_BUDGET = 5_000
MAX_ITERATIONS = 4


class FeastMCPClient:
    def __init__(self):
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = anthropic.Anthropic()
        self.messages: list[dict] = []
        self.available_tools: list[dict] = []

    # ── Step 1: Connect to MCP server ────────────────────────────────────

    async def connect(self, server_script: str):
        """Spawn the MCP server as a subprocess and connect via stdio.

        The server runs as a child process communicating over stdin/stdout
        using JSON-RPC (the MCP protocol). After connecting, we perform
        the MCP handshake (initialize) and discover available tools.
        """
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", server_script],
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        # MCP handshake — negotiate capabilities with the server
        await self.session.initialize()

        await self._discover_tools()

    # ── Step 2: MCP operations (discover + call tools) ─────────────────

    async def _discover_tools(self):
        """Ask the server what tools it offers and convert to Anthropic format.

        MCP tools use "inputSchema" while Anthropic expects "input_schema".
        This fetches the tool list and stores the converted definitions.
        """
        response = await self.session.list_tools()
        self.available_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

    async def _call_tool(self, tool_use_id: str, name: str, args: dict) -> dict:
        """Route a single tool call through MCP and return a tool_result dict.

        This is the key MCP integration point: instead of executing tools
        locally, we call session.call_tool() which sends the request to
        the MCP server over stdio via JSON-RPC.
        """
        result = await self.session.call_tool(name, args)
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": result.content[0].text if result.content else "",
        }

    # ── Step 3: Chat loop — Claude + MCP tool routing ────────────────────

    async def chat(self, user_message: str) -> str:
        """Send a message through Claude with MCP tools.

        This is where MCP, Claude, and the conversation come together:
        - Claude sees the MCP tools as if they were native tool definitions
        - When Claude decides to call a tool, we route it through MCP
          (session.call_tool) instead of executing locally
        - Results flow back to Claude for the next reasoning step
        """
        if not self.session:
            raise RuntimeError("Not connected — call connect() first")

        self.messages.append({"role": "user", "content": user_message})

        # Prompt caching: mark the last tool and the tool prompt as
        # ephemeral so the API caches everything up to that point.
        # On subsequent requests in the same session, the system prompt
        # and tool definitions are served from cache — reducing latency
        # and input token costs.
        tools = [dict(t) for t in self.available_tools]
        if tools:
            tools[-1]["cache_control"] = {"type": "ephemeral"}

        system = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
            },
            {
                "type": "text",
                "text": TOOL_PROMPT,
                "cache_control": {"type": "ephemeral"},
            },
        ]

        # Claude may need multiple round trips to answer a question.
        # For example: "Get features for user 1001" requires Claude to
        # first call list_feature_views to learn the schema, then call
        # get_online_features with the right parameters. Each iteration
        # is one Claude API call → tool execution → feed results back
        # cycle. MAX_ITERATIONS caps this to prevent runaway loops.
        for _ in range(MAX_ITERATIONS):
            # Streaming: tokens arrive as they're generated. We consume
            # the full stream and get the final message. Extended thinking
            # lets Claude reason about which tools to call before acting —
            # this improves tool selection on multi-step requests.
            with self.anthropic.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                tools=tools,
                messages=self.messages,
                thinking={
                    "type": "enabled",
                    "budget_tokens": THINKING_BUDGET,
                },
            ) as stream:
                response = stream.get_final_message()

            # Thinking blocks are ephemeral — the API rejects them if
            # they appear in subsequent requests. Since self.messages is
            # sent back on every call, we must filter them out.
            content_for_history = [
                block for block in response.content
                if block.type != "thinking"
            ]
            self.messages.append({"role": "assistant", "content": content_for_history})

            # If Claude responded with text (not tool calls), we're done
            if response.stop_reason != "tool_use":
                return self._extract_text(response)

            # Claude wants to call tools — route each one through MCP.
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self._call_tool(block.id, block.name, block.input)
                    tool_results.append(result)

            # Append tool results as a "user" message (required by the API)
            # and loop back to let Claude process the results
            self.messages.append({"role": "user", "content": tool_results})

        return self._extract_text(response)

    def _extract_text(self, response: anthropic.types.Message) -> str:
        """Pull text content from a Claude response."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    async def close(self):
        """Clean up the MCP connection.

        Tears down the ClientSession and stdio transport, which kills
        the server subprocess. Safe to call multiple times.
        """
        self.session = None
        self.available_tools = []
        await self.exit_stack.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
