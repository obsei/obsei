# syntax=docker/dockerfile:1
# obsei container image: one rootless image for CLI, server and MCP.
# Dependencies come from uv.lock, so the image runs exactly what CI tested.

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.12-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    UV_FROZEN=1 UV_NO_DEV=1 UV_PROJECT_ENVIRONMENT=/opt/obsei
ARG EXTRAS="--extra apple --extra google --extra mcp --extra sql"
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages/obsei/pyproject.toml packages/obsei/
COPY plugins/obsei-reddit/pyproject.toml plugins/obsei-reddit/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package obsei --no-install-workspace $EXTRAS
COPY packages ./packages
COPY plugins ./plugins
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package obsei --no-editable $EXTRAS
# Pre-install DuckDB's OpenSSL-backed extension so encrypted stores work offline, for any UID.
RUN /opt/obsei/bin/python -c "import duckdb; duckdb.connect(config={'extension_directory': '/opt/duckdb/extensions'}).execute('INSTALL httpfs')" \
    && chmod -R a+rX /opt/duckdb

FROM python:3.12-slim-trixie
LABEL org.opencontainers.image.source="https://github.com/obsei/obsei" \
      org.opencontainers.image.description="Privacy-first, self-hosted Voice of Customer for AI agents" \
      org.opencontainers.image.licenses="Apache-2.0"
RUN useradd --create-home --uid 10001 obsei \
    && install -d -m 1777 /data
COPY --from=build /opt/obsei /opt/obsei
COPY --from=build /opt/duckdb /opt/duckdb
COPY docker/healthcheck.py /opt/obsei/healthcheck.py
ENV PATH="/opt/obsei/bin:${PATH}" PYTHONUNBUFFERED=1 \
    OBSEI_DUCKDB_EXTENSIONS=/opt/duckdb/extensions
USER 10001
WORKDIR /data
EXPOSE 8765
# Probes /healthz only when the container runs `obsei serve`; one-shot commands always pass.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "/opt/obsei/healthcheck.py"]
ENTRYPOINT ["obsei"]
CMD ["--help"]
