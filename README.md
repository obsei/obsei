<p align="center">
  <img src="https://raw.githubusercontent.com/obsei/obsei/master/images/logos/obsei_200x200.png" alt="obsei" width="120">
</p>

<h1 align="center">obsei</h1>

<p align="center"><b>Voice of Customer without violating privacy.</b><br>
Open-source, self-hosted, AI-native feedback analytics. Bring your own sources, models and agents.</p>

<p align="center">
  <a href="https://github.com/obsei/obsei/actions/workflows/ci.yml"><img src="https://github.com/obsei/obsei/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/obsei/"><img src="https://img.shields.io/pypi/v/obsei" alt="PyPI"></a>
  <a href="https://github.com/obsei/obsei/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License"></a>
</p>

---

> [!IMPORTANT]
> **obsei is being rebuilt.** The next stable release, **1.0.0**, is a new codebase and is not
> compatible with 0.0.x. Pre-releases (`1.0.0a1`, ...) are opt-in with `pip install --pre`.
> The last 0.0.x release (0.0.15) stays available on PyPI, and its code remains in the
> git history. See the [roadmap](ROADMAP.md).

## What obsei is becoming

Teams want to understand what customers say in reviews, tickets, calls and surveys, but often can't
send that text to another SaaS or a public LLM. obsei runs entirely inside your own infrastructure:

- **Private by design.** PII is redacted and authors are pseudonymised at ingest. Use local models,
  models in your own cloud tenancy, or (opt-in) public APIs. No telemetry. Air-gapped mode.
- **Bring your own.** Your sources (native connectors plus generic REST, SQL, MCP-client, webhook and
  file drops), your LLM (Ollama, vLLM, Azure OpenAI, Bedrock, Vertex, OpenAI, Anthropic, Gemini) and
  your agents.
- **AI-native.** An MCP server first, so Claude, ChatGPT, Cursor and your own agents can query
  feedback with cited, privacy-filtered evidence.
- **One schema, kept over time.** Many sources mapped into one Feedback Record, deduplicated and
  stored in a single DuckDB file you own.

obsei provides controls that *support* compliance with laws such as GDPR and India's DPDP Act. It
does not make compliance claims; the deploying organisation remains the data controller.

## Try the preview

The 0.1 development line is under active construction and not yet on PyPI (installing `obsei` from
PyPI today still gives the old 0.0.15). It currently ships the Feedback Record schema, the plugin
registry, pseudonymisation and the CLI. Run it from source:

```bash
git clone https://github.com/obsei/obsei && cd obsei
uv sync
uv run obsei doctor
uv run obsei schema    # Feedback Record JSON Schema
```

Pre-releases of 1.0 will be published as they land: `uvx --prerelease allow obsei doctor`, or
`pip install --pre obsei`. The first stable public release is 1.0.0.

## Roadmap at a glance

| Phase | Scope |
| --- | --- |
| 0.1 Private core | Record, encrypted DuckDB, redaction, pseudonyms, retention and erasure, no-egress mode, BYO LLM, first sources and sinks |
| 0.2 MCP and Claude plugin | MCP read tools, Claude plugin, GitHub Action recipes, docs site |
| 0.3 Enterprise BYO | SQL, MCP-client and file-drop sources; Zendesk, Intercom, Freshdesk; Jira, Linear and warehouse sinks |
| 0.4 Themes and Studio | Stable themes, dedupe, knowledge graph preview, read-only web UI, static demo |

Details in [ROADMAP.md](ROADMAP.md).

## Contributing

Questions and ideas go to [Discussions](https://github.com/obsei/obsei/discussions). See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, conventions and the DCO sign-off.

## License

[Apache-2.0](LICENSE)
