"""Container HEALTHCHECK: probe /healthz when PID 1 is `obsei serve`, otherwise report healthy."""

import sys
import urllib.request
from pathlib import Path


def serve_url(argv: list[str]) -> str | None:
    if "serve" not in argv:
        return None
    host, port = "127.0.0.1", "8765"
    for i, arg in enumerate(argv):
        name, _, value = arg.partition("=")
        if name in ("--host", "--port") and not value and i + 1 < len(argv):
            value = argv[i + 1]
        if name == "--host" and value not in ("", "0.0.0.0", "::"):  # noqa: S104
            host = value
        elif name == "--port" and value:
            port = value
    if ":" in host:
        host = f"[{host}]"
    return f"http://{host}:{port}/healthz"


def main() -> int:
    argv = Path("/proc/1/cmdline").read_bytes().decode().split("\0")
    url = serve_url(argv)
    if url is None:
        return 0
    with urllib.request.urlopen(url, timeout=4) as response:  # noqa: S310
        return 0 if response.status == 200 else 1  # noqa: PLR2004


if __name__ == "__main__":
    sys.exit(main())
