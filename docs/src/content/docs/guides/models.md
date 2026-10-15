---
title: Models
description: A local classifier by default; decision models or any LLM when you choose, with egress control.
sidebar:
  order: 4
---

Models are named under `llms` in `obsei.yaml`; plugins refer to them by name (`default` unless
set). Each entry has an `api`:

| `api` | What runs | Use it for |
| --- | --- | --- |
| `local` (the `obsei init` default) | zero-shot classifiers inside obsei, on the CPU | `classify` labels, routing fields and scores, with nothing to serve |
| `decision` | a [decision model](#decision-models) on llama.cpp or a hosted API | the same labels from a model server; `filter` and `ask_judge` |
| `openai` (default when `api` is unset) | any OpenAI-compatible chat endpoint | `ask`, theme labels, free-text fields, or `classify` with a chat model |

## Local classifier

The default classifier runs in process, so feedback never leaves the machine and there is no server
to start:

```bash
pip install 'obsei[local]'           # PyTorch, Transformers and GLiNER2
obsei models download                # once, with network; --dir or OBSEI_MODELS_DIR picks the cache
```

```yaml
llms:
  default:
    api: local
    model: MoritzLaurer/bge-m3-zeroshot-v2.0       # the default; any zero-shot NLI model works
    models: {sentiment: fastino/gliner2-multi-v1}   # optional: another model for one question
```

Each question is answered on its own. Every option, written as `key: description`, is scored as the
hypothesis "This customer message is …" against the message text, which gives a probability per
option. The answer is the most likely option, and its probability is the confidence. A score field
scores each level with its question, so `scores` and `levels` work as with decision models. A
`yesno` field needs `yes_means` and `no_means` and is asked as a two-option choice. Free-text fields
need a chat model. Models with `gliner2` in their name run with
[GLiNER2](https://github.com/fastino-ai/GLiNER2) instead of NLI.

`bge-m3-zeroshot-v2.0` (MIT, 568M parameters, about 2.2 GB) labelled about 0.7 records a second on
one CPU with three questions per record. Each extra field costs about as much as one of those
questions. `gliner2-multi-v1` (Apache-2.0) is about five times faster and slightly better at sentiment,
but it routed no Japanese message to the right team, so the example above uses it for sentiment
only. `obsei models download --classifier <model>` (repeatable) fetches other models.

In `air_gapped` mode (the default) obsei never downloads a model: it loads them from
`OBSEI_MODELS_DIR`, or from a local directory given as `model`. Run `obsei models download` once
on a machine with network and copy the directory over if needed.

### Benchmark

We labelled the 136 records of the [demo](/demo/) (8 issues in 11 languages) with three questions:
intent, sentiment and team. Each model got the demo's option descriptions, and the expected answer
for each record comes from the demo issue it was written for.

| Model | How it answers | Intent | Sentiment | Team | Mean | Worst ECE | Review at 0.7 | Records/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Julia-1 (144M) | decision API, llama.cpp | .71 | .75 | .62 | .69 | .33 | 23% | not timed |
| mDeBERTa-v3-base xnli | zero-shot NLI | .46 | .65 | .76 | .62 | .31 | 96% | 0.64 |
| **bge-m3-zeroshot-v2.0** (default) | zero-shot NLI | .82 | .90 | .91 | .88 | .26 | 80% | 0.69 |
| gliner2-multi-v1 | GLiNER2 | .77 | .92 | .75 | .81 | .19 | 36% | 3.25 |
| gliner2-base-v1 | GLiNER2, English only | .76 | .61 | .65 | .67 | .38 | 21% | 3.52 |
| Qwen3-0.6B | option-letter probabilities | .74 | .75 | .86 | .78 | .21 | 43% | 0.18 |
| gliner2-multi for sentiment, bge-m3 for the rest | `models: {sentiment: …}` | .82 | .95 | .91 | .90 | | 71% | 0.56 |

Intent, sentiment and team are accuracy. ECE is the expected calibration error of the confidence,
for the worst of the three questions (0 means a confidence of 0.8 is right 80% of the time). Review
at 0.7 is the share of records with at least one answer below 0.7. The mixed row was measured through obsei's
`api: local` classifier; the others with the benchmark script, calling each model the same way.

- bge-m3 was the most accurate, and right at least half the time in every language for every
  question. Its probabilities are spread out, so at the usual 0.7 cutoff it sends 80% of records to
  review; `obsei init` uses 0.4 for it, which sends 13% ([cutoffs](#choose-a-cutoff-per-question)).
- Julia-1 was the least accurate and the most overconfident: few answers fall below the cutoff, but
  many confident answers are wrong (team .62, ECE .33). Its numbers are from the labels committed
  with the demo.
- mDeBERTa and gliner2-base missed whole languages (0% in Japanese, Korean, Hindi or Arabic on some
  questions). Qwen3-0.6B was the best calibrated on team routing (ECE .05) but the slowest.

Caveats: the records are synthetic, about 12 per language, and expected answers come from the demo's
issue definitions, not from human review of each message. Timings are PyTorch on one CPU, one record
at a time. Qwen3 1.7B and 4B, larger decision models (Kev-4B, Clef-Flash) and GPUs were not tested.
Your options and your feedback differ, so [measure on a labelled sample of your
own](#measure-on-your-own-data) before a route acts on labels. `obsei eval --demo` reruns the
default's row: the gold set ships with obsei as `templates/demo-gold.csv`.

## Chat endpoints

obsei talks to any OpenAI-compatible chat endpoint with structured JSON output:

```yaml
llms:
  chat:
    base_url: http://localhost:11434/v1
    model: qwen3:8b
    max_requests: 500        # optional; also api_key_env, api_key_header, timeout
ask_llm: chat                # ask and the Slack bot use this entry (default: default)
```

| Where | `base_url` |
| --- | --- |
| Ollama | `http://localhost:11434/v1` |
| vLLM, llama.cpp, LM Studio | `http://your-host:8000/v1` |
| Azure OpenAI | `https://<resource>.openai.azure.com/openai/v1` with `api_key_header: api-key` |
| OpenAI, Mistral, Groq, OpenRouter | the provider's `/v1` URL |
| AWS Bedrock, Google Vertex AI, Anthropic | a [LiteLLM proxy](https://docs.litellm.ai) in your network |

To classify with a chat model instead, point `classify` at it (`llm: chat`). A cloud model needs its
own `llms` entry and must pass the [egress policy](#egress-modes): send feedback to a provider only
when you have consent to do so.

## Egress modes

| Mode | Model and sink endpoints allowed |
| --- | --- |
| `air_gapped` (default) | localhost, private and link-local IPs, `.localhost`, `.internal`, `.local`, single-label hosts |
| `private` | the above plus `OBSEI_EGRESS_ALLOW` (comma-separated hosts and their subdomains) |
| `hybrid` | any host |

Set the mode with `OBSEI_EGRESS_MODE`, or with `egress: {mode: private, allowed_hosts: [...]}` in
`obsei.yaml`, which takes precedence over the environment. A public endpoint is refused before any
request is made. Local classifiers make no requests at run time; in `air_gapped` mode they also
never download.

## Cost and quality

`max_requests` caps requests per endpoint client, so a run cannot exceed it. With `fallback_llm` on
the `classify` enricher, the `llm` model labels everything and records it is unsure about go to the
`fallback_llm` chat model ([cutoffs](#choose-a-cutoff-per-question)).

Feedback is sent to chat models as JSON data, and the system prompt tells the model never to follow
instructions inside it.

## Decision models

A decision model does not write text: you give it the feedback and a few questions with their
options, and it scores every option in one forward pass. The answer is always one of your options,
with a probability for each, so there is nothing to parse and nothing to retry. Small decision
models run fast on a CPU: Julia-1 answered four questions about a ticket in about 140 ms in our
tests. Local classifiers give answers of the same shape, so everything below about fields,
probabilities and cutoffs applies to `api: local` too.

| Use a decision or local model for | Use a chat model for |
| --- | --- |
| Labels from a fixed list: sentiment, intent, product area | Theme labels (short phrases you have not listed) |
| Routing: which team, which queue, which sink | Ask answers and summaries |
| Moderation: spam, bots, off-topic (the `filter` enricher, decision only) | Free-text `classify` fields |
| Ordered scores: urgency, severity, effort | Feedback no option fits well |
| Judging: is an Ask answer supported by its sources (`ask_judge`, decision only) | |

obsei speaks the decision API served by llama.cpp, the OpenJev helper and hosted services. Set
`url`, or `url_env` (an environment variable holding it), to the full endpoint URL your server
documents ([Serving](#serving)); obsei posts to it as is:

```yaml
llms:
  julia:
    api: decision
    url_env: OBSEI_DECISION_URL     # or url: <the endpoint URL>
    model: Julia-1                  # optional; picks a model on a llama.cpp router
    timeout: 30                     # also api_key_env, api_key_header, max_requests
```

### Models

| Model | Size | Languages | Images | Get it |
| --- | --- | --- | --- | --- |
| Julia-1 | 144M (mmBERT-small) | 50+ | no | `ggml-org/Julia-1-GGUF` (Q8_0, 168 MB) |
| Laya | 421M (ModernBERT-large) | English | no | the model's page |
| Kev-4B | 4B | English | no | `ggml-org/Kev-4B-GGUF` |
| lev | 4B | English | no | the model's page |
| Clef-Flash | 9B (Qwen3.5-9B) | benchmarked in English | no | `ggml-org/Clef-Flash-GGUF` (Q4_K_M 6.5 GB, Q8_0 9.7 GB) |
| Clef | 27B (Qwen3.8-27B) | benchmarked in English | Transformers only | `ggml-org/Clef-GGUF` (Q4_K_M 19.2 GB, Q8_0 28.7 GB); Cloudflare Workers AI |
| OpenJev | 27B | en, de, fr, hi, zh, ja | vLLM (16-bit, FP8) | `openjev/openjev` (also `-FP8`, `-GGUF`, `-MLX`) |

Check each model's page for its licence and terms.

Julia-1 is the smallest multilingual decision model and the fastest per record, but in the
[benchmark](#benchmark) it was less accurate than the local default. Use **Kev-4B** or **lev** for
English-only feedback, and **Clef-Flash** when you have a GPU (its published benchmarks are
English). A 4B or larger decision model is also what `ask_judge` needs.

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
    llm: default
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

Each field is one question; a decision model gets all questions for a record in one request. A
`yesno` field with `yes_means` and `no_means` is asked as a choice between two described options;
small models answer that far more reliably than a bare yes/no question, so describe both sides
(local models require it). Free-text fields need a chat model. Language is taken from the record.

The stored `classify` value keeps the usual `sentiment`, `intent`, `language`, `confidence` and
`fields` (yes/no fields are `true` or `false`), plus `probabilities` per question, `scores` (the
expected level of each score field, e.g. 2.28 between "today" and "right now"), `levels` of each
score field, `confidences`, and `review` with the `uncertain` questions. Sinks filter on nested and yes/no fields:

```yaml
when: {classify.intent: [bug], classify.fields.urgency: [today, right now]}
when: {classify.fields.asks_for_refund: ["true"]}
when: {classify.review: ["true"]}
```

Conditions can also test the stored numbers, e.g. `{classify.intent: {is: bug, min_confidence:
0.8}}` or `{classify.fields.urgency: {gte: today}}`, and ordered `route:` rules send each record to
one set of sinks. See [Routing](/guides/routing/).

### Choose a cutoff per question

Each answer has a confidence. For a local model it is the top probability. For a decision model
it is the server's confidence, which is 0 when every option is equally likely. For a yes/no it is
the larger of p and 1 - p. These probabilities are not calibrated for your data: in the
[benchmark](#benchmark) one model was overconfident and another underconfident on the same
question. Check cutoffs on a labelled sample of your own feedback
([`obsei eval`](#measure-on-your-own-data) suggests one per question) and set them per question:

```yaml
- type: classify
  config:
    llm: default
    fallback_llm: chat           # a chat model on another endpoint
    threshold: 0.6               # cutoff for every answer
    min_confidence:              # per-question overrides
      team: 0.45                 # options that overlap spread the probability
      urgency: 0.3               # score confidence runs lower than choice confidence
```

A record with any answer below its cutoff goes to `fallback_llm`, which labels the whole record.
Without a fallback, or when the fallback fails, the labels are kept with `review: true`.

The cutoff trades review load against accuracy. For the local default (bge-m3) on the 136 demo
records:

| Cutoff | Records marked for review | Accuracy of kept answers (intent / sentiment / team) |
| --- | --- | --- |
| 0.3 | 1% | .82 / .90 / .92 |
| 0.4 | 13% | .83 / .90 / .95 |
| 0.5 | 41% | .88 / .94 / .98 |
| 0.7 | 80% | .97 / .98 / 1.00 |

`obsei init` sets `threshold: 0.4` for the local classifier; the built-in default stays 0.7, which
suits decision models such as Julia-1. These numbers hold for this model and these options only:
cutoffs depend on the model, so tune them per question on labelled feedback of your own:
`obsei eval` suggests them ([Measure on your own data](#measure-on-your-own-data)).

### Known limits

Small models make mistakes, so measure them on your own feedback before a route acts on their
labels.

- The [demo](/demo/) shows labels from Julia-1 (144M parameters, on a CPU) as they came out of the
  model. At the demo's cutoffs it marks 67 of 136 records (49%) for review, and some labels are
  wrong: 13 of 29 login complaints are routed to the `design` team.
- Start with a `review` route and a high `min_confidence`, read a sample of what goes to review,
  then lower the cutoffs where the model is reliably right.
- Clef-Flash currently aborts in the CPU build of llama.cpp (a GPU build or Cloudflare Workers AI
  may work), so it is not in the benchmark.

### Egress and air-gapped use

A decision endpoint follows the same egress policy as chat endpoints: the URL is checked before any
request, and every request is checked again on the wire. Julia-1 and the other GGUF models run
under llama.cpp inside your network, so a decision pipeline works fully `air_gapped`; only hosted
APIs (Jev, Workers AI) need `private` mode with their host allow-listed.

## Measure on your own data

Label a few hundred messages of your own feedback in a CSV: a `text` column, an optional `lang`
column, and one column per question, named as in `min_confidence`: `sentiment`, `intent`, or the
field name (`team`, `urgency`; yes/no fields take `true` or `false`). Answers must be options of
your `classify` config; empty cells are not scored.

```csv
text,lang,intent,sentiment,team
I can't log in since the update,en,bug,negative,engineering
Fui cobrado duas vezes este mês,pt,complaint,negative,payments
```

`obsei eval gold.csv` redacts each row as at ingest, runs the `classify` enricher of the first
pipeline that has one (`-p` picks another) and compares its answers with yours. Nothing is stored
or delivered; a model endpoint sees the redacted text as in a run. On the demo gold set with the local default (`obsei eval --demo`, about 3.5 minutes
on a laptop CPU):

```text
136 records, model MoritzLaurer/bge-m3-zeroshot-v2.0, 13% marked for review

question        n  accuracy  macro F1   ECE  Brier  cutoff  review  kept  suggest  review  worst language
sentiment     136      0.90      0.87  0.06   0.07    0.40      0%  0.90     0.44      1%  ko 0.50
intent        136      0.82      0.81  0.13   0.11    0.40      1%  0.83     0.51     12%  es 0.60
team          136      0.91      0.92  0.26   0.15    0.40     13%  0.95     0.00      0%  de 0.75

most common mistakes (expected -> answered):
sentiment   negative -> neutral (12), negative -> positive (2)
intent      praise -> bug (12), bug -> complaint (6), feature_request -> bug (6)
team        payments -> engineering (6), design -> engineering (3), engineering -> logistics (2)
```

- **cutoff, review, kept:** the configured cutoff of each question, the share of answers below it,
  and the accuracy of the answers at or above it.
- **suggest:** the lowest cutoff whose kept answers are right at least 90% of the time
  (`--target-precision`), and the share of answers it sends to review. Set it under
  `min_confidence`; `-` means no cutoff reaches the target.
- **ECE and Brier** measure how well the confidence matches how often answers are right (0 is
  perfect). The top line counts records with any answer below its cutoff.

`--json` prints the full report. `obsei eval` exits non-zero only on errors, or with
`--min-accuracy 0.8` when a question scores lower, so it can gate a model or config change in CI.
The demo gold set ships with obsei as `templates/demo-gold.csv`; its expected answers come from
the demo issue each record was written for.

### Correct labels

Fix wrong answers with a CSV of record ids (from Studio, MCP or `obsei export`) and a column per
question:

```bash
obsei correct labels.csv      # id,intent,team
```

A correction replaces the model's answer inside the record's `classify` labels, with confidence 1,
removes it from `uncertain` (so `review` clears once every uncertain answer is corrected), and lists
the question under `corrected`. Routes, MCP tools and Studio read corrected labels like any other;
records already delivered are not sent again. Each run is recorded in `obsei audit`.

`obsei eval --from-store` uses every corrected record as the gold set, so the labels your
reviewers fix become the test set for the next model or cutoff.

### Relabel stored feedback

After changing the model, options, fields or cutoffs, relabel what is already stored:

```bash
obsei reprocess --dry-run                 # count what would change
obsei reprocess --since 2026-09-01        # relabel records created since then
```

Every stored record with `classify` labels is labelled again by the current config; human
corrections are kept. The report counts changed answers per question with the most common changes
(`intent  14 changed: praise -> bug (9), ...`). Records are updated in place and the run is
audited; sinks are not called and routes are not re-run. DuckDB allows one writer, so stop
`obsei serve` before `reprocess` or `correct`.

A practical loop: start with a `review` route, correct what lands there, run
`obsei eval --from-store`, adjust options and cutoffs, then `obsei reprocess`.
