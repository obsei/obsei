"""Outbound-network policy for model endpoints. Air-gapped by default."""

from __future__ import annotations

import ipaddress
import os
from typing import Literal, TypeAlias
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

EgressMode: TypeAlias = Literal["air_gapped", "private", "hybrid"]
MODE_ENV_VAR = "OBSEI_EGRESS_MODE"
ALLOW_ENV_VAR = "OBSEI_EGRESS_ALLOW"


class EgressError(PermissionError):
    pass


def _is_internal(host: str) -> bool:
    if host == "localhost" or "." not in host:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith((".localhost", ".internal", ".local"))
    return address.is_private or address.is_loopback or address.is_link_local


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
        host = (urlsplit(url).hostname or "").lower()
        if not host:
            raise EgressError(f"endpoint {url!r} has no host")
        if _is_internal(host) or self.mode == "hybrid":
            return
        if self.mode == "private" and self._allowlisted(host):
            return
        raise EgressError(
            f"egress to {host!r} is blocked in {self.mode} mode; "
            f"set {MODE_ENV_VAR}=private and add it to {ALLOW_ENV_VAR}, or use hybrid mode"
        )
