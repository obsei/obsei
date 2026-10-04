# syntax=docker/dockerfile:1
# obsei container image: one rootless image for CLI, server and MCP.

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.12-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv build --package obsei --out-dir /dist \
    && uv venv /opt/obsei \
    && uv pip install --python /opt/obsei /dist/*.whl

FROM python:3.12-slim-trixie
LABEL org.opencontainers.image.source="https://github.com/obsei/obsei" \
      org.opencontainers.image.description="Privacy-first, self-hosted Voice of Customer for AI agents" \
      org.opencontainers.image.licenses="Apache-2.0"
RUN useradd --create-home --uid 10001 obsei
COPY --from=build /opt/obsei /opt/obsei
ENV PATH="/opt/obsei/bin:${PATH}" PYTHONUNBUFFERED=1
USER 10001
WORKDIR /home/obsei
ENTRYPOINT ["obsei"]
CMD ["--help"]
