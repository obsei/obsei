# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/obsei/obsei/security/advisories/new).
Do not open public issues for security problems.

Include affected versions, a description, reproduction steps and the impact you expect. Please do
not include real personal data.

## What to expect

obsei is maintained part-time. Security fixes are best-effort, with a target of a fix or mitigation
within 30 days of a confirmed report. Fixes are published as GitHub security advisories.

## Supported versions

Only the latest release line receives security fixes. The 0.0.x line is no longer maintained.

## Scope notes

- obsei is self-hosted software; deployers are responsible for their infrastructure, credentials
  and data-protection obligations.
- Community plugins are not security-reviewed or sandboxed by the maintainers. Install only the
  plugins you trust, and use an explicit plugin allowlist in server mode.
