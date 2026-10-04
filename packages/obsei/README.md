<p align="center">
  <img src="https://raw.githubusercontent.com/obsei/obsei/master/docs/public/logo.png" alt="obsei" width="110">
</p>

# obsei

**Voice of Customer without violating privacy.** Open-source, self-hosted, AI-native feedback
analytics: collect feedback from every channel and language, redact personal data before it is
stored, find stable themes, and let your AI agents answer questions with cited evidence.

> 1.0 is in pre-release and is not compatible with 0.0.x. Install it with the `>=1.0.0rc1`
> specifier; a plain `pip install obsei` still gives 0.0.15.

```bash
pip install "obsei[mcp]>=1.0.0rc1"     # or: uv tool install "obsei[mcp]>=1.0.0rc1"
obsei init
export OBSEI_DB_KEY="$(openssl rand -hex 24)" OBSEI_PSEUDONYM_SALT="$(openssl rand -hex 24)"
obsei try && obsei run
```

Optional extras: `mcp` (MCP server, `obsei serve`), `sql`, `google`, `apple`, `names` (person-name
redaction), `embeddings` (multilingual themes).

- Docs: https://docs.obsei.com
- Live demo: https://docs.obsei.com/demo/
- Source: https://github.com/obsei/obsei
- Container: `ghcr.io/obsei/obsei:1.0.0-rc.1` <!-- x-release-please-version -->
