"""Outbound-network policy for model and sink endpoints. Air-gapped by default."""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, TypeAlias
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

EgressMode: TypeAlias = Literal["air_gapped", "private", "hybrid"]
MODE_ENV_VAR = "OBSEI_EGRESS_MODE"
ALLOW_ENV_VAR = "OBSEI_EGRESS_ALLOW"
IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address

_INET_PART = re.compile(r"0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*")
_INTERNAL_SUFFIXES = (".localhost", ".internal", ".local")
_MAX_PARTS = 4
_OCTET = 0xFF


EGRESS: Mapping[str, object] = MappingProxyType({"obsei_egress": True})
"""Pass as ``extensions=EGRESS`` on requests that carry feedback out (sinks): every hop, redirects
included, must then pass the egress policy."""


class EgressError(PermissionError):
    pass


def _inet_aton(host: str) -> ipaddress.IPv4Address | None:
    """IPv4 parsed like ``getaddrinfo``: 1-4 decimal, octal (0...) or hex (0x...) parts.

    Raises ValueError for numeric forms out of range; returns None for host names."""
    parts = host.split(".")
    if len(parts) > _MAX_PARTS or not all(_INET_PART.fullmatch(p) for p in parts):
        return None
    values = [
        int(p, 16) if p[:2] in ("0x", "0X") else int(p, 8 if p[0] == "0" else 10) for p in parts
    ]
    *head, last = values
    if any(v > _OCTET for v in head) or last >= 1 << (8 * (_MAX_PARTS - len(head))):
        raise ValueError(f"invalid IPv4 address {host!r}")
    number = last
    for index, value in enumerate(head):
        number |= value << (8 * (_MAX_PARTS - 1 - index))
    return ipaddress.IPv4Address(number)


def parse_address(host: str) -> IPAddress | None:
    """The IP address ``host`` names (IPv4-mapped IPv6 unwrapped), or None for a host name."""
    host = host.strip("[]").rstrip(".").lower()
    v4 = _inet_aton(host)
    if v4 is not None:
        return v4
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def is_internal(host: str) -> bool:
    """Private, loopback or link-local addresses, ``localhost``, ``*.localhost``, ``*.internal``,
    ``*.local`` and single-label (non-numeric) names."""
    try:
        address = parse_address(host)
    except ValueError:
        return False
    if address is not None:
        return address.is_private or address.is_loopback or address.is_link_local
    name = host.rstrip(".").lower()
    return name == "localhost" or name.endswith(_INTERNAL_SUFFIXES) or "." not in name


class EgressPolicy(BaseModel):
    """``air_gapped``: internal hosts only. ``private``: plus ``allowed_hosts``. ``hybrid``: any."""

    model_config = ConfigDict(frozen=True)

    mode: EgressMode = "air_gapped"
    allowed_hosts: frozenset[str] = frozenset()

    @classmethod
    def from_env(cls) -> EgressPolicy:
        mode = os.environ.get(MODE_ENV_VAR, "air_gapped")
        hosts = {
            h.strip().lower() for h in os.environ.get(ALLOW_ENV_VAR, "").split(",") if h.strip()
        }
        return cls.model_validate({"mode": mode, "allowed_hosts": hosts})

    def _allowlisted(self, host: str) -> bool:
        return any(host == h or host.endswith(f".{h}") for h in self.allowed_hosts)

    def check(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
        if not host:
            raise EgressError(f"endpoint {url!r} has no host")
        if self.mode == "hybrid" or is_internal(host):
            return
        if self.mode == "private" and self._allowlisted(host):
            return
        raise EgressError(
            f"egress to {host!r} is blocked in {self.mode} mode; "
            f"set {MODE_ENV_VAR}=private and add it to {ALLOW_ENV_VAR}, or use hybrid mode"
        )
