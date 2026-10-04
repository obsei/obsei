---
title: Models
description: Bring your own LLM, with egress control.
sidebar:
  order: 3
---

obsei talks to any OpenAI-compatible chat endpoint with structured JSON output, and to
[decision models](#decision-models) for labels, routing and moderation. Endpoints are named under
`llms` in `obsei.yaml`; plugins refer to them by name (`default` unless set):

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

## Decision models

A decision model does not write text: you give it the feedback and a few questions with their
options, and it scores every option in one forward pass. The answer is always one of your options,
with a probability for each, so there is nothing to parse and nothing to retry. Small decision
models run fast on a CPU: Julia-1 answered four questions about a ticket in about 140 ms in our
tests.

| Use a decision model for | Use a chat model for |
| --- | --- |
| Labels from a fixed list: sentiment, intent, product area | Theme labels (short phrases you have not listed) |
| Routing: which team, which queue, which sink | Ask answers and summaries |
| Moderation: spam, bots, off-topic (the `filter` enricher) | Free-text `classify` fields |
| Ordered scores: urgency, severity, effort | Feedback no option fits well |
| Judging: is an Ask answer supported by its sources (`ask_judge`) | |

obsei speaks the decision API served by llama.cpp, the OpenJev helper and hosted services. Set
`url`, or `url_env` (an environment variable holding it), to the full endpoint URL your server
documents ([Serving](#serving)); obsei posts to it as is:

```yaml
llms:
  julia:
    api: decision                   # default: openai (chat, with base_url)
    url_env: OBSEI_DECISION_URL     # or url: <the endpoint URL>
    model: Julia-1                  # optional; picks a model on a llama.cpp router
    timeout: 30                     # also api_key_env, api_key_header, max_requests
  ollama:
    base_url: http://localhost:11434/v1
    model: qwen3:8b
```

### Models

| Model | Size | Languages | Images | Get it |
| --- | --- | --- | --- | --- |
| **Julia-1** (recommended default) | 144M (mmBERT-small) | 50+ | no | `ggml-org/Julia-1-GGUF` (Q8_0, 168 MB) |
| Laya | 421M (ModernBERT-large) | English | no | the model's page |
| Kev-4B | 4B | English | no | `ggml-org/Kev-4B-GGUF` |
| lev | 4B | English | no | the model's page |
| Clef-Flash | 9B (Qwen3.5-9B) | benchmarked in English | no | `ggml-org/Clef-Flash-GGUF` (Q4_K_M 6.5 GB, Q8_0 9.7 GB) |
| Clef | 27B (Qwen3.8-27B) | benchmarked in English | Transformers only | `ggml-org/Clef-GGUF` (Q4_K_M 19.2 GB, Q8_0 28.7 GB); Cloudflare Workers AI |
| OpenJev | 27B | en, de, fr, hi, zh, ja | vLLM (16-bit, FP8) | `openjev/openjev` (also `-FP8`, `-GGUF`, `-MLX`) |

Check each model's page for its licence and terms.

Start with **Julia-1**: it is multilingual, small enough for any CPU and labels tickets in dozens
of languages. Use **Kev-4B** or **lev** for English-only feedback, and **Clef-Flash** when you
have a GPU and want higher accuracy (its published benchmarks are English).

### Serving

```bash
llama serve -hf ggml-org/Julia-1-GGUF
llama serve -hf ggml-org/Clef-Flash-GGUF       # a GPU helps
```

llama.cpp serves decisions at `http://127.0.0.1:8080/v1/systemone`; set `OBSEI_DECISION_URL` to it.

OpenJev runs on vLLM behind its helper (`openjev/helper/shim.py`), which serves the same API on
port 3000 (the same path on `http://127.0.0.1:3000`). OpenJev reads prompts up to 16,384 tokens.

Clef answers all questions of a request together in one prompt (the others answer each question
independently). A llama.cpp server running Clef serves only the decision endpoint, no chat, so point
`fallback_llm`, `ask_llm` and `themes.labeler` at a different endpoint.

Clef is also hosted on Cloudflare Workers AI. Give the run URL as `url`; obsei unwraps Cloudflare's
response envelope:

```yaml
egress:
  mode: private
  allowed_hosts: [api.cloudflare.com]
llms:
  clef:
    api: decision
    url: https://api.cloudflare.com/client/v4/accounts/<account-id>/ai/run/@cf/cloudflare/clef
    model: clef
    api_key_env: CLOUDFLARE_API_TOKEN   # sent as a Bearer token
```

The hosted option sends redacted feedback text to Cloudflare, which is why it needs `private`
egress with `api.cloudflare.com` allow-listed. A self-hosted GGUF keeps everything on your
machines and works in `air_gapped` mode.

### Describe the options

Bare labels route worse than described ones. `sentiments`, `intents` and `choices` accept a list
or a mapping of option to a one-line description; obsei ships descriptions for the built-in
sentiments and intents.

```yaml
- type: classify
  config:
    llm: julia
    intents:
      bug: something is broken, errors, crashes or does not work as documented
      billing: charges, invoices, refunds, payment methods or prices
      churn_risk: threatens to cancel, downgrade or move to a competitor
      other: none of the above
    fields:
      area:                                   # choice
        description: Which part of the product is this about?
        choices: {mobile: iOS or Android app, web: the browser app, api: the public API}
      urgency:                                # score: levels lowest first (2 to 10)
        description: How soon does the customer need this resolved?
        levels: [can wait, this week, today, right now]
      asks_for_refund:                        # yes/no
        type: yesno
        description: Does the customer ask for money back?
        yes_means: asks for a refund, a chargeback or money back
        no_means: does not ask for money back
```

Each field is one question, and all questions for a record go in one request. A `yesno` field with
`yes_means` and `no_means` is asked as a choice between two described options; small models answer
that far more reliably than a bare yes/no question, so describe both sides. Free-text fields need a
chat model. Language is taken from the record, as before.

The stored `classify` value keeps the usual `sentiment`, `intent`, `language`, `confidence` and
`fields` (yes/no fields are `true` or `false`), plus `probabilities` per question, `scores` (the
expected level of each score field, e.g. 2.28 between "today" and "right now"), `confidences`, and
`review` with the `uncertain` questions. Sinks filter on nested and yes/no fields:

```yaml
when: {classify.intent: [bug], classify.fields.urgency: [today, right now]}
when: {classify.fields.asks_for_refund: ["true"]}
when: {classify.review: ["true"]}
```

### Choose a cutoff per model

Each answer has a confidence: for a choice, 0 when every option is equally likely; for a yes/no,
the larger of p and 1 - p. Probabilities are scaled with temperatures stored in the model file and
are not guaranteed to be calibrated for your data, so check a cutoff on a sample of your own
feedback (`obsei try --enrich` prints every probability) and set it per model:

```yaml
- type: classify
  config:
    llm: julia
    fallback_llm: ollama         # a chat model on another endpoint
    threshold: 0.6               # cutoff for every answer
    min_confidence:              # per-question overrides
      urgency: 0.3               # score confidence runs lower than choice confidence
```

A record with any answer below its cutoff goes to `fallback_llm`, which labels the whole record.
Without a fallback, or when the fallback fails, the decision model's labels are kept with
`review: true`.

### Egress and air-gapped use

A decision endpoint follows the same egress policy as chat endpoints: the URL is checked before any
request, and every request is checked again on the wire. Julia-1 and the other GGUF models run
under llama.cpp inside your network, so a decision pipeline works fully `air_gapped`; only hosted
APIs (Jev, Workers AI) need `private` mode with their host allow-listed.
