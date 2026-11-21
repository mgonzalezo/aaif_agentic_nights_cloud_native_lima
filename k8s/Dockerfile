# One image for the forge MCP server and the A2A reviewer.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY bestiary ./bestiary
COPY upstream ./upstream
COPY minimal_agent.py ./
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8765 9999
CMD ["python", "-m", "bestiary.services.forge_mcp", "--host", "0.0.0.0"]
