"""
MCP Client — connects to the Feast MCP server, discovers tools,
and wires them into a Claude conversation loop with streaming and
extended thinking.
"""

import asyncio
import json
from contextlib import AsyncExitStack

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from system_prompt import SYSTEM_PROMPT

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

    async def connect(self, server_script: str):
        """Spawn the MCP server and connect via stdio."""
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
        await self.session.initialize()

        # Discover tools from the server
        response = await self.session.list_tools()
        self.available_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

        print(f"Connected to server. Discovered {len(self.available_tools)} tools:")
        for tool in self.available_tools:
            print(f"  - {tool['name']}: {tool['description']}")

    async def chat(self, user_message: str) -> str:
        """Send a message through Claude with MCP tools, using streaming and extended thinking."""
        self.messages.append({"role": "user", "content": user_message})

        # Tool caching: mark last tool definition as ephemeral
        tools = [dict(t) for t in self.available_tools]
        if tools:
            tools[-1]["cache_control"] = {"type": "ephemeral"}

        # Tool prompt: help Claude use the tools effectively
        tool_prompt = (
            "When asked about the feature store, use the available tools to look up "
            "real data rather than guessing. Call list_feature_views or list_entities "
            "first if you need to discover what's available before fetching specific "
            "feature values. When fetching features, use the exact feature view and "
            "entity names returned by the list tools."
        )
        system = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
            },
            {
                "type": "text",
                "text": tool_prompt,
                "cache_control": {"type": "ephemeral"},
            },
        ]

        for _ in range(MAX_ITERATIONS):
            # Streaming with extended thinking
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

            # Strip thinking blocks from history
            content_for_history = [
                block for block in response.content
                if block.type != "thinking"
            ]
            self.messages.append({"role": "assistant", "content": content_for_history})

            # If no tool use, return the text response
            if response.stop_reason != "tool_use":
                return self._extract_text(response)

            # Route tool calls through MCP
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self.session.call_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.content[0].text if result.content else "",
                    })

            self.messages.append({"role": "user", "content": tool_results})

        return self._extract_text(response)

    def _extract_text(self, response: anthropic.types.Message) -> str:
        """Pull text content from a Claude response."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    async def run(self):
        """Interactive REPL loop."""
        await self.connect("server.py")
        print("\nReady! Ask me about the feature store. Type 'quit' to exit.\n")

        while True:
            try:
                user_input = input("You: ")
            except (EOFError, KeyboardInterrupt):
                break

            if user_input.strip().lower() in ("quit", "exit"):
                break

            response = await self.chat(user_input)
            print(f"\nClaude: {response}\n")

        await self.exit_stack.aclose()


async def main():
    client = FeastMCPClient()
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
