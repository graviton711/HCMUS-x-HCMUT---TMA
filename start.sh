#!/bin/sh
# Single image, multiple roles (Render runs one service per role).
# ROLE=backend: public FastAPI only; agent turns attach to the remote box.
# ROLE=opencode: `opencode serve` on $PORT (Render requires 0.0.0.0:$PORT);
#   MCP tour-catalog runs in-process project via `uv run --project .`.
# ROLE=codex: Codex CLI gateway on $PORT; keep OpenCode in the Render blueprint
#   until hosted ChatGPT plan eligibility is confirmed.
set -eu
if [ "${ROLE:-backend}" = "opencode" ]; then
  # Warm the MCP interpreter + imports once at boot: on 0.1 CPU the first
  # `uv run` (page cache cold, .pyc fresh) exceeds the MCP spawn budget and
  # every later spawn reuses the warm cache. No pipe: a failed warmup must
  # crash the deploy loudly instead of serving a dead MCP.
  uv run --project . python -c "import backend.agent.mcp_server; print('mcp warm')"
  exec opencode serve --hostname 0.0.0.0 --port "${PORT:-4098}"
elif [ "${ROLE:-backend}" = "codex" ]; then
  exec uv run tour-codex serve --host 0.0.0.0 --port "${PORT:-4099}"
else
  exec uv run tour-backend serve --host 0.0.0.0 --port "${PORT:-8000}"
fi
