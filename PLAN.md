# Feast MCP — Project Plan

## Goal

Build a conversational management layer for a Feast feature store using MCP. The server exposes Feast SDK operations as tools (discovery, inspection, retrieval). The client connects to the server, discovers those tools, and routes Claude's tool calls through the protocol. Also a hands-on way to learn MCP concepts.

## What You'll Build

1. **MCP Server** — how to wrap an existing SDK (Feast) as MCP tools using `FastMCP` and `@mcp.tool()` decorators
2. **MCP Client** — how to connect to a server, discover tools via `list_tools()`, and call them via `call_tool()`
3. **Wiring MCP into Claude** — how to take discovered MCP tools, send them to Claude as tool definitions, and route `tool_use` responses back through MCP
4. **stdio transport** — how client and server communicate over stdin/stdout using JSON-RPC
5. **MCP Inspector** — how to debug and test your server in the browser before writing the client

## Architecture

```
You (terminal)
    │
    ▼
┌─────────────────────┐       stdio        ┌─────────────────────┐
│    client.py         │  ←───────────→    │    server.py         │
│                      │   (JSON-RPC)      │                      │
│  1. User types msg   │                    │  Wraps Feast SDK:    │
│  2. Send to Claude   │                    │                      │
│     with MCP tools   │                    │  @mcp.tool()         │
│  3. Claude returns   │                    │  list_feature_views  │
│     tool_use         │                    │  list_entities       │
│  4. Route via MCP:   │                    │  get_online_features │
│     session.call_tool│                    │  list_data_sources   │
│  5. Feed result back │                    │                      │
│  6. Print response   │                    │  Feast FeatureStore  │
│                      │                    │  (SQLite + Parquet)  │
└─────────────────────┘                     └─────────────────────┘
```

## Project Structure

```
feast-mcp/
├── feature_repo/              # Created by `feast init` (Step 1)
│   ├── data/
│   │   └── driver_stats.parquet
│   ├── feature_store.yaml     # Points at local SQLite online store
│   └── feature_definitions.py # Driver entity, feature views, feature service
├── server.py                  # MCP server — 4 tools wrapping Feast SDK
├── client.py                  # MCP client — REPL that talks to Claude via MCP tools
├── pyproject.toml
├── PLAN.md
└── README.md
```

## Prerequisites

- Python 3.10+
- `uv` installed
- `ANTHROPIC_API_KEY` set in your environment
- Node.js (for MCP Inspector only)

---

## Step 1: Project Setup + Feast Feature Repo

### 1a. Initialize the project

```bash
cd /Users/milawilson/Dev/feast-mcp
uv init
uv add feast anthropic "mcp[cli]"
```

### 1b. Create the Feast feature repo

```bash
uv run feast init feature_repo
```

This creates `feature_repo/` with:
- `data/driver_stats.parquet` — sample data with columns: `driver_id`, `conv_rate`, `acc_rate`, `avg_daily_trips`, `event_timestamp`, `created`
- `feature_store.yaml` — config pointing at local SQLite online store
- `feature_definitions.py` — defines:
  - **Entity**: `driver` (join key: `driver_id`)
  - **Feature view**: `driver_hourly_stats` with fields `conv_rate` (Float32), `acc_rate` (Float32), `avg_daily_trips` (Int64)
  - **On-demand feature view**: `transformed_conv_rate` (computed at request time)
  - **Feature service**: `driver_activity_v1`

### 1c. Apply definitions and materialize data

```bash
cd feature_repo
uv run feast apply
CURRENT_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S")
uv run feast materialize-incremental $CURRENT_TIME
cd ..
```

`feast apply` registers entities/features in the registry. `materialize-incremental` loads the parquet data into the SQLite online store so `get_online_features()` works.

### 1d. Verify it works

Quick smoke test — run in Python:

```python
from feast import FeatureStore

store = FeatureStore(repo_path="feature_repo")

# List what's registered
print("Feature views:", [fv.name for fv in store.list_feature_views()])
print("Entities:", [e.name for e in store.list_entities()])

# Fetch features for a driver
features = store.get_online_features(
    features=["driver_hourly_stats:conv_rate", "driver_hourly_stats:acc_rate"],
    entity_rows=[{"driver_id": 1001}],
).to_dict()
print("Features for driver 1001:", features)
```

**Done when**: You see feature views listed and get actual feature values back for a driver_id.

---

## Step 2: MCP Server (`server.py`)

Build a server that exposes 4 Feast operations as MCP tools.

### Key concepts

- `FastMCP("feast-server")` creates the server
- `@mcp.tool()` registers a function as a tool — name, description, and input schema are auto-generated from the function signature and docstring
- `mcp.run(transport="stdio")` starts the server on stdin/stdout
- **Never use `print()` to stdout** — it corrupts the JSON-RPC protocol. Use `logging` to stderr instead.

### Tools to implement

| Tool | Feast SDK Call | What it returns |
|---|---|---|
| `list_feature_views` | `store.list_feature_views()` | Names, schemas, entities, TTL for each view |
| `list_entities` | `store.list_entities()` | Entity names and join keys |
| `get_online_features` | `store.get_online_features(features, entity_rows)` | Feature values for given entity IDs |
| `list_data_sources` | `store.list_data_sources()` | Source names, types, paths |

### Example tool pattern

```python
from mcp.server.fastmcp import FastMCP
from feast import FeatureStore

mcp = FastMCP("feast-server")
store = FeatureStore(repo_path="feature_repo")

@mcp.tool()
def list_feature_views() -> str:
    """List all registered feature views and their schemas."""
    views = store.list_feature_views()
    result = []
    for fv in views:
        result.append({
            "name": fv.name,
            "entities": [e.name for e in fv.entities],
            "features": [f.name for f in fv.schema],
            "ttl": str(fv.ttl),
        })
    return json.dumps(result, indent=2)
```

### How to test the server standalone

```bash
uv run mcp dev server.py
```

This launches the **MCP Inspector** at `http://localhost:5173`. You can:
- See all registered tools
- Click a tool to see its input schema
- Call a tool with sample inputs and see the response
- Debug issues before writing any client code

**Done when**: All 4 tools show up in the Inspector and return correct data when called.

---

## Step 3: MCP Client (`client.py`)

Build a client that connects to the server, discovers tools, and wires them into a Claude conversation loop.

### Key concepts

- `StdioServerParameters(command="uv", args=["run", "python", "server.py"])` — tells the client how to spawn the server
- `stdio_client(server_params)` — opens a stdio connection to the server subprocess
- `ClientSession(read, write)` — the session object you use to talk to the server
- `session.initialize()` — MCP handshake (negotiate capabilities)
- `session.list_tools()` — discover what tools the server offers
- `session.call_tool(name, args)` — invoke a tool and get the result

### Client structure

```python
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from anthropic import Anthropic

class FeastMCPClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.messages = []           # Conversation history
        self.available_tools = []    # Discovered MCP tools

    async def connect(self, server_script: str):
        """Spawn the server and connect via stdio."""
        # 1. Create server params
        # 2. Open stdio transport
        # 3. Create ClientSession
        # 4. Call session.initialize()
        # 5. Call session.list_tools() and store them

    async def chat(self, user_message: str) -> str:
        """Send a message through Claude with MCP tools."""
        # 1. Append user message to self.messages
        # 2. Convert MCP tools to Anthropic tool format
        # 3. Call Claude API with messages + tools
        # 4. If stop_reason == "tool_use":
        #    a. For each tool_use block, call session.call_tool()
        #    b. Append assistant + tool results to messages
        #    c. Call Claude again
        # 5. Return final text response

    async def run(self):
        """REPL loop."""
        await self.connect("server.py")
        while True:
            user_input = input("You: ")
            if user_input.lower() in ("quit", "exit"):
                break
            response = await self.chat(user_input)
            print(f"Claude: {response}")
        await self.exit_stack.aclose()
```

### Converting MCP tools to Anthropic format

MCP tools from `list_tools()` have: `name`, `description`, `inputSchema`
Anthropic API expects: `name`, `description`, `input_schema`

```python
anthropic_tools = [
    {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.inputSchema,
    }
    for tool in self.available_tools
]
```

### Routing tool calls

When Claude returns a `tool_use` block:

```python
for block in response.content:
    if block.type == "tool_use":
        result = await self.session.call_tool(block.name, block.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": result.content[0].text,
        })
```

**Done when**: You can have a multi-turn conversation with Claude about the feature store.

---

## Step 4: Test It

### Run the client

```bash
uv run python client.py
```

The client spawns the server automatically as a subprocess.

### Example conversations to try

```
You: What feature views are available?
Claude: There's one feature view called "driver_hourly_stats" with features
        conv_rate, acc_rate, and avg_daily_trips for the driver entity...

You: Get me the features for driver 1001
Claude: Here are the features for driver 1001:
        - conv_rate: 0.83
        - acc_rate: 0.91
        - avg_daily_trips: 47

You: What about drivers 1002 and 1003?
Claude: [calls get_online_features for both drivers and shows results]

You: Where does this data come from?
Claude: The driver stats come from a parquet file at data/driver_stats.parquet...
```

### Debug with MCP Inspector

If something isn't working, test the server in isolation:

```bash
uv run mcp dev server.py
```

Open `http://localhost:5173`, call tools manually, and inspect the JSON-RPC messages to see what's going over the wire.

**Done when**: All 4 conversations above produce correct results.

---

## Dependencies

| Package | Purpose |
|---|---|
| `feast` | Feature store SDK — runs locally on SQLite + Parquet |
| `mcp[cli]` | MCP Python SDK (client + server + Inspector CLI) |
| `anthropic` | Claude API client |

## Key Reference: MCP Imports

```python
# Server
from mcp.server.fastmcp import FastMCP

# Client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
```

## Not in Scope

- Custom feature definitions (use Feast's built-in demo data)
- SSE/HTTP transport (stdio only)
- Historical feature retrieval (`get_historical_features`)
- Authentication or authorization
- Multi-server connections
- Production error handling
