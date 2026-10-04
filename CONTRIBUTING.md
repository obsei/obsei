# Contributing to obsei

Thanks for helping. obsei is maintained part-time, so clear, small, well-tested pull requests are
the fastest way to get changes merged.

## Where to talk

- **Questions and ideas:** [GitHub Discussions](https://github.com/obsei/obsei/discussions)
- **Bugs, features, connector requests:** [issue forms](https://github.com/obsei/obsei/issues/new/choose)
- **Security issues:** never in public; see [SECURITY.md](SECURITY.md)

## Development setup

You need [uv](https://docs.astral.sh/uv/) 0.12 or newer. uv installs the right Python for you.

```bash
git clone https://github.com/obsei/obsei && cd obsei
uv sync                 # creates .venv with obsei and the dev tools
uv run pytest           # tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # type-check (strict)
uv run obsei doctor     # try the CLI
```

The repository is a uv workspace. The installable package lives in `packages/obsei`.

## Pull requests

- **Title:** use [Conventional Commits](https://www.conventionalcommits.org/), e.g.
  `feat: add Zendesk source`, `fix: handle empty review text`. PRs are squash-merged and the title
  drives the changelog and version bump.
- **Tests:** every change needs tests. Network calls must be mocked or recorded; CI never calls
  real third-party APIs or downloads large models.
- **Privacy:** never commit personal data, real customer text, secrets or API keys, including in
  test fixtures. Use synthetic examples.
- **Plugins:** reference plugins by name through the registry; configuration must never import
  arbitrary code.

## Developer Certificate of Origin (DCO)

obsei uses the [DCO](https://developercertificate.org/) instead of a CLA. Sign off every commit to
certify you have the right to contribute it under the Apache-2.0 license:

```bash
git commit -s -m "feat: add Zendesk source"
```

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## For maintainers: releases

Releases are automated. Merging to `master` updates a release PR opened by release-please; merging
that PR tags the release, publishes to PyPI via Trusted Publishing and pushes a signed image to
`ghcr.io/obsei/obsei`. After the first 0.1.0 release, remove `"release-as": "0.1.0"` from
`release-please-config.json`.
