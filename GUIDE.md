# Feast MCP — User Guide

## What This Is

A conversational management layer for your Feast feature store. The MCP server exposes Feast SDK operations as tools. The MCP client connects to the server, discovers those tools, and routes Claude's tool calls through the protocol. You ask questions in plain language; the tools handle the Feast SDK calls.

### Who it's for

- **ML engineers** debugging feature values or verifying data before training runs
- **Data scientists** exploring available features for a new model without reading infra code
- **Platform engineers** auditing feature definitions, data sources, and materialization state

### What the MCP layer does

| Capability | What it covers |
|---|---|
| **Feature discovery** | List feature views, entities, data sources, and feature services. Understand what's registered and how it's connected. |
| **Online retrieval** | Fetch latest feature values for any entity. Inspect what the model would see at serving time. |
| **Schema inspection** | View feature types, descriptions, TTLs, and tags. Understand what each feature means without reading definition files. |
| **Data source lookup** | See where feature data comes from — file paths, table names, timestamp columns. |

### What the MCP layer does NOT do

It doesn't replace the feature platform underneath:
- Not a feature pipeline — no streaming ingestion or real-time transformations
- Not a serving layer — models call the feature store directly, not through MCP
- Not a training pipeline — batch retrieval for training datasets happens in pipeline orchestrators

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) installed
- `ANTHROPIC_API_KEY` set in your environment
- Node.js (only needed for the MCP Inspector)

### Setup

```bash
cd feast-mcp

# Install dependencies
uv sync

# Generate sample music streaming data
uv run python generate_data.py

# Register feature definitions and materialize to online store
cd feature_repo
uv run feast apply
uv run feast materialize-incremental $(date -u +"%Y-%m-%dT%H:%M:%S")
cd ..
```

### Run

```bash
# Start chatting
uv run python chat.py
```

The client spawns the MCP server automatically. No separate server process needed.

## Example Workflows

### 1. Feature discovery — "What do we have?"

When onboarding to a new feature store or checking what's available for a model:

```
You: What feature views are registered?
You: What entities does the feature store have?
You: Which feature services bundle listener and track features together?
You: Where does the listener data come from?
```

### 2. Online retrieval — "What would the model see?"

When debugging predictions or verifying feature values at serving time:

```
You: Get me the listening stats for user 1001
You: What are the audio features for track t005?
You: Show me the features for users 1001, 1003, and 1007 side by side
You: What features would the recommendation model get for user 1004 and track t012?
```

### 3. Data quality — "Does this look right?"

When validating features before a training run or after a pipeline change:

```
You: Which users have the highest skip rate?
You: Are there any users with unusually low listening time?
You: Compare the audio features of Midnight Drive and Golden Hour — do they look reasonable for their genres?
You: Show me all track features for hip-hop tracks — are the energy and danceability values consistent?
```

### 4. Schema understanding — "What does this feature mean?"

When interpreting model inputs or writing feature documentation:

```
You: What does a danceability of 0.78 mean?
You: What's the TTL on the listener stats feature view?
You: Explain the difference between acousticness and instrumentalness
You: What type is the skip_rate feature and what's its valid range?
```

### 5. Feature preparation — "Help me set up features"

When planning which features to use in a new model:

```
You: What features would be most useful for a playlist recommendation model?
You: I need user and track features for a skip prediction model — what's available?
You: Which feature service should I use if I only need listener behavior data?
```

## Testing

### Run tests

```bash
uv run python -m pytest tests/
```

### Test server tools directly

You can call any MCP server tool without the Claude API or MCP client:

```bash
# List feature views
uv run python -c "from mcp_servers.feast_server import list_feature_views; print(list_feature_views())"

# Get online features for a user
uv run python -c "from mcp_servers.feast_server import get_online_features; print(get_online_features('listener_stats', {'user_id': [1001]}))"

# Describe a feature view
uv run python -c "from mcp_servers.feast_server import describe_feature_view; print(describe_feature_view('track_features'))"
```

## Running the Server Locally

You can run the MCP server as a standalone process to see raw tool output without going through Claude. This is useful for verifying feature data, debugging tool behavior, or understanding what Claude sees when it calls a tool.

```bash
# Start the server
uv run python mcp_servers/feast_server.py
```

Or import tools directly in a Python session:

```python
from mcp_servers.feast_server import list_feature_views, get_online_features, describe_feature_view

# See all registered feature views
print(list_feature_views())

# Check what features a user has
print(get_online_features("listener_stats", {"user_id": [1001]}))

# Inspect a feature view's full schema
print(describe_feature_view("track_features"))
```

All tools return JSON strings, so you can pipe them through `jq` or parse them in scripts.

## Debugging with MCP Inspector

If tools aren't behaving as expected, test the server in isolation:

```bash
uv run mcp dev mcp_servers/feast_server.py
```

This opens a browser UI at `http://localhost:5173` where you can:
- See all registered tools and their schemas
- Call tools manually with sample inputs
- Inspect the raw JSON-RPC messages going over the wire

## Sample Data

The feature store is populated with music streaming data inspired by the [Spotify Tracks Dataset](https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset).

### listener_stats (10 users: 1001-1010)

Aggregated listening behavior, updated every 6 hours.

| Feature | Type | Description |
|---|---|---|
| total_plays_7d | int | Track plays in the last 7 days |
| unique_tracks_7d | int | Distinct tracks played |
| unique_artists_7d | int | Distinct artists played |
| avg_listen_minutes_daily | float | Average daily listening time (minutes) |
| skip_rate | float | Fraction of tracks skipped within 30s (0.0-1.0) |
| top_genre | string | Most-played genre |
| avg_track_popularity | float | Average popularity of played tracks (0-100) |

### track_features (20 tracks: t001-t020)

Per-track audio features and metadata, modeled after Spotify's audio analysis API.

| Feature | Type | Description |
|---|---|---|
| track_name | string | Track title |
| artist_name | string | Primary artist |
| genre | string | Genre classification |
| popularity | int | Popularity score (0-100) |
| danceability | float | Suitability for dancing (0.0-1.0) |
| energy | float | Intensity and activity (0.0-1.0) |
| valence | float | Musical positiveness (0.0-1.0) |
| tempo | float | Estimated BPM |
| acousticness | float | Acoustic confidence (0.0-1.0) |
| instrumentalness | float | Likelihood of no vocals (0.0-1.0) |
| duration_ms | int | Track length in milliseconds |

Genre-based audio profiles shape realistic feature distributions (e.g., electronic tracks have high danceability/energy, jazz has high acousticness).

### Artists in the catalog

| Track IDs | Artist | Genre |
|---|---|---|
| t001, t010, t015 | Luna Park | electronic |
| t002, t008, t016 | Rosa Vega | pop, latin |
| t003, t009, t017 | Ghost Protocol | hip-hop |
| t004, t011, t018 | Ama Diallo | r&b |
| t005, t012, t019 | Neon Bridges | indie |
| t006, t014, t020 | The Midnight Waves | rock |
| t007, t013 | Kira Sato | jazz |

## Using Your Own Data

The sample music data is just a starting point. To use your own data, you need to create a `feature_definitions.py` that describes your feature store schema. This file is what tells Feast about your entities, features, and data sources.

### 1. Write your feature definitions

Create or edit `feature_repo/feature_definitions.py`. You need to define:

- **Entities** — the primary keys for feature lookups (e.g. `user_id`, `product_id`)
- **Data sources** — where your raw data lives (Parquet files, BigQuery tables, etc.)
- **Feature views** — groups of features tied to an entity and source, with field names, types, and a TTL
- **Feature services** (optional) — bundles of feature views that get served together

See the included `feature_definitions.py` for a working example.

### 2. Prepare your data

Your data source needs at minimum:
- A column matching each entity's join key
- A timestamp column for point-in-time correctness
- Columns for each feature in your schema

If using local files, place Parquet files in `feature_repo/data/`.

### 3. Apply and materialize

```bash
cd feature_repo
uv run feast apply
uv run feast materialize-incremental $(date -u +"%Y-%m-%dT%H:%M:%S")
cd ..
```

### 4. Chat with your data

Run `uv run python chat.py`. The MCP tools and system prompt are generic — they'll discover your feature views, entities, and schemas automatically. No code changes needed in the server or client.

### Connect to a remote data source

Replace `FileSource` with a BigQuery, Snowflake, or Redshift source in `feature_definitions.py`. Feast supports many [offline stores](https://docs.feast.dev/reference/offline-stores).

### Add historical feature retrieval

Add a tool that wraps `store.get_historical_features()` for generating training datasets with point-in-time correct joins — the core Feast workflow for ML training pipelines.

### Add feature freshness monitoring

Add a tool that checks when features were last materialized and alerts on stale data. In production, this would integrate with monitoring systems to enforce freshness SLAs.
