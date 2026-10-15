"""Agents only propose; a human approves before anything leaves obsei.

Free text an agent wrote after reading feedback can carry injected instructions, so it is held
here until someone with the admin role (or shell access, via ``obsei approvals``) approves it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime

import httpx

from obsei.config import ObseiConfig, SinkEntry, builtin_registry
from obsei.core.context import Context
from obsei.core.protocols import OpensIssues
from obsei.core.record import Record
from obsei.store import Approval, ApprovalResult, ApprovalStatus, IssueProposal, Store

StoreOpener = Callable[[], AbstractContextManager[Store]]
ISSUE_SINKS = frozenset({"github_issues", "jira", "linear"})
NOTICE = "> Proposed by an AI agent via obsei; review before acting."


class ApprovalError(ValueError):
    pass


def targets(config: ObseiConfig) -> dict[str, SinkEntry]:
    """Issue sinks by key; a key used for different sinks in several pipelines is qualified as
    ``pipeline/key``."""
    found: dict[str, list[tuple[str, SinkEntry]]] = {}
    for pipeline in config.pipelines:
        for sink in pipeline.sinks:
            if sink.type in ISSUE_SINKS:
                found.setdefault(sink.name, []).append((pipeline.name, sink))
    named: dict[str, SinkEntry] = {}
    for key, entries in found.items():
        if all(sink == entries[0][1] for _, sink in entries):
            named[key] = entries[0][1]
        else:
            named.update({f"{pipeline}/{key}": sink for pipeline, sink in entries})
    return named


def propose(store: Store, config: ObseiConfig, proposal: IssueProposal, by: str) -> Approval:
    known = targets(config)
    if proposal.target not in known:
        raise ApprovalError(f"no issue sink {proposal.target!r}; targets are {sorted(known)}")
    unknown = [r for r in proposal.record_ids if store.get(r) is None]
    if unknown:
        raise ApprovalError(f"no records {unknown}")
    approval = Approval(
        id=f"apr_{uuid.uuid4().hex}",
        payload=proposal,
        proposed_by=by,
        proposed_at=datetime.now(UTC),
    )
    store.add_approval(approval)
    _audit(store, approval, "proposed", by)
    return approval


def issue_body(proposal: IssueProposal, records: list[Record | None]) -> str:
    cited = [
        f"- `{rid}`" + (f" ({r.source.type}) {r.source.url}" if r and r.source.url else "")
        for rid, r in zip(proposal.record_ids, records, strict=True)
    ]
    parts = [NOTICE, proposal.body]
    if cited:
        parts.append("Cited feedback:\n" + "\n".join(cited))
    return "\n\n".join(parts)


def approve(
    open_store: StoreOpener, config: ObseiConfig, ctx: Context, approval_id: str, by: str
) -> Approval:
    """Opens the issue once. A failed approval can be approved again; the sink finds an issue
    an earlier attempt opened by its approval id, so a retry never opens a second one."""
    with open_store() as store:
        claimed = store.decide_approval(approval_id, "approved", by, was=("pending", "failed"))
        if claimed is None:
            raise ApprovalError(_not_open(store, approval_id))
        records = [store.get(r) for r in claimed.payload.record_ids]
    proposal = claimed.payload
    result = ApprovalResult()
    try:
        target = targets(config).get(proposal.target)
        if target is None:
            raise ApprovalError(f"issue sink {proposal.target!r} is no longer configured")
        sink = builtin_registry(config.plugins).sink(target.type).create(target.config, ctx)
        if not isinstance(sink, OpensIssues):
            raise ApprovalError(f"sink {target.type!r} cannot open issues")
        result.created = sink.open_issue(proposal.title, issue_body(proposal, records), claimed.id)
    except (RuntimeError, OSError, ValueError, httpx.HTTPError) as exc:
        result.error = str(exc)
    with open_store() as store:
        status: ApprovalStatus = "failed" if result.error else "approved"
        done = store.decide_approval(approval_id, status, by, was=("approved",), result=result)
        if done is None:
            raise ApprovalError(_not_open(store, approval_id))
        _audit(store, done, done.status, by)
    return done


def reject(store: Store, approval_id: str, by: str, reason: str | None = None) -> Approval:
    done = store.decide_approval(
        approval_id, "rejected", by, was=("pending", "failed"), result=ApprovalResult(reason=reason)
    )
    if done is None:
        raise ApprovalError(_not_open(store, approval_id))
    _audit(store, done, "rejected", by)
    return done


def _not_open(store: Store, approval_id: str) -> str:
    found = store.approvals(approval_id=approval_id)
    return f"approval {approval_id} is {found[0].status}" if found else f"no approval {approval_id}"


def _audit(store: Store, approval: Approval, decision: str, by: str) -> None:
    store.audit(
        "approval",
        {"id": approval.id, "target": approval.payload.target, "decision": decision, "by": by},
    )
