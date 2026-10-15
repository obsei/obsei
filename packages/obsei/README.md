<p align="center">
  <img src="https://raw.githubusercontent.com/obsei/obsei/master/docs/public/logo.png" alt="obsei" width="110">
</p>

# obsei

**Voice of Customer without violating privacy.** The self-hosted, open source alternative to Enterpret and Unwrap that strips PII before any LLM sees it.
Collect feedback from every channel and language, redact personal data before it is stored, find
stable themes, and let your AI agents answer questions with cited evidence.

> 1.0 is in pre-release and is not compatible with 0.0.x. Install it with the `>=1.0.0rc1`
> specifier; a plain `pip install obsei` still gives 0.0.15.

```bash
uvx --from "obsei[recommended]>=1.0.0rc1" obsei init   # or: pip install "obsei[recommended]>=1.0.0rc1"
obsei try                                        # redacted, labelled preview; nothing stored
obsei add appstore                               # add sources and sinks without editing YAML
obsei add slack
obsei check
obsei run
```

`obsei init` writes the database key and pseudonym salt to `.obsei/secrets.env` (owner-only,
git-ignored), which every command loads; on servers and in CI, set `OBSEI_DB_KEY` and
`OBSEI_PSEUDONYM_SALT` or mount the file.

Optional extras: `recommended` (`local` and `embeddings`), `local` (in-process classifier), `sql`, `google`, `apple`, `names` (person-name
redaction), `embeddings` (multilingual themes).

Use it from your AI tool: `/plugin install obsei --marketplace obsei/obsei` in Claude Code,
`gemini extensions install https://github.com/obsei/obsei`, or `uvx --from "obsei>=1.0.0rc1" obsei mcp`
in any MCP client. Codex, Copilot, VS Code, Cursor and others: https://docs.obsei.com/guides/ai-tools/

<!-- mcp-name: io.github.obsei/obsei -->

- Docs: https://docs.obsei.com
- Live demo: https://docs.obsei.com/demo/
- Source: https://github.com/obsei/obsei
- Container: `ghcr.io/obsei/obsei:1.0.0` <!-- x-release-please-version -->
