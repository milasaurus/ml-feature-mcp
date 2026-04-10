"""
Tests for the MCP client — verifies connection, tool discovery, and message handling.

The client is the bridge between Claude and the MCP server. These tests mock
the MCP transport and Anthropic API to verify the client's plumbing:
- stdio connection setup and MCP handshake
- Tool format conversion (MCP's inputSchema → Anthropic's input_schema)
- Tool call routing through session.call_tool()
- Conversation history management
- Error handling (calling chat() before connect())

These are unit tests — they don't start a real server or call the Claude API.
For end-to-end tests, see test_integration.py.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic

from mcp_client import FeastMCPClient


# ── Initialization ───────────────────────────────────────────────────────────


class TestClientInit:
    """Verify the client starts in a clean, disconnected state."""

    def test_initial_state(self):
        client = FeastMCPClient()
        assert client.session is None
        assert client.messages == []
        assert client.available_tools == []

    def test_has_anthropic_client(self):
        # The Anthropic client is created eagerly — it reads ANTHROPIC_API_KEY
        # from the environment. If this fails, the key isn't set.
        client = FeastMCPClient()
        assert client.anthropic is not None


# ── Connection ───────────────────────────────────────────────────────────────


class TestClientConnect:
    """Verify the client can establish an MCP connection.

    connect() does three things:
    1. Spawns the server as a subprocess over stdio
    2. Performs the MCP handshake (session.initialize())
    3. Discovers available tools (session.list_tools())
    """

    @pytest.mark.asyncio
    async def test_connect_sets_session(self):
        client = FeastMCPClient()

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))

        with patch("mcp_client.stdio_client") as mock_stdio:
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
            mock_stdio.return_value = mock_transport

            with patch("mcp_client.ClientSession") as mock_cs:
                mock_cs_instance = AsyncMock()
                mock_cs_instance.__aenter__ = AsyncMock(return_value=mock_session)
                mock_cs.return_value = mock_cs_instance

                await client.connect("mcp_servers/feast_server.py")

        assert client.session is mock_session

    @pytest.mark.asyncio
    async def test_chat_without_connect_raises(self):
        # Calling chat() before connect() should fail fast with a clear error,
        # not a cryptic NoneType error from session being None.
        client = FeastMCPClient()
        with pytest.raises(RuntimeError, match="Not connected"):
            await client.chat("hello")


# ── Tool discovery ───────────────────────────────────────────────────────────


class TestToolDiscovery:
    """Verify MCP tools are converted to Anthropic's expected format.

    MCP tools use "inputSchema" (camelCase) while the Anthropic API expects
    "input_schema" (snake_case). The client must convert during discovery,
    otherwise Claude won't see the tool parameters.
    """

    @pytest.mark.asyncio
    async def test_discover_converts_tool_format(self):
        client = FeastMCPClient()

        mock_tool = MagicMock()
        mock_tool.name = "list_feature_views"
        mock_tool.description = "List all feature views"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        client.session = AsyncMock()
        client.session.list_tools = AsyncMock(
            return_value=MagicMock(tools=[mock_tool])
        )

        await client._discover_tools()

        assert len(client.available_tools) == 1
        tool = client.available_tools[0]
        assert tool["name"] == "list_feature_views"
        assert tool["description"] == "List all feature views"
        # Must be snake_case for Anthropic, not camelCase from MCP
        assert "input_schema" in tool
        assert "inputSchema" not in tool


# ── Tool calling ─────────────────────────────────────────────────────────────


class TestToolCalling:
    """Verify tool calls are routed through the MCP session correctly.

    When Claude returns a tool_use block, the client calls
    session.call_tool(name, args) and wraps the result in the format
    the Anthropic API expects for tool_result messages.
    """

    @pytest.mark.asyncio
    async def test_call_tool_routes_through_session(self):
        client = FeastMCPClient()

        mock_result = MagicMock()
        mock_result.content = [MagicMock(text='{"data": "test"}')]

        client.session = AsyncMock()
        client.session.call_tool = AsyncMock(return_value=mock_result)

        result = await client._call_tool("tool_123", "list_entities", {})

        # Verify the call was forwarded to the MCP server
        client.session.call_tool.assert_called_once_with("list_entities", {})
        # Verify the result is wrapped in Anthropic's tool_result format
        assert result["type"] == "tool_result"
        assert result["tool_use_id"] == "tool_123"
        assert result["content"] == '{"data": "test"}'

    @pytest.mark.asyncio
    async def test_call_tool_handles_empty_content(self):
        # Some tools might return no content (e.g., a delete operation).
        # The client should return an empty string, not crash.
        client = FeastMCPClient()

        mock_result = MagicMock()
        mock_result.content = []

        client.session = AsyncMock()
        client.session.call_tool = AsyncMock(return_value=mock_result)

        result = await client._call_tool("tool_123", "list_entities", {})
        assert result["content"] == ""


# ── Text extraction ──────────────────────────────────────────────────────────


class TestExtractText:
    """Verify _extract_text pulls the right content from Claude responses.

    Claude responses contain a list of content blocks (text, tool_use, etc.).
    _extract_text should return the first text block's content, or empty
    string if there are no text blocks.
    """

    def test_extracts_text_block(self):
        client = FeastMCPClient()
        response = MagicMock()
        response.content = [MagicMock(type="text", text="Here are the features")]

        assert client._extract_text(response) == "Here are the features"

    def test_returns_empty_for_no_text_blocks(self):
        # This can happen if Claude responds with only tool_use blocks
        # and the iteration limit is hit before a text response arrives.
        client = FeastMCPClient()
        response = MagicMock()
        response.content = [MagicMock(type="tool_use", text=None)]
        # tool_use blocks don't have .text in the same way, but _extract_text
        # checks block.type == "text", so it should skip them
        response.content[0].type = "tool_use"

        assert client._extract_text(response) == ""

    def test_extracts_first_text_block(self):
        # If Claude returns multiple text blocks (rare but possible),
        # we return the first one.
        client = FeastMCPClient()
        response = MagicMock()
        response.content = [
            MagicMock(type="text", text="First"),
            MagicMock(type="text", text="Second"),
        ]

        assert client._extract_text(response) == "First"


# ── Message history ──────────────────────────────────────────────────────────


class TestMessageHistory:
    """Verify conversation history is built correctly.

    The client maintains self.messages across chat() calls. Each call
    appends the user message and Claude's response. This history is sent
    back to Claude on every API call for multi-turn context.
    """

    @pytest.mark.asyncio
    async def test_chat_appends_user_message(self):
        client = FeastMCPClient()
        client.session = AsyncMock()
        client.available_tools = []

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MagicMock(type="text", text="Hello!")]

        with patch.object(client.anthropic.messages, "stream") as mock_stream:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock(get_final_message=MagicMock(return_value=mock_response)))
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_stream.return_value = mock_ctx

            await client.chat("test message")

        assert client.messages[0] == {"role": "user", "content": "test message"}

    @pytest.mark.asyncio
    async def test_chat_appends_assistant_response(self):
        client = FeastMCPClient()
        client.session = AsyncMock()
        client.available_tools = []

        mock_content = [MagicMock(type="text", text="Hello!")]
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = mock_content

        with patch.object(client.anthropic.messages, "stream") as mock_stream:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=MagicMock(get_final_message=MagicMock(return_value=mock_response)))
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_stream.return_value = mock_ctx

            await client.chat("test message")

        # Should have user message + assistant response
        assert len(client.messages) == 2
        assert client.messages[1]["role"] == "assistant"


# ── Cleanup ──────────────────────────────────────────────────────────────────


class TestClose:
    """Verify the client cleans up properly on close.

    close() tears down the MCP session and stdio transport. After close(),
    the client should be in a clean state (no session, no tools). The
    context manager (__aenter__/__aexit__) should call close() automatically.
    """

    @pytest.mark.asyncio
    async def test_close_clears_state(self):
        client = FeastMCPClient()
        client.session = MagicMock()
        client.available_tools = [{"name": "test"}]

        await client.close()

        assert client.session is None
        assert client.available_tools == []

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with FeastMCPClient() as client:
            assert client is not None
        assert client.session is None
