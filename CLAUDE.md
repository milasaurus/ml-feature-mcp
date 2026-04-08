# CLAUDE.md

## Commands

```bash
uv run python chat.py            # Run the interactive REPL (spawns server automatically)
uv run mcp dev mcp_server.py     # Debug server in MCP Inspector (http://localhost:5173)
uv run python -m pytest tests/   # Run tests
```

## Claude API Defaults

When calling the Anthropic API, always use:

- **Streaming**: Use `client.messages.stream()`, not `client.messages.create()`
- **Extended thinking**: Enable with `thinking={"type": "enabled", "budget_tokens": 5000}`
- **Prompt caching**: Mark system prompt with `cache_control: {"type": "ephemeral"}`. Mark the last tool definition with `cache_control: {"type": "ephemeral"}`
- **Max tokens**: Default to `max_tokens=16000`
- **Model**: `claude-haiku-4-5-20251001`

## Code Standards

- Python 3.10+
- Use `uv` for package management
- 4 spaces for indentation
- snake_case for functions and variables, PascalCase for classes
- Use named parameters for hardcoded values
- API key from environment (`ANTHROPIC_API_KEY`), never hardcoded

## After Making Changes

After any code or structural change, check if these files need updating:
- `README.md` — project structure, data model, quick start commands
- `GUIDE.md` — example workflows, sample data tables, setup instructions
- `CLAUDE.md` — commands, API defaults, code standards
