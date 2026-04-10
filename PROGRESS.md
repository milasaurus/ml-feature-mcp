# Progress

## Completed

- [x] Project setup (`uv init`, dependencies: feast, mcp, anthropic)
- [x] Feast feature repo with music streaming data (listener_stats, track_features)
- [x] Sample data generator (`generate_data.py`) with genre-based audio feature profiles
- [x] `feast apply` + `feast materialize-incremental` — online store populated
- [x] MCP client (`mcp_client.py`) — connect, discover tools, route tool calls through MCP to Claude
- [x] Claude integration — streaming, extended thinking, prompt caching, tool caching
- [x] Chat REPL (`chat.py`) — separated from client for reusability
- [x] System prompt (`system_prompt.py`) — generic, works with any Feast feature store
- [x] MCP server scaffold (`mcp_servers/feast_server.py`) — TODO outline for tools
- [x] Documentation (README, GUIDE, CLAUDE.md, PLAN.md)
- [x] GitHub repo created and pushed (milasaurus/ml-feature-mcp)

## In Progress

- [x] **Step 2: MCP Server** — implement the Feast tools in `mcp_servers/feast_server.py`
  - [x] Initialize FastMCP server + Feast FeatureStore
  - [x] `list_feature_views` — registered views with schemas, entities, TTL, tags
  - [x] `list_entities` — entity definitions and join keys
  - [x] `list_data_sources` — source names, types, paths, timestamp columns
  - [x] `list_feature_services` — services and which views they bundle
  - [x] `get_online_features` — fetch latest feature values for entity rows
  - [x] `describe_feature_view` — detailed schema for a single view
  - [ ] Test all tools in MCP Inspector (`uv run mcp dev mcp_servers/feast_server.py`)

## Remaining

- [x] **Step 3: End-to-end test** — run `chat.py` and verify full flow
  - [x] "What feature views are available?"
  - [x] "Get me the features for user 1001"
  - [x] "Compare tracks t001 and t006"
  - [x] "What entities are defined?"
  - [x] Multi-turn conversation works

- [ ] **Step 4: Commit + PR**
  - [ ] Final commit on `feat/mcp-server`
  - [ ] Push and open PR to main

- [ ] **Step 5: Tests**
  - [ ] Unit tests for MCP server tools (mock Feast FeatureStore, verify JSON output)
  - [ ] Unit tests for MCP client (mock ClientSession + Anthropic, verify tool routing)
  - [ ] Integration test: client connects to real server, discovers tools
  - [ ] E2E test: full chat flow with live Feast + Claude API

## Future

- [ ] **Multi-server support** — connect to multiple MCP servers simultaneously
  - [ ] `connect()` accepts a list of server scripts
  - [ ] Each server gets its own `ClientSession`
  - [ ] Tools from all servers merged into one list for Claude
  - [ ] Tool call routing looks up which session owns each tool
  - [ ] Example: Feast server + MLflow server running side by side
