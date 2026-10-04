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
`ghcr.io/obsei/obsei`.

Until 1.0.0, releases are PyPI pre-releases (`1.0.0a1`, `1.0.0rc1`, ...), which `pip install obsei`
ignores unless the requirement names one (`obsei>=1.0.0rc1`). In `release-please-config.json`:

- next releases bump the pre-release number automatically (`1.0.0-rc.2`, ...); nothing to change;
- to start betas or release candidates, set `release-as` to `1.0.0-beta.1` or `1.0.0-rc.1` and
  `prerelease-type` to `beta` or `rc`, then remove `release-as` after that release;
- for the launch, set `release-as` to `1.0.0` and remove `versioning`, `prerelease` and
  `prerelease-type`, then remove `release-as` after the release.

Release-please also bumps exact versions on lines marked `x-release-please-version` (or between
`x-release-please-start-version` and `x-release-please-end`) in the files listed under
`extra-files`: the image tags in both READMEs, the docs quickstart and the blog post, and the
release link on the website. Install specifiers such as `>=1.0.0rc1` are minimums and need no
change: they already install the newest release. Prefer a minimum or a link to
[Releases](https://github.com/obsei/obsei/releases) over an exact version in new text.

## For maintainers: websites

obsei.com (`website/`, static, no build), docs.obsei.com (`docs/`, Astro Starlight, which also
serves the Studio demo at `/demo/`) and blog.obsei.com (`blog/`, Astro with MDX) are Cloudflare
Pages projects connected to this repository. Each deploys on push to `master` and gives every pull
request a preview URL.

| Setting | `obsei-docs` | `obsei-site` | `obsei-blog` |
| --- | --- | --- | --- |
| Root directory | `docs` | `website` | `blog` |
| Build command | `npm ci && npm run build` | `exit 0` | `npm ci && npm run build` |
| Output directory | `dist` | `.` | `dist` |
| Variables | `NODE_VERSION=22` | | `NODE_VERSION=22` |
| Custom domains | `docs.obsei.com` | `obsei.com`, `www.obsei.com` | `blog.obsei.com` |

Each site sets its security headers in `_headers` (`website/_headers`, `docs/public/_headers`,
`blog/public/_headers`). The website and blog ship no JavaScript, so their Content-Security-Policy
allows no scripts; JSON-LD blocks are data and are not affected.

Vector logos (full and mark, light and dark) are in `docs/public/brand/`, served at
https://docs.obsei.com/brand/obsei-logo.svg and similar. Brand colours come from the logo: teal `#238a91` (text `#1b7a80`) and blue `#1a6d9d`; on dark
backgrounds `#5cc6cc` and `#7fb4e0`. Regenerate the demo with `uv run obsei demo --out docs/public/demo`
(offline `hashing` embedder) and the Studio bundle with `cd studio && npm ci && npm run build`.
For a demo whose themes span languages, use the multilingual model:

```bash
uv run --extra embeddings obsei models download
uv run --extra embeddings obsei demo --embedder local --out docs/public/demo
```

The social images `website/og.png` and `docs/public/og.png` are rendered from the `og.svg` next to
them (1200x630); the blog renders its own at build time.

### Writing a blog post

We aim for one post a week: practical guides, analyses of how themes shift across companies and
domains, and experiments with new models. Preview with `cd blog && npm ci && npm run dev`.

1. Add `blog/src/content/posts/<slug>.mdx`. The file name is the URL: `blog.obsei.com/<slug>/`.
2. Start with frontmatter:

   ```yaml
   ---
   title: "Short, specific title"          # up to 100 characters
   description: "One or two sentences."   # meta description, cards and RSS; up to 300 characters
   pubDate: 2026-10-12
   updatedDate: 2026-10-20                # optional, for meaningful edits
   author: Lalit Pagaria                  # authors with a profile link live in blog/src/consts.ts
   tags: [guide, privacy]                 # lowercase, hyphenated; each gets a /tags/<tag>/ page
   cover: ./<slug>/cover.svg              # 1200x630, SVG preferred (PNG/JPEG/WebP also work)
   coverAlt: "What the cover shows"
   draft: false                           # true hides the post from production builds
   ---
   ```

3. Put the cover and any images in `blog/src/content/posts/<slug>/`. Copy an existing `cover.svg`
   and change the text: the build renders it to `/og/<slug>.png` for social cards with the Inter
   subset in `blog/og-fonts/`, so keep cover text to Latin characters.
4. Figures are Astro components in `blog/src/components/figures/`. Import them in the MDX with a
   relative path (`import Timeline from "../../components/figures/Timeline.astro";`) and use them
   as `<Timeline />`. Use HTML and CSS or inline SVG with the brand tokens from
   `blog/src/styles/global.css`, no inline `style` attributes and no scripts (the CSP blocks
   both), wrap the drawing in `role="img"` with a full `aria-label`, add a `<figcaption>`, and
   check it at 390px wide in light and dark.
5. Code blocks are highlighted with Prism at build time (classes only, CSP-safe).
6. Run `npm run build` and open a pull request; Cloudflare posts a preview link.
