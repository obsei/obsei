"""Who may use ``obsei serve``: named tokens with roles, or users vouched for by an SSO proxy.

viewer: Studio aggregates and themes. analyst: also redacted evidence, Ask and MCP.
admin: also pipeline run status. Every evidence, Ask and MCP request is written to the audit log.
"""

from __future__ import annotations

import hmac
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

Role: TypeAlias = Literal["viewer", "analyst", "admin"]
RANK: dict[Role, int] = {"viewer": 1, "analyst": 2, "admin": 3}
PUBLIC_PATHS = ("/healthz", "/ingest/", "/studio", "/slack/")
RULES: tuple[tuple[str, Role], ...] = (
    ("/api/runs", "admin"),
    ("/api/themes/", "analyst"),
    ("/api/ask", "analyst"),
    ("/mcp", "analyst"),
    ("/api/", "viewer"),
)
AUDITED: frozenset[Role] = frozenset({"analyst", "admin"})
MIN_SECRET = 16


class UserToken(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    token_env: str
    role: Role = "viewer"


class TrustedProxy(BaseModel):
    """For an SSO proxy (oauth2-proxy, Pomerium, Cloudflare Access) in front of obsei.

    The proxy must send ``secret_header`` with the shared secret, so requests that bypass it are
    refused. Users get the highest role whose groups they belong to, else ``default_role``.
    """

    model_config = ConfigDict(extra="forbid")

    secret_env: str
    secret_header: str = "x-obsei-proxy-secret"  # noqa: S105
    user_header: str = "x-forwarded-email"
    groups_header: str = "x-forwarded-groups"
    roles: dict[Role, list[str]] = Field(default_factory=dict)
    default_role: Role | None = None


class AccessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    users: list[UserToken] = Field(default_factory=list)
    trusted_proxy: TrustedProxy | None = None


class AccessError(RuntimeError):
    pass


@dataclass(frozen=True)
class Principal:
    name: str
    role: Role


def required_role(path: str) -> Role | None:
    """None for public paths (they authenticate themselves) and unknown paths."""
    if path.startswith(PUBLIC_PATHS):
        return None
    return next((role for prefix, role in RULES if path.startswith(prefix)), "admin")


def _secret(env: str) -> str:
    value = os.environ.get(env, "")
    if len(value) < MIN_SECRET:
        raise AccessError(f"{env} must be set to a secret of at least {MIN_SECRET} characters")
    return value


class Authenticator:
    def __init__(self, config: AccessConfig, admin_token: str | None) -> None:
        self.tokens: list[tuple[str, Principal]] = [
            (_secret(u.token_env), Principal(u.name, u.role)) for u in config.users
        ]
        if admin_token:
            self.tokens.append((admin_token, Principal("admin", "admin")))
        self.proxy = config.trusted_proxy
        self.proxy_secret = _secret(self.proxy.secret_env) if self.proxy else ""

    @property
    def enabled(self) -> bool:
        return bool(self.tokens) or self.proxy is not None

    def _from_proxy(self, headers: Mapping[str, str]) -> Principal | None:
        proxy = self.proxy
        if proxy is None:
            return None
        headers = {k.lower(): v for k, v in headers.items()}
        given = headers.get(proxy.secret_header.lower(), "")
        user = headers.get(proxy.user_header.lower(), "").strip()
        if not given or not hmac.compare_digest(given, self.proxy_secret) or not user:
            return None
        groups = {g.strip() for g in headers.get(proxy.groups_header.lower(), "").split(",")}
        granted = [role for role, names in proxy.roles.items() if groups & set(names)]
        role = max(granted, key=RANK.__getitem__, default=proxy.default_role)
        return Principal(user, role) if role else None

    def resolve(self, headers: Mapping[str, str]) -> Principal | None:
        """``headers`` must have lower-case names."""
        header = headers.get("authorization", "")
        if header.startswith("Bearer "):
            token = header.removeprefix("Bearer ")
            for secret, principal in self.tokens:
                if hmac.compare_digest(token, secret):
                    return principal
            return None
        return self._from_proxy(headers)
