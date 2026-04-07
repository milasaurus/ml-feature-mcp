"""
Feature definitions for a music streaming recommendation system.

Inspired by the Spotify Tracks Dataset (kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset)
which contains ~114k tracks with audio features like danceability, energy, valence, tempo, etc.

In a real system, these features would be computed from streaming logs and track metadata.
Here we generate sample data that mirrors the schema and distributions of real Spotify data.
"""

from datetime import timedelta

from feast import (
    Entity,
    FeatureService,
    FeatureView,
    Field,
    FileSource,
    Project,
)
from feast.types import Float32, Int64, String

project = Project(name="feature_repo", description="Music streaming recommendation features")

# ── Entities ─────────────────────────────────────────────────────────────────

listener = Entity(name="listener", join_keys=["user_id"])
track = Entity(name="track", join_keys=["track_id"])

# ── Listener behavior features ───────────────────────────────────────────────
# Aggregated from a user's recent streaming history.

listener_stats_source = FileSource(
    name="listener_stats_source",
    path="data/listener_stats.parquet",
    timestamp_field="event_timestamp",
)

listener_stats_fv = FeatureView(
    name="listener_stats",
    entities=[listener],
    ttl=timedelta(days=7),
    schema=[
        Field(name="total_plays_7d", dtype=Int64, description="Total track plays in the last 7 days"),
        Field(name="unique_tracks_7d", dtype=Int64, description="Distinct tracks played in the last 7 days"),
        Field(name="unique_artists_7d", dtype=Int64, description="Distinct artists played in the last 7 days"),
        Field(name="avg_listen_minutes_daily", dtype=Float32, description="Average daily listening time in minutes"),
        Field(name="skip_rate", dtype=Float32, description="Fraction of tracks skipped within 30 seconds (0.0-1.0)"),
        Field(name="top_genre", dtype=String, description="Most-played genre in the last 7 days"),
        Field(name="avg_track_popularity", dtype=Float32, description="Average popularity score (0-100) of played tracks"),
    ],
    online=True,
    source=listener_stats_source,
    tags={"team": "recommendations"},
)

# ── Track audio features ─────────────────────────────────────────────────────
# Per-track metadata from audio analysis, similar to Spotify's audio features API.

track_features_source = FileSource(
    name="track_features_source",
    path="data/track_features.parquet",
    timestamp_field="event_timestamp",
)

track_features_fv = FeatureView(
    name="track_features",
    entities=[track],
    ttl=timedelta(days=30),
    schema=[
        Field(name="track_name", dtype=String, description="Name of the track"),
        Field(name="artist_name", dtype=String, description="Primary artist name"),
        Field(name="genre", dtype=String, description="Track genre classification"),
        Field(name="popularity", dtype=Int64, description="Popularity score 0-100 based on play count and recency"),
        Field(name="danceability", dtype=Float32, description="How suitable for dancing (0.0-1.0)"),
        Field(name="energy", dtype=Float32, description="Perceptual intensity and activity (0.0-1.0)"),
        Field(name="valence", dtype=Float32, description="Musical positiveness — high is happy, low is sad (0.0-1.0)"),
        Field(name="tempo", dtype=Float32, description="Estimated tempo in BPM"),
        Field(name="acousticness", dtype=Float32, description="Confidence the track is acoustic (0.0-1.0)"),
        Field(name="instrumentalness", dtype=Float32, description="Likelihood of no vocals (0.0-1.0)"),
        Field(name="duration_ms", dtype=Int64, description="Track length in milliseconds"),
    ],
    online=True,
    source=track_features_source,
    tags={"team": "catalog"},
)

# ── Feature services ─────────────────────────────────────────────────────────

listener_profile_v1 = FeatureService(
    name="listener_profile_v1",
    features=[listener_stats_fv],
)

recommendation_features_v1 = FeatureService(
    name="recommendation_features_v1",
    features=[listener_stats_fv, track_features_fv],
)
