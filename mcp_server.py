"""
Feast MCP Server — exposes Feast SDK operations as MCP tools.

The server wraps a local Feast FeatureStore and registers tools for:
- Feature discovery (list feature views, entities, data sources, feature services)
- Online retrieval (fetch latest feature values for given entities)
- Schema inspection (feature types, descriptions, TTLs, tags)

Runs over stdio transport. The MCP client spawns this as a subprocess.

Usage:
    uv run python mcp_server.py           # Run as MCP server (stdio)
    uv run mcp dev mcp_server.py          # Debug in MCP Inspector (http://localhost:5173)
"""

# TODO: Step 2 — implement the following:
#
# 1. Initialize FastMCP server and Feast FeatureStore
#    - from mcp.server.fastmcp import FastMCP
#    - from feast import FeatureStore
#    - Point FeatureStore at feature_repo/
#
# 2. Register discovery tools:
#    - list_feature_views: return registered views with schemas, entities, TTL, tags
#    - list_entities: return entity definitions and their join keys
#    - list_data_sources: return source names, types, paths, timestamp columns
#    - list_feature_services: return services and which feature views they bundle
#
# 3. Register retrieval tools:
#    - get_online_features: fetch latest feature values for entity rows
#      accepts: feature view name(s), entity key-value pairs
#      returns: feature values as JSON
#
# 4. Register inspection tools:
#    - describe_feature_view: detailed schema for a single feature view
#      (types, descriptions, TTL, source, tags)
#
# 5. Run the server:
#    if __name__ == "__main__":
#        mcp.run(transport="stdio")
#
# Remember: never print() to stdout — it corrupts the JSON-RPC protocol.
# Use logging to stderr instead.
