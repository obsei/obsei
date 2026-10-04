---
title: GitHub Action
description: Run pipelines on a schedule in GitHub Actions.
sidebar:
  order: 8
---

```yaml
- uses: obsei/obsei@<release tag or commit SHA>
  with:
    config: .github/obsei.yaml
    extras: google
  env:
    OBSEI_DB_KEY: ${{ secrets.OBSEI_DB_KEY }}
    OBSEI_PSEUDONYM_SALT: ${{ secrets.OBSEI_PSEUDONYM_SALT }}
```

A complete daily recipe (app reviews → classify → GitHub issues and Slack, with the encrypted
database kept in the Actions cache) is in
[`examples/github-actions`](https://github.com/obsei/obsei/tree/master/examples/github-actions).
Runs on GitHub-hosted runners send feedback to the model you configure; use a self-hosted runner
for air-gapped setups.
