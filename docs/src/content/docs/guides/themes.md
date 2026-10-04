---
title: Themes, dedupe and ask
description: Stable themes, near-duplicates and cited answers.
sidebar:
  order: 5
---

```bash
obsei themes                 # embed new feedback, update themes, list them
obsei ask "Why are users in Brazil asking for refunds?"
```

## Stable themes

Each new record is embedded, marked as a near-duplicate of an earlier record when it is almost
identical, and assigned to the nearest theme or starts a new one. Theme ids never change, so
dashboards, tickets and agents can refer to them over time.

```yaml
themes:
  embedder: hashing        # offline, any script; or local, or an llms name with embedding_model
  similarity: null         # default 0.3 hashing, 0.65 local multilingual, 0.75 other models
  duplicate_similarity: 0.9
  labeler: ollama          # llms name; without it, keyword labels
  label_language: English  # labels in your team's language; feedback stays as written
  k_anonymity: 5
```

The built-in `hashing` embedder needs no model and works in every script, but it groups by
wording, so the same issue in two languages forms two themes. To group by meaning across 50+
languages, use the local multilingual model (CPU only, about 220 MB, no PyTorch):

```bash
uv tool install --force "obsei[mcp,embeddings]>=1.0.0rc1"   # or: pip install "obsei[embeddings]>=1.0.0rc1"
obsei models download --dir /models      # once, with network
export OBSEI_MODELS_DIR=/models          # air-gapped runs load it from here
```

```yaml
themes:
  embedder: local          # or local:intfloat/multilingual-e5-large for higher quality
```

Thresholds differ between models; tune `similarity` if themes split or merge too much. A model
served by Ollama or vLLM (for example `bge-m3`) also works:

```yaml
llms:
  ollama:
    base_url: http://localhost:11434/v1
    model: qwen3:8b
    embedding_model: bge-m3
themes:
  embedder: ollama         # the llms name, not "local"
```

`hashing`, `local` and `local:<model>` always mean the built-in embedders, so do not use them as
`llms` names for an embedding endpoint.

## k-anonymity

Themes and aggregate groups smaller than `k_anonymity` records are never labelled, listed,
exported or shown in Studio, so small groups cannot single out a customer.

## Ask

`obsei ask` retrieves the most relevant feedback, adds the theme overview, and asks your model to
answer in the language of the question, quoting customers in their own language and citing record
ids. Citations are checked against the records actually retrieved.
