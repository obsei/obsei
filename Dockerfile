# syntax=docker/dockerfile:1
# obsei container image: one rootless image for CLI, server and MCP.
# Dependencies come from uv.lock, so the image runs exactly what CI tested.

FROM ghcr.io/astral-sh/uv:0.12.24@sha256:3af4716e991d6956a41e573eab705d0ee08500cd829ed30293eb8472f372c65a AS uv

FROM python:3.12-slim-trixie@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016 AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    UV_FROZEN=1 UV_NO_DEV=1 UV_PROJECT_ENVIRONMENT=/opt/obsei
ARG EXTRAS="--extra apple --extra google --extra mcp --extra sql"
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages/obsei/pyproject.toml packages/obsei/
COPY plugins/obsei-reddit/pyproject.toml plugins/obsei-reddit/
COPY plugins/obsei-teams/pyproject.toml plugins/obsei-teams/
COPY plugins/obsei-typeform/pyproject.toml plugins/obsei-typeform/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package obsei --no-install-workspace $EXTRAS
COPY packages ./packages
COPY plugins ./plugins
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package obsei --no-editable $EXTRAS
# Pre-install DuckDB's OpenSSL-backed extension so encrypted stores work offline, for any UID.
RUN /opt/obsei/bin/python -c "import duckdb; duckdb.connect(config={'extension_directory': '/opt/duckdb/extensions'}).execute('INSTALL httpfs')" \
    && chmod -R a+rX /opt/duckdb

FROM python:3.12-slim-trixie@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016
LABEL org.opencontainers.image.source="https://github.com/obsei/obsei" \
      org.opencontainers.image.description="Privacy-first, self-hosted Voice of Customer for AI agents" \
      org.opencontainers.image.licenses="Apache-2.0"
RUN useradd --no-create-home --home-dir /tmp --uid 10001 obsei \
    && install -d -m 1777 /data
COPY --from=build /opt/obsei /opt/obsei
COPY --from=build /opt/duckdb /opt/duckdb
COPY docker/healthcheck.py /opt/obsei/healthcheck.py
# HOME is writable for any UID so DuckDB and model caches work under `--user $(id -u):$(id -g)`.
ENV PATH="/opt/obsei/bin:${PATH}" PYTHONUNBUFFERED=1 HOME=/tmp \
    OBSEI_DUCKDB_EXTENSIONS=/opt/duckdb/extensions
USER 10001
WORKDIR /data
EXPOSE 8765
# Probes /healthz only when the container runs `obsei serve`; one-shot commands always pass.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "/opt/obsei/healthcheck.py"]
ENTRYPOINT ["obsei"]
CMD ["--help"]
