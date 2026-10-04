# obsei.com

A static landing page with no build step. The docs and the Studio demo live at docs.obsei.com
(built from [`../docs`](../docs)). Both are hosted on Cloudflare Pages.

## Cloudflare setup (once)

Do these in order so the site never goes dark. The domain's DNS must be on Cloudflare (it is
registered there).

1. **Docs project.** Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git →
   `obsei/obsei`:
   - Project name: `obsei-docs`
   - Production branch: `master`
   - Framework preset: Astro
   - Root directory: `docs`
   - Build command: `npm ci && npm run build`
   - Build output directory: `dist`
   - Environment variable: `NODE_VERSION` = `22`

   Then open the project → Custom domains → add `docs.obsei.com` (Cloudflare creates the DNS
   record).
2. **Website project.** Create a second Pages project from the same repository:
   - Project name: `obsei-site`
   - Production branch: `master`
   - Framework preset: None
   - Root directory: `website`
   - Build command: leave empty
   - Build output directory: `.` (the root directory itself)

   Then Custom domains → add `obsei.com` and `www.obsei.com`. If a CNAME record for
   `www.obsei.com` still points at `obsei.github.io`, Cloudflare offers to replace it; accept.
3. **One host.** Rules → Redirect Rules → create a rule: when hostname equals `www.obsei.com`,
   redirect to `https://obsei.com${uri}` (dynamic, 301, keep query string).
4. **Turn off GitHub Pages.** GitHub → obsei/obsei → Settings → Pages → Source: None. Merging the
   PR that adds this folder also removes `CNAME` and `_config.yml`.
5. **Check:** https://obsei.com, https://www.obsei.com (redirects), https://obsei.com/docs
   (redirects to docs), https://docs.obsei.com and https://docs.obsei.com/demo/.

Each pull request that changes `docs/` or `website/` gets a preview URL from Cloudflare Pages;
leave "Preview deployments" on. To build only when relevant files change, set Build watch paths:
`docs/**` for `obsei-docs` and `website/**` for `obsei-site`.

## Files

- `_redirects`: `/docs/*` and `/demo` to docs.obsei.com.
- `_headers`: security headers; the page runs no JavaScript.
