.PHONY: chat dev test setup

# Start the interactive chat REPL
chat:
	uv run python chat.py

# Debug server in MCP Inspector (http://localhost:5173)
dev:
	uv run mcp dev mcp_servers/feast_server.py

# Run tests
test:
	uv run python -m pytest tests/

# Generate data and set up Feast
setup:
	uv run python generate_data.py
	cd feature_repo && uv run feast apply && uv run feast materialize-incremental $$(date -u +"%Y-%m-%dT%H:%M:%S")
