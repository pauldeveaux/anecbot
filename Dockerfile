FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY README.md ./
RUN uv sync --frozen --no-dev

FROM python:3.14-slim-bookworm

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin anecbot
WORKDIR /app

COPY --from=builder --chown=anecbot:anecbot /app/.venv /app/.venv
COPY --chown=anecbot:anecbot src/ src/
COPY --chown=anecbot:anecbot migrations/ migrations/
COPY --chown=anecbot:anecbot RELEASE_NOTES.md ./

USER anecbot
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "anecbot"]
