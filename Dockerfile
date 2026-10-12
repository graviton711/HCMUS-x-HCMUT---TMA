# Single-box demo image: FastAPI backend + local OpenCode server.
# Mirrors local dev: `opencode serve 127.0.0.1:4098` + `tour-backend serve`.
# The agent server only listens on container localhost; the only public
# surface is the backend on $PORT, which keeps its own session auth.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITECODE=1 \
    PYTHONUNBUFFERED=1

# Node.js 22 for the `opencode-ai` binary (same npm package the backend
# runner resolves locally). Needs curl + CA certs on slim.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g opencode-ai \
    && pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY configs/ ./configs/
COPY src/ ./src/
COPY opencode.json ./
COPY .opencode/ ./.opencode/
COPY start.sh ./
RUN chmod +x start.sh && uv sync --frozen --no-dev

EXPOSE 8000
CMD ["./start.sh"]
