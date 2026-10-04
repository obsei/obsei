"""Package version. release-please rewrites RELEASE_VERSION; ``__version__`` is its PEP 440 form."""

import re

RELEASE_VERSION = "1.0.0-rc.1"  # x-release-please-version

_PRERELEASE = {"alpha": "a", "beta": "b", "rc": "rc"}
_SEMVER = re.compile(r"(?P<release>\d+\.\d+\.\d+)(?:-(?P<kind>alpha|beta|rc)(?:\.(?P<num>\d+))?)?")


def pep440(version: str) -> str:
    """Normalise a release-please version such as ``1.0.0-alpha.1`` to PEP 440 (``1.0.0a1``)."""
    match = _SEMVER.fullmatch(version)
    if match is None:
        raise ValueError(f"unsupported version {version!r}")
    kind = match["kind"]
    if kind is None:
        return match["release"]
    return f"{match['release']}{_PRERELEASE[kind]}{int(match['num'] or 0)}"


__version__ = pep440(RELEASE_VERSION)
