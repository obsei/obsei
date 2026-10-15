---
title: Use obsei from your AI tool
description: Install the obsei MCP server and voice-of-customer skill in Claude, Codex, Copilot, VS Code, Cursor, Gemini and other AI tools.
sidebar:
  label: AI tools
  order: 6.2
---

Every tool runs the same local MCP server over stdio:

```bash
uvx --from "obsei>=1.0" obsei mcp
```

`uvx` comes with [uv](https://docs.astral.sh/uv/). The `>=1.0` floor stops uvx from reusing an
older cached obsei, such as a release candidate. The first start downloads obsei, so give the
server a startup timeout of about 60 seconds where the tool has one.

The server reads `obsei.yaml` in the working directory, or the file named by `OBSEI_CONFIG`. Set
`OBSEI_DB` for a database somewhere else and `OBSEI_DB_KEY` when it is encrypted. It opens the
store read-only, except to queue agent proposals for approval ([MCP](/guides/mcp/)). The plugins for Claude Code, Codex, Copilot, VS Code, Cursor and Gemini also add
the `voice-of-customer` skill: one [`SKILL.md`](https://github.com/obsei/obsei/blob/master/integrations/claude/obsei/skills/voice-of-customer/SKILL.md)
shared by all of them.

[![Install in Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/install-mcp?name=obsei&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyItLWZyb20iLCJvYnNlaT49MS4wIiwib2JzZWkiLCJtY3AiXX0%3D)
[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_obsei-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=obsei&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22--from%22%2C%22obsei%3E%3D1.0%22%2C%22obsei%22%2C%22mcp%22%5D%7D)

| Tool | Install | Notes |
| --- | --- | --- |
| Claude Code | `/plugin install obsei --marketplace obsei/obsei` | MCP server and skill. Older versions: `/plugin marketplace add obsei/obsei`, then `/plugin install obsei@obsei` |
| Codex | `codex plugin marketplace add obsei/obsei`, then `codex plugin add obsei@obsei` | MCP server and skill. MCP only: [below](#codex) |
| GitHub Copilot CLI | `copilot plugin install obsei/obsei:integrations/claude/obsei` | MCP server and skill |
| VS Code (Copilot agent mode) | button above, or `code --add-mcp '{"name":"obsei","command":"uvx","args":["--from","obsei>=1.0","obsei","mcp"]}'` | MCP server. For the skill too, run **Chat: Install Plugin From Source** with `https://github.com/obsei/obsei` |
| Cursor | button above | MCP server. The plugin with the skill is awaiting Cursor Marketplace review |
| Gemini CLI | `gemini extensions install https://github.com/obsei/obsei` | Asks for `OBSEI_CONFIG`, `OBSEI_DB` and `OBSEI_DB_KEY`; Gemini passes only these to the server |
| Antigravity | `agy plugin import gemini` | Imports the Gemini CLI extension above |
| Claude Desktop | [JSON config](#json-config) in `claude_desktop_config.json` | |
| Cline | ask Cline to install `https://github.com/obsei/obsei` | It follows [`llms-install.md`](https://github.com/obsei/obsei/blob/master/llms-install.md) |
| Devin Desktop (formerly Windsurf) | [JSON config](#json-config) in `~/.config/devin/mcp_config.json` | |
| Zed | [Zed settings](#zed) | |
| JetBrains AI Assistant | **Settings > Tools > AI Assistant > Model Context Protocol (MCP)**, **Add**, paste the [JSON config](#json-config) | |
| Junie | [JSON config](#json-config) in `.junie/mcp/mcp.json` | |
| Kiro | [JSON config](#json-config) in `.kiro/settings/mcp.json` | |
| Goose | [Install in Goose](goose://extension?cmd=uvx&arg=--from&arg=obsei%3E%3D1.0&arg=obsei&arg=mcp&id=obsei&name=obsei&description=Privacy-first%20Voice%20of%20Customer) | Or `goose configure`, **Add Extension**, **Command-line Extension** with the command above |
| ChatGPT | [Secure MCP Tunnel](#chatgpt) | Private use only |

## JSON config

Most tools take the same `mcpServers` block:

```json
{
  "mcpServers": {
    "obsei": {
      "command": "uvx",
      "args": ["--from", "obsei>=1.0", "obsei", "mcp"],
      "env": { "OBSEI_CONFIG": "/path/to/obsei.yaml", "OBSEI_DB_KEY": "..." }
    }
  }
}
```

VS Code's `.vscode/mcp.json` uses `servers` in place of `mcpServers`.

## Codex

```bash
codex mcp add obsei --env OBSEI_CONFIG=/path/to/obsei.yaml -- uvx --from "obsei>=1.0" obsei mcp
```

Then raise the startup timeout in `~/.codex/config.toml`, and forward the database key from your
environment rather than writing it to the file:

```toml
[mcp_servers.obsei]
command = "uvx"
args = ["--from", "obsei>=1.0", "obsei", "mcp"]
env = { OBSEI_CONFIG = "/path/to/obsei.yaml" }
env_vars = ["OBSEI_DB_KEY"]
startup_timeout_sec = 60
```

## Zed

In `settings.json`:

```json
{
  "context_servers": {
    "obsei": {
      "command": "uvx",
      "args": ["--from", "obsei>=1.0", "obsei", "mcp"],
      "env": { "OBSEI_CONFIG": "/path/to/obsei.yaml" }
    }
  }
}
```

## ChatGPT

ChatGPT does not run local stdio servers. Its connectors need a public HTTPS MCP server with
OAuth 2.1 (or no authentication) and reject static bearer tokens, so `obsei serve` with
`OBSEI_API_TOKEN` cannot be added. obsei does not provide an OAuth server yet.

For private use in your own workspace, OpenAI's
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) wraps
`obsei mcp` with an outbound-only connection. Create a tunnel in
[Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels), download
`tunnel-client`, then:

```bash
export CONTROL_PLANE_API_KEY="sk-..."
tunnel-client init --sample sample_mcp_stdio_local --profile obsei \
  --tunnel-id tunnel_... --mcp-command 'uvx --from "obsei>=1.0" obsei mcp'
tunnel-client run --profile obsei
```

In ChatGPT, open **Plugins**, select **+**, **Add custom MCP server**, choose **Tunnel** under
**Connection** and pick the tunnel. Keep `tunnel-client run` running while you use it. Records
leave your machine for OpenAI as each tool returns them, already redacted.

## Remote MCP

For tools that connect over HTTP with a header, `obsei serve` serves the same tools at `/mcp`;
see [MCP and agents](/guides/mcp/#remote-mcp).
