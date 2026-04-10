"""
Tests for the MCP server — verifies FastMCP setup and tool registration.

These tests check the server configuration layer, not the tool logic itself
(see test_tools.py for that). They ensure:
- The FastMCP server is properly initialized with the Feast store
- All 6 tools are registered with correct names, descriptions, and schemas
- Tool parameter schemas match what the MCP client expects

Why this matters: if a tool isn't registered or has a wrong parameter schema,
the MCP client won't discover it and Claude won't be able to call it.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from mcp_servers.feast_server import mcp, store


class TestServerSetup:
    """Verify the FastMCP server and Feast store are properly initialized."""

    def test_server_is_fastmcp_instance(self):
        assert isinstance(mcp, FastMCP)

    def test_server_name(self):
        # The server name appears in MCP Inspector and client logs.
        assert mcp.name == "feast"

    def test_feast_store_initialized(self):
        assert store is not None

    def test_feast_store_has_feature_views(self):
        # Sanity check that the store can talk to the registry.
        # If this fails, the Feast repo probably hasn't been applied.
        views = store.list_feature_views()
        assert len(views) > 0


class TestToolRegistration:
    """Verify all tools are registered with correct metadata.

    The MCP client calls session.list_tools() to discover what the server
    offers. These tests ensure every tool shows up with the right name,
    a non-empty description (used by Claude to decide which tool to call),
    and the correct parameter schema.
    """

    def setup_method(self):
        self.tools = {tool.name: tool for tool in mcp._tool_manager.list_tools()}

    def test_all_tools_registered(self):
        expected = [
            "list_feature_views",
            "list_entities",
            "list_data_sources",
            "list_feature_services",
            "get_online_features",
            "describe_feature_view",
        ]
        for name in expected:
            assert name in self.tools, f"Tool '{name}' not registered"

    def test_tool_count(self):
        assert len(self.tools) == 6

    def test_tools_have_descriptions(self):
        # Claude uses descriptions to decide which tool to call.
        # A missing description means Claude can't reason about the tool.
        for name, tool in self.tools.items():
            assert tool.description, f"Tool '{name}' has no description"

    def test_get_online_features_has_parameters(self):
        # get_online_features needs both a feature_view name and entity_dict.
        # If either is missing from the schema, Claude won't know what to pass.
        schema = self.tools["get_online_features"].parameters
        assert "feature_view" in schema["properties"]
        assert "entity_dict" in schema["properties"]

    def test_describe_feature_view_has_parameters(self):
        schema = self.tools["describe_feature_view"].parameters
        assert "name" in schema["properties"]
