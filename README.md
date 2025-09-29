# MCP Bridge: Obsidian × Ollama × Gemini (HTTP‑style)

> TL;DR: This is an experimental, HTTP‑only “MCP‑ish” bridge that lets you hit simple tools (discover files, analyze a file with Ollama) via REST. It’s great with curl, decent with scripts, and… occasionally moody with Gemini CLI.

## The Saga (human, honest, and a bit funny)
 - The idea: “There’s no clean bridge to use Obsidian with Ollama inside Gemini CLI. I can’t do it in the Ollama shell, so… let’s route it through Gemini CLI. Gemini, you handle the interaction and search my vault; Ollama does the heavy lifting.”
- The ego tussle: Gemini said, “Bro, I can answer these myself.” Ollama said, “Let me cook.” Our bridge said, “I’ll just be here… translating.”
- Reality check: Gemini loves proper MCP over JSON‑RPC. Our bridge currently speaks plain HTTP with JSON. So Gemini sometimes connects, sometimes throws a fit, and sometimes says “Disconnected” while the server is very much alive.

## What this actually is
- A small Flask app exposing:
  - `GET /mcp/health` and `GET|POST /` for basic health pings
  - `GET /mcp/version` for a version hint
  - `GET /mcp/tools` to list available tools
  - `POST /mcp/tools/discover_files` to find files recursively by pattern
  - `POST /mcp/tools/analyze_file` to read a file and ask Ollama about it
- Perfect for direct HTTP calls (curl, scripts). Not a full MCP JSON‑RPC server.

## What this is NOT (yet)
- Not a spec‑compliant MCP server. Gemini expects JSON‑RPC methods like `initialize`, `tools/list`, and `tools/call`. We don’t (yet) implement those.
- Because of that, Gemini CLI may display the server as “Disconnected” even while endpoints work fine.

## Repo layout
```
MCP/
├─ .env
├─ .gemini/
│  └─ settings.json   # Local CLI config (optional; you can also use ~/.gemini/settings.json)
├─ mcp_bridge.py       # The HTTP bridge
└─ requirements.txt    # Flask + friends
```

## Requirements
- Python 3.10+
- `pip install -r requirements.txt`
- Ollama running locally (`http://localhost:11434`) with a model available.
  - By default, the code calls `qwen3:1.7b`. You can edit `call_ollama_api` in `mcp_bridge.py` to change the model.

## API Requirements (what needs to be configured)
- Ollama API: Local server listening at `http://localhost:11434`. The bridge posts to `/api/generate` with your chosen model. Install your model in Ollama beforehand.
- Obsidian: This bridge does not directly call Obsidian’s API. If you want Obsidian vault operations from Gemini, use the `obsidian-mcp-tools` plugin separately. The bridge’s `discover_files` can still browse your vault folder like normal files.

## Quick start
1) Configure environment (optional)
```
# .env
HOST=0.0.0.0
PORT=5004
```

2) Start the bridge
```
python3 mcp_bridge.py
```
You should see it listening on `http://127.0.0.1:5004`.

3) Health check
```
curl http://localhost:5004/mcp/health
# => {"status":"ok"}
```

4) List tools
```
curl http://localhost:5004/mcp/tools
# => {"tools":[...]}
```

5) Discover files (recursive)
```
curl -X POST http://localhost:5004/mcp/tools/discover_files \
  -H "Content-Type: application/json" \
  -d '{"directory":"/Users/you/Documents","pattern":"*.md"}'
```

6) Analyze a file with Ollama
```
curl -X POST http://localhost:5004/mcp/tools/analyze_file \
  -H "Content-Type: application/json" \
  -d '{"file_path":"/path/to/file.md","query":"Summarize this"}'
```

## Using with Gemini CLI (HTTP transport)
This bridge is HTTP‑style. Gemini prefers proper MCP over JSON‑RPC, but you can still try:

Option A: Project settings (`MCP/.gemini/settings.json`)
```
{
  "mcpServers": {
    "ollama-bridge": {
      "command": "python3",
      "args": ["/Users/you/MCP/mcp_bridge.py"],
      "env": {},
      "httpUrl": "http://localhost:5004",
      "transport": "http"
    }
  }
}
```

Option B: Global settings (`~/.gemini/settings.json`)
- Same block as above, added under `mcpServers` to make it available everywhere.

Then check:
```
gemini mcp list
```
If it shows “Disconnected”, the HTTP endpoints still work via curl. That’s expected until this bridge speaks JSON‑RPC like a full MCP server.

## Troubleshooting
- Port conflicts: Make sure `PORT=5004` in `.env`, no other process on 5004.
- Health oddities: We allow `GET` and `POST` on `/` and `GET` on `/mcp/health`.
- Obsidian plugin errors: Unrelated to this bridge; they come from `obsidian-mcp-tools`.
- Home folder scan errors in Gemini: Permission issues (e.g., `~/.Trash`). Try running Gemini in a narrower working directory.
- Ollama not responding: Ensure `ollama serve` is running and the model name in `call_ollama_api` exists locally.

## Roadmap (a.k.a. how we’ll make Gemini happy)
- Add JSON‑RPC 2.0 endpoint (likely at `POST /`) to handle:
  - `initialize` (capabilities, tools)
  - `tools/list` (enumerate schemas)
  - `tools/call` (execute and return results)
- Optional stdio transport for tighter Gemini integration.

## Contributing / Sharing
- Open an issue for bugs, ideas, or JSON‑RPC help.
- PRs welcome. Keep it simple and focused.
- If you fork for GitHub, this README is ready to go.

## Acknowledgements
- Gemini, for being talented and occasionally opinionated.
- Ollama, for doing the heavy lifting.
- You, for reading this and giving the bridge a spin.