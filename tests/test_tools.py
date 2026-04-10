"""
Tests for MCP server tools — verifies Feast SDK calls return correct data.

Each tool is a thin wrapper around a Feast SDK call that returns JSON.
These tests call the tool functions directly (no MCP transport) against
the real Feast store with materialized sample data. They verify:
- Correct JSON structure and field names
- Entity columns are filtered out of feature lists
- Known sample data values are present
- Error cases raise appropriate exceptions

These are integration tests — they hit the real SQLite online store.
If tests fail with registry errors, run `make setup` first.
"""

import json

import pytest

from mcp_servers.feast_server import (
    describe_feature_view,
    get_online_features,
    list_data_sources,
    list_entities,
    list_feature_services,
    list_feature_views,
)


# ── Output format consistency ────────────────────────────────────────────────
# Every tool must return a valid JSON string. If a tool returns a dict or None,
# the MCP transport will fail to serialize the response.


class TestToolOutputFormat:
    """Verify every tool returns a parseable JSON string, not a dict or None."""

    DISCOVERY_TOOLS = [
        list_feature_views,
        list_entities,
        list_data_sources,
        list_feature_services,
    ]

    @pytest.mark.parametrize("tool_fn", DISCOVERY_TOOLS)
    def test_discovery_tools_return_valid_json(self, tool_fn):
        result = tool_fn()
        assert isinstance(result, str), f"{tool_fn.__name__} returned {type(result)}, expected str"
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_get_online_features_returns_valid_json(self):
        result = get_online_features("listener_stats", {"user_id": [1001]})
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_describe_feature_view_returns_valid_json(self):
        result = describe_feature_view("listener_stats")
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)


# ── list_feature_views ───────────────────────────────────────────────────────


class TestListFeatureViews:
    def setup_method(self):
        self.result = json.loads(list_feature_views())

    def test_returns_list(self):
        assert isinstance(self.result, list)

    def test_has_two_views(self):
        assert len(self.result) == 2

    def test_view_names(self):
        names = {v["name"] for v in self.result}
        assert names == {"listener_stats", "track_features"}

    def test_view_has_required_fields(self):
        # These fields are what Claude uses to understand the feature store.
        # Missing any of them degrades Claude's ability to answer questions.
        for view in self.result:
            assert "name" in view
            assert "entities" in view
            assert "features" in view
            assert "ttl" in view
            assert "tags" in view
            assert "online" in view

    def test_features_exclude_entity_columns(self):
        # Feast's schema includes entity join keys (user_id, track_id) alongside
        # actual features. We filter them out so Claude doesn't try to fetch
        # "listener_stats:user_id" as a feature — that would cause a KeyError.
        for view in self.result:
            feature_names = [f["name"] for f in view["features"]]
            assert "user_id" not in feature_names
            assert "track_id" not in feature_names

    def test_listener_stats_features(self):
        listener = next(v for v in self.result if v["name"] == "listener_stats")
        feature_names = {f["name"] for f in listener["features"]}
        assert "skip_rate" in feature_names
        assert "top_genre" in feature_names
        assert "total_plays_7d" in feature_names

    def test_track_features_features(self):
        tracks = next(v for v in self.result if v["name"] == "track_features")
        feature_names = {f["name"] for f in tracks["features"]}
        assert "danceability" in feature_names
        assert "energy" in feature_names
        assert "track_name" in feature_names


# ── list_entities ────────────────────────────────────────────────────────────


class TestListEntities:
    def setup_method(self):
        self.result = json.loads(list_entities())

    def test_returns_list(self):
        assert isinstance(self.result, list)

    def test_has_two_entities(self):
        assert len(self.result) == 2

    def test_entity_names(self):
        names = {e["name"] for e in self.result}
        assert names == {"listener", "track"}

    def test_join_keys(self):
        for entity in self.result:
            assert "join_keys" in entity
            assert len(entity["join_keys"]) == 1

    def test_listener_join_key(self):
        # Claude needs the join key name to build entity_dict for get_online_features.
        listener = next(e for e in self.result if e["name"] == "listener")
        assert listener["join_keys"] == ["user_id"]

    def test_track_join_key(self):
        track = next(e for e in self.result if e["name"] == "track")
        assert track["join_keys"] == ["track_id"]


# ── list_data_sources ────────────────────────────────────────────────────────


class TestListDataSources:
    def setup_method(self):
        self.result = json.loads(list_data_sources())

    def test_returns_list(self):
        assert isinstance(self.result, list)

    def test_has_two_sources(self):
        assert len(self.result) == 2

    def test_source_names(self):
        names = {s["name"] for s in self.result}
        assert names == {"listener_stats_source", "track_features_source"}

    def test_sources_are_file_type(self):
        for source in self.result:
            assert source["type"] == "FileSource"

    def test_sources_have_timestamp_field(self):
        for source in self.result:
            assert source["timestamp_field"] == "event_timestamp"

    def test_sources_have_paths(self):
        for source in self.result:
            assert "path" in source
            assert source["path"].endswith(".parquet")


# ── list_feature_services ────────────────────────────────────────────────────


class TestListFeatureServices:
    def setup_method(self):
        self.result = json.loads(list_feature_services())

    def test_returns_list(self):
        assert isinstance(self.result, list)

    def test_has_two_services(self):
        assert len(self.result) == 2

    def test_service_names(self):
        names = {s["name"] for s in self.result}
        assert names == {"listener_profile_v1", "recommendation_features_v1"}

    def test_listener_profile_views(self):
        service = next(s for s in self.result if s["name"] == "listener_profile_v1")
        assert service["feature_views"] == ["listener_stats"]

    def test_recommendation_views(self):
        # This service bundles both views — used when the recommendation
        # model needs listener behavior + track audio features together.
        service = next(s for s in self.result if s["name"] == "recommendation_features_v1")
        assert set(service["feature_views"]) == {"listener_stats", "track_features"}


# ── get_online_features ──────────────────────────────────────────────────────


class TestGetOnlineFeatures:
    """Verify online feature retrieval against materialized sample data.

    These tests hit the real SQLite online store. The entity_dict format
    mirrors what Claude sends: {"user_id": [1001]} or {"track_id": ["t001"]}.
    """

    def test_single_listener(self):
        result = json.loads(get_online_features("listener_stats", {"user_id": [1001]}))
        assert "user_id" in result
        assert result["user_id"] == [1001]
        assert "top_genre" in result
        assert "skip_rate" in result

    def test_single_track(self):
        result = json.loads(get_online_features("track_features", {"track_id": ["t001"]}))
        assert "track_id" in result
        assert result["track_id"] == ["t001"]
        assert "track_name" in result
        assert "danceability" in result

    def test_multiple_listeners(self):
        # Claude often fetches multiple entities at once for comparison queries.
        result = json.loads(get_online_features("listener_stats", {"user_id": [1001, 1002]}))
        assert len(result["user_id"]) == 2

    def test_multiple_tracks(self):
        result = json.loads(get_online_features("track_features", {"track_id": ["t001", "t006"]}))
        assert len(result["track_id"]) == 2

    def test_invalid_feature_view_raises(self):
        with pytest.raises(Exception):
            get_online_features("nonexistent_view", {"user_id": [1001]})


# ── describe_feature_view ────────────────────────────────────────────────────


class TestDescribeFeatureView:
    """Verify detailed schema inspection for individual feature views.

    describe_feature_view returns richer info than list_feature_views —
    it includes feature descriptions, source details, and tags. Claude
    uses this when a user asks "what does skip_rate mean?" or "where
    does this data come from?".
    """

    def test_listener_stats(self):
        result = json.loads(describe_feature_view("listener_stats"))
        assert result["name"] == "listener_stats"
        assert result["online"] is True
        assert result["tags"]["team"] == "recommendations"

    def test_track_features(self):
        result = json.loads(describe_feature_view("track_features"))
        assert result["name"] == "track_features"
        assert result["tags"]["team"] == "catalog"

    def test_has_source_info(self):
        result = json.loads(describe_feature_view("listener_stats"))
        assert result["source"]["name"] == "listener_stats_source"
        assert result["source"]["type"] == "FileSource"
        assert result["source"]["path"].endswith(".parquet")

    def test_features_have_descriptions(self):
        # Descriptions help Claude explain feature meanings to users.
        result = json.loads(describe_feature_view("listener_stats"))
        for feature in result["features"]:
            assert feature["description"], f"Feature '{feature['name']}' has no description"

    def test_features_exclude_entity_columns(self):
        result = json.loads(describe_feature_view("listener_stats"))
        feature_names = [f["name"] for f in result["features"]]
        assert "user_id" not in feature_names

    def test_has_ttl(self):
        result = json.loads(describe_feature_view("listener_stats"))
        assert result["ttl"] is not None

    def test_invalid_view_raises(self):
        with pytest.raises(Exception):
            describe_feature_view("nonexistent_view")
