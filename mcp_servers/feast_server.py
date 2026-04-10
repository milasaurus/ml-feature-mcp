"""
Feast MCP Server — exposes Feast SDK operations as MCP tools.

The server wraps a local Feast FeatureStore and registers tools for:
- Feature discovery (list feature views, entities, data sources, feature services)
- Online retrieval (fetch latest feature values for given entities)
- Schema inspection (feature types, descriptions, TTLs, tags)

Runs over stdio transport. The MCP client spawns this as a subprocess.

Usage:
    make chat                                           # Run the REPL (spawns server automatically)
    make dev                                            # Debug in MCP Inspector (http://localhost:5173)
"""

import json
import logging
from pathlib import Path

from feast import FeatureStore
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

mcp = FastMCP("feast")

REPO_PATH = str(Path(__file__).parent.parent / "feature_repo")
store = FeatureStore(repo_path=REPO_PATH)


# ── Discovery tools ─────────────────────────────────────────────────────────


@mcp.tool()
def list_feature_views() -> str:
    """List all registered feature views with their schemas, entities, TTL, and tags."""
    views = store.list_feature_views()
    result = []
    for fv in views:
        entity_col_names = {ec.name for ec in fv.entity_columns}
        result.append({
            "name": fv.name,
            "entities": list(fv.entities),
            "features": [
                {"name": f.name, "dtype": str(f.dtype)}
                for f in fv.schema
                if f.name not in entity_col_names
            ],
            "ttl": str(fv.ttl) if fv.ttl else None,
            "tags": dict(fv.tags) if fv.tags else {},
            "online": fv.online,
        })
    return json.dumps(result, indent=2)


@mcp.tool()
def list_entities() -> str:
    """List all entity definitions and their join keys."""
    entities = store.list_entities()
    result = []
    for entity in entities:
        result.append({
            "name": entity.name,
            "join_keys": [entity.join_key],
            "description": entity.description or "",
        })
    return json.dumps(result, indent=2)


@mcp.tool()
def list_data_sources() -> str:
    """List all data sources with their names, types, paths, and timestamp columns."""
    sources = store.list_data_sources()
    result = []
    for ds in sources:
        info = {
            "name": ds.name,
            "type": type(ds).__name__,
            "timestamp_field": ds.timestamp_field if hasattr(ds, "timestamp_field") else None,
        }
        if hasattr(ds, "path"):
            info["path"] = ds.path
        result.append(info)
    return json.dumps(result, indent=2)


@mcp.tool()
def list_feature_services() -> str:
    """List all feature services and which feature views they bundle."""
    services = store.list_feature_services()
    result = []
    for fs in services:
        result.append({
            "name": fs.name,
            "feature_views": [
                proj.name for proj in fs.feature_view_projections
            ],
            "description": fs.description or "",
            "tags": dict(fs.tags) if fs.tags else {},
        })
    return json.dumps(result, indent=2)


# ── Retrieval tools ──────────────────────────────────────────────────────────


@mcp.tool()
def get_online_features(feature_view: str, entity_dict: dict) -> str:
    """Fetch the latest online feature values for given entities.

    Args:
        feature_view: Name of the feature view to query (e.g. "listener_stats")
        entity_dict: Entity key-value pairs (e.g. {"user_id": [1001, 1002]})
    """
    fv = store.get_feature_view(feature_view)
    entity_col_names = {ec.name for ec in fv.entity_columns}
    feature_refs = [
        f"{feature_view}:{f.name}"
        for f in fv.schema
        if f.name not in entity_col_names
    ]

    result = store.get_online_features(
        features=feature_refs,
        entity_rows=[
            {k: v for k, v in zip(entity_dict.keys(), vals)}
            for vals in zip(*entity_dict.values())
        ],
    )
    return json.dumps(result.to_dict(), indent=2, default=str)


# ── Inspection tools ─────────────────────────────────────────────────────────


@mcp.tool()
def describe_feature_view(name: str) -> str:
    """Get detailed schema for a single feature view including types, descriptions, TTL, source, and tags.

    Args:
        name: Name of the feature view (e.g. "listener_stats")
    """
    fv = store.get_feature_view(name)
    entity_col_names = {ec.name for ec in fv.entity_columns}
    result = {
        "name": fv.name,
        "entities": list(fv.entities),
        "ttl": str(fv.ttl) if fv.ttl else None,
        "online": fv.online,
        "tags": dict(fv.tags) if fv.tags else {},
        "source": {
            "name": fv.batch_source.name if fv.batch_source else None,
            "type": type(fv.batch_source).__name__ if fv.batch_source else None,
            "path": getattr(fv.batch_source, "path", None),
        },
        "features": [
            {
                "name": f.name,
                "dtype": str(f.dtype),
                "description": f.description or "",
            }
            for f in fv.schema
            if f.name not in entity_col_names
        ],
    }
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
