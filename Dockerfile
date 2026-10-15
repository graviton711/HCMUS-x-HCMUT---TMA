# Shared service image for the backend, OpenCode survey server and Codex
# gateway roles. Render keeps the agent provider separate from the backend.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITECODE=1 \
    PYTHONUNBUFFERED=1

# Node.js 22 for OpenCode survey and the pinned Codex CLI gateway. Needs curl
# + CA certs on slim.
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
    && npm install -g opencode-ai @openai/codex@0.162.1 \
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
