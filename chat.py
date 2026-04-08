"""Interactive REPL for chatting with the Feast feature store via MCP."""

import asyncio

from mcp_client import FeastMCPClient

async def main():
    async with FeastMCPClient() as client:
        await client.connect("mcp_servers/feast_server.py")

        print(f"Connected. Discovered {len(client.available_tools)} tools:")
        for tool in client.available_tools:
            print(f"  - {tool['name']}: {tool['description']}")
        print("\nReady! Ask me about the feature store. Type 'quit' to exit.\n")

        while True:
            try:
                user_input = input("You: ")
            except (EOFError, KeyboardInterrupt):
                break

            if user_input.strip().lower() in ("quit", "exit"):
                break

            response = await client.chat(user_input)
            print(f"\nClaude: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
