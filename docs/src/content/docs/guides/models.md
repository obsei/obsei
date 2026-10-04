---
title: Models
description: Bring your own LLM, with egress control.
sidebar:
  order: 3
---

obsei talks to any OpenAI-compatible chat endpoint with structured JSON output. Endpoints are named
under `llms` in `obsei.yaml`; plugins refer to them by name (`default` unless set):

```yaml
llms:
  default:
    base_url: http://localhost:11434/v1
    model: qwen3:8b
    max_requests: 500        # optional; also api_key_env, api_key_header, timeout
```

| Where | `base_url` |
| --- | --- |
| Ollama | `http://localhost:11434/v1` |
| vLLM, llama.cpp, LM Studio | `http://your-host:8000/v1` |
| Azure OpenAI | `https://<resource>.openai.azure.com/openai/v1` with `api_key_header: api-key` |
| OpenAI, Mistral, Groq, OpenRouter | the provider's `/v1` URL |
| AWS Bedrock, Google Vertex AI, Anthropic | a [LiteLLM proxy](https://docs.litellm.ai) in your network |

## Egress modes

| Mode | Model and sink endpoints allowed |
| --- | --- |
| `air_gapped` (default) | localhost, private and link-local IPs, `.localhost`, `.internal`, `.local`, single-label hosts |
| `private` | the above plus `OBSEI_EGRESS_ALLOW` (comma-separated hosts and their subdomains) |
| `hybrid` | any host |

Set the mode with `OBSEI_EGRESS_MODE`, or with `egress: {mode: private, allowed_hosts: [...]}` in
`obsei.yaml`, which takes precedence over the environment. A public endpoint is refused before any
request is made.

## Cost and quality

`max_requests` caps requests per endpoint client, so a run cannot exceed it. With `fallback_llm` on the `classify` enricher, the `llm` model labels everything and
only results below `threshold` confidence (default 0.7) go to the larger model.

Feedback is sent to the model as JSON data, and the system prompt tells the model never to follow
instructions inside it.
