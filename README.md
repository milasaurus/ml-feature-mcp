# Feast MCP

A conversational management layer for ML feature stores. Uses MCP (Model Context Protocol) to let you discover, inspect, and retrieve features through natural language instead of writing boilerplate SDK scripts.

Built on Feast (open-source feature store). The MCP client and server are generic — they work with any Feast feature store. The project includes a sample music streaming data model for illustrative purposes; see [GUIDE.md](GUIDE.md#using-your-own-data) for how to plug in your own data.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Node.js](https://nodejs.org/) — required for MCP Inspector (`uv run mcp dev`)
- `ANTHROPIC_API_KEY` environment variable set

## Quick Start

```bash
# Install dependencies
uv sync

# Generate sample data and set up Feast
uv run python generate_data.py
cd feature_repo && uv run feast apply && uv run feast materialize-incremental $(date -u +"%Y-%m-%dT%H:%M:%S") && cd ..

# Run the MCP client (spawns the server automatically)
uv run python chat.py

# Or debug the server in the MCP Inspector (requires Node.js)
uv run mcp dev mcp_servers/feast_server.py
```

## Testing

```bash
# Run unit and integration tests
uv run python -m pytest tests/

# Test MCP server tools directly (no Claude API needed)
uv run python -c "from mcp_servers.feast_server import list_feature_views; print(list_feature_views())"

# Debug server interactively in the MCP Inspector (requires Node.js)
uv run mcp dev mcp_servers/feast_server.py
```

## Data Model

The sample data below is for illustration only — it demonstrates the kinds of features a music streaming platform might store. Audio feature schema inspired by the [Spotify Tracks Dataset](https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset).

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

| Feature | Type | Values | Description |
|---|---|---|---|
| `total_plays_7d` | int | 20-500 | Track plays in the last 7 days |
| `unique_tracks_7d` | int | 10-200 | Distinct tracks played |
| `unique_artists_7d` | int | 5-80 | Distinct artists played |
| `avg_listen_minutes_daily` | float | 15-180 | Average daily listening time (minutes) |
| `skip_rate` | float | 0.0-1.0 | Fraction of tracks skipped within 30 seconds |
| `top_genre` | string | e.g. "hip-hop" | Most-played genre in the last 7 days |
| `avg_track_popularity` | float | 0-100 | Average popularity score of played tracks |

### track_features

Per-track audio features and metadata. TTL: 30 days.

| Feature | Type | Values | Description |
|---|---|---|---|
| `track_name` | string | e.g. "Midnight Drive" | Track title |
| `artist_name` | string | e.g. "Luna Park" | Primary artist |
| `genre` | string | e.g. "electronic" | Genre classification |
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
├── mcp_servers/
│   └── feast_server.py        # MCP server — wraps Feast SDK as tools
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

## If You're Coming from a Production Feature Store

If you're used to a platform with a feature catalog, streaming ingestion, and structured feature configs, here's where those concerns land in this project:

| In production you have... | Here it maps to... |
|---|---|
| Feature catalog with search, ownership, lineage | `list_feature_views` / `list_entities` MCP tools — flat list, no ownership or lineage |
| Hierarchical feature paths (`/<entity>/<project>/<feature>`) | Simple `feature_view:feature_name` strings (e.g. `listener_stats:skip_rate`) |
| `FeatureSpec` / `FeatureColumn` config modules with column aliasing | Inline string lists passed directly to `get_online_features()` |
| `LabelSpec` with typed entity keys and partitioned storage | `get_historical_features()` with a pandas DataFrame — entity IDs + timestamps |
| Typed entity identifiers with encoding (e.g. base62) | Plain integer/string IDs (`user_id: 1001`, `track_id: "t001"`) |
| Distributed online stores (Redis, Bigtable) + data lake offline stores | Local SQLite online store + Parquet files |
| Streaming ingestion with freshness SLAs | Manual `feast materialize-incremental` |
| Real-time serving endpoints (<10ms p99) | Interactive exploration via MCP tools — not a serving path |

### What's not covered

These production concerns live outside the MCP layer entirely:
- Feature versioning, lineage, and governance
- Streaming ingestion and real-time feature computation
- Feature monitoring, drift detection, and freshness alerts
- Multi-team access controls and feature sharing
- Integration with ML training pipelines (TFX, Kubeflow, etc.)
