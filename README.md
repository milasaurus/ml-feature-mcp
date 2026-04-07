# Feast MCP

A conversational management layer for ML feature stores. Uses MCP (Model Context Protocol) to let you discover, inspect, and retrieve features through natural language instead of writing boilerplate SDK scripts.

Built on Feast (open-source feature store) with sample music streaming data.

## Quick Start

```bash
# Install dependencies
uv sync

# Generate sample data and set up Feast
uv run python generate_data.py
cd feature_repo && uv run feast apply && uv run feast materialize-incremental $(date -u +"%Y-%m-%dT%H:%M:%S") && cd ..

# Run the MCP client (spawns the server automatically)
uv run python mcp_client.py

# Or debug the server in the MCP Inspector
uv run mcp dev server.py
```

## Data Model

Audio feature schema inspired by the [Spotify Tracks Dataset](https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset).

```
┌─────────────────────────────────────────────────────────────────┐
│                        Feature Store                            │
│                                                                 │
│  ┌─────────────┐       ┌──────────────────┐                     │
│  │   Entities   │       │  Feature Views   │                     │
│  │             │       │                  │                     │
│  │  listener ──┼──────▶│ listener_stats   │                     │
│  │  (user_id)  │       │                  │                     │
│  │             │       │                  │                     │
│  │  track ─────┼──────▶│ track_features   │                     │
│  │  (track_id) │       │                  │                     │
│  └─────────────┘       └──────────────────┘                     │
│                                                                 │
│  ┌──────────────────────────────────────┐                       │
│  │         Feature Services             │                       │
│  │                                      │                       │
│  │  listener_profile_v1                 │                       │
│  │    └── listener_stats                │                       │
│  │                                      │                       │
│  │  recommendation_features_v1          │                       │
│  │    ├── listener_stats                │                       │
│  │    └── track_features                │                       │
│  └──────────────────────────────────────┘                       │
│                                                                 │
│  ┌──────────────────────────────────────┐                       │
│  │         Data Sources                 │                       │
│  │                                      │                       │
│  │  listener_stats_source (Parquet)     │                       │
│  │    └── data/listener_stats.parquet   │                       │
│  │                                      │                       │
│  │  track_features_source (Parquet)     │                       │
│  │    └── data/track_features.parquet   │                       │
│  └──────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### Entities

| Entity | Join Key | ID Format | Example |
|---|---|---|---|
| listener | `user_id` | integer | `1001` |
| track | `track_id` | string | `"t001"` |

### listener_stats

Aggregated listening behavior per user, updated every 6 hours. TTL: 7 days.

| Feature | Type | Range | Description |
|---|---|---|---|
| `total_plays_7d` | int | 20-500 | Track plays in the last 7 days |
| `unique_tracks_7d` | int | 10-200 | Distinct tracks played |
| `unique_artists_7d` | int | 5-80 | Distinct artists played |
| `avg_listen_minutes_daily` | float | 15-180 | Average daily listening time (minutes) |
| `skip_rate` | float | 0.0-1.0 | Fraction of tracks skipped within 30 seconds |
| `top_genre` | string | — | Most-played genre in the last 7 days |
| `avg_track_popularity` | float | 0-100 | Average popularity score of played tracks |

### track_features

Per-track audio features and metadata. TTL: 30 days.

| Feature | Type | Range | Description |
|---|---|---|---|
| `track_name` | string | — | Track title |
| `artist_name` | string | — | Primary artist |
| `genre` | string | — | Genre classification |
| `popularity` | int | 0-100 | Popularity score based on play count and recency |
| `danceability` | float | 0.0-1.0 | Suitability for dancing |
| `energy` | float | 0.0-1.0 | Perceptual intensity and activity |
| `valence` | float | 0.0-1.0 | Musical positiveness (high = happy, low = sad) |
| `tempo` | float | BPM | Estimated tempo |
| `acousticness` | float | 0.0-1.0 | Confidence the track is acoustic |
| `instrumentalness` | float | 0.0-1.0 | Likelihood of no vocals |
| `duration_ms` | int | ms | Track length in milliseconds |

### Sample entities

**10 listeners**: user IDs `1001`–`1010`

**20 tracks across 7 artists**:

| Track IDs | Artist | Genre |
|---|---|---|
| t001, t010, t015 | Luna Park | electronic |
| t002, t008, t016 | Rosa Vega | pop, latin |
| t003, t009, t017 | Ghost Protocol | hip-hop |
| t004, t011, t018 | Ama Diallo | r&b |
| t005, t012, t019 | Neon Bridges | indie |
| t006, t014, t020 | The Midnight Waves | rock |
| t007, t013 | Kira Sato | jazz |

## Project Structure

```
feast-mcp/
├── mcp_client.py              # MCP client — connects to server, routes tool calls to Claude
├── chat.py                    # REPL interface for interactive use
├── server.py                  # MCP server — wraps Feast SDK as tools
├── system_prompt.py           # System prompt with feature store context
├── generate_data.py           # Sample data generator
├── feature_repo/              # Feast feature repository
│   ├── feature_store.yaml     # Feast config (local SQLite online store)
│   ├── feature_definitions.py # Entity + feature view definitions
│   └── data/                  # Parquet files (listener_stats, track_features)
└── PLAN.md                    # Detailed build plan
```

## What the MCP Layer Does

The MCP server exposes Feast SDK operations as tools that Claude can call. The MCP client connects to the server, discovers those tools, and routes Claude's tool calls through the protocol. Together they provide:

| Capability | How it works |
|---|---|
| **Feature discovery** | Tools that list registered feature views, entities, data sources, and feature services |
| **Online retrieval** | Tools that fetch latest feature values for any entity — inspect what a model sees at serving time |
| **Schema inspection** | Tools that return feature types, descriptions, TTLs, and tags |
| **Data source lookup** | Tools that show where feature data comes from — file paths, table names, timestamp columns |

### What the MCP layer does NOT do

The MCP layer is a management and exploration interface. It does not replace the underlying feature platform:

- **Not a feature pipeline** — it doesn't run streaming ingestion or real-time transformations
- **Not a serving layer** — models call the feature store directly at inference time, not through MCP
- **Not a training pipeline** — batch feature retrieval for training datasets happens in pipeline orchestrators (Airflow, Kubeflow, etc.)

## How It Differs from Production

| Aspect | This Project (Feast MCP) | Production |
|---|---|---|
| **Feature references** | Simple `feature_view:feature_name` strings (e.g. `listener_stats:skip_rate`) | Hierarchical registered paths: `/<entity>/<project>/<feature>` (e.g. `/artist/jukebox-apm-sample/popularity_normalized`) |
| **Feature config** | Inline string lists passed to `get_online_features()` | Structured `FeatureSpec` with `FeatureColumn` objects in dedicated config modules, with column aliasing for downstream pipeline steps |
| **Label joins** | `get_historical_features()` with a pandas DataFrame containing entity IDs + timestamps | `LabelSpec` with typed entity keys (e.g. base62-encoded IDs), epoch millis timestamps, partitioned storage (TF_Example format), and support for features already present in label data |
| **Entities** | Simple integer/string IDs (`user_id: 1001`, `track_id: "t001"`) | Typed identifiers with encoding (e.g. `SourceKey("artist", "base62", "artist_gid")`) |
| **Data storage** | Local SQLite online store + Parquet files | Distributed online stores (Redis, DynamoDB, Bigtable), data lake offline stores, partitioned by date |
| **Scale** | 10 users, 20 tracks, single machine | Millions of entities, thousands of features, multi-region serving |
| **Feature freshness** | Manual `feast materialize-incremental` | Continuous streaming ingestion with freshness SLAs and monitoring |
| **Access pattern** | Interactive exploration via MCP tools | Batch training pipelines + real-time serving endpoints with <10ms p99 latency |
| **Feature discovery** | `list_feature_views()` returns everything | Feature catalog with search, ownership, lineage, and access controls |

### What transfers to production

The core concepts are the same:
- **Entities** as join keys between label data and features
- **Point-in-time joins** to prevent data leakage (latest feature value before each label's timestamp)
- **Online vs offline stores** for serving vs training
- **Feature views** as the unit of feature definition and materialization

### What doesn't transfer

- No feature versioning, lineage, or governance
- No streaming ingestion or real-time feature computation
- No feature monitoring, drift detection, or freshness alerts
- No multi-team access controls or feature sharing
- No integration with ML training pipelines (TFX, Kubeflow, etc.)
