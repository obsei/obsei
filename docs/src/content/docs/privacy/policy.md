---
title: Privacy policy
description: What data obsei, its plugins and its websites collect.
---

**The obsei software collects nothing.** The `obsei` package, its MCP server and the plugins and
extensions for AI tools (Claude, Codex, Copilot, VS Code, Cursor, Gemini and others) send no
telemetry, usage data or crash reports, and have no account or sign-up. They run on your
infrastructure and store data only where your `obsei.yaml` says. The maintainers never receive
your data.

Network requests go only to the sources, models and sinks you configure, under the egress policy
you set (see [Privacy controls](/privacy/overview/)). Installing obsei downloads it from PyPI, or
the image from GitHub Container Registry; those services apply their own privacy policies.

**AI tools.** When an AI tool calls the obsei MCP server, the tool results (redacted feedback
text, labels and record ids, never author pseudonyms) go to that tool and the model provider it
uses, under their terms. You choose the tool and its provider.

**Websites.** obsei.com, docs.obsei.com and blog.obsei.com are static sites hosted on Cloudflare
Pages. They set no cookies and include no analytics or tracking scripts. Cloudflare processes
request data such as IP addresses to deliver and protect the sites, under the
[Cloudflare privacy policy](https://www.cloudflare.com/privacypolicy/).

**Contact.** Questions go to [GitHub Discussions](https://github.com/obsei/obsei/discussions);
security issues are handled as described in
[SECURITY.md](https://github.com/obsei/obsei/blob/master/SECURITY.md).
