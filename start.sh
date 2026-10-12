#!/bin/sh
# Single image, two roles (Render runs one service per role).
# ROLE=backend: public FastAPI only; agent turns attach to the remote box.
# ROLE=opencode: `opencode serve` on $PORT (Render requires 0.0.0.0:$PORT);
#   MCP tour-catalog runs in-process project via `uv run --project .`.
set -eu
if [ "${ROLE:-backend}" = "opencode" ]; then
  exec opencode serve --hostname 0.0.0.0 --port "${PORT:-4098}"
else
  exec uv run tour-backend serve --host 0.0.0.0 --port "${PORT:-8000}"
fi
