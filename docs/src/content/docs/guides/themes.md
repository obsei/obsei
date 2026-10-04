---
title: Themes, dedupe and ask
description: Stable themes, near-duplicates and cited answers.
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
  embedder: hashing        # offline, any script; or an llms name with embedding_model
  similarity: null         # default 0.3 for hashing, 0.75 for embedding models
  duplicate_similarity: 0.9
  labeler: local           # llms name; without it, keyword labels
  label_language: English  # labels in your team's language; feedback stays as written
  k_anonymity: 5
```

The built-in `hashing` embedder needs no model and works in every script, but it groups by
wording, so the same issue in two languages forms two themes. A multilingual embedding model
(for example `bge-m3` or `multilingual-e5` on Ollama or vLLM) groups by meaning across languages:

```yaml
llms:
  local:
    base_url: http://localhost:11434/v1
    model: qwen3:8b
    embedding_model: bge-m3
themes:
  embedder: local
```

## k-anonymity

Themes and aggregate groups smaller than `k_anonymity` records are never labelled, listed,
exported or shown in Studio, so small groups cannot single out a customer.

## Ask

`obsei ask` retrieves the most relevant feedback, adds the theme overview, and asks your model to
answer in the language of the question, quoting customers in their own language and citing record
ids. Citations are checked against the records actually retrieved.
