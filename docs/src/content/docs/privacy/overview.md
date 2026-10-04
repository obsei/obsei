---
title: Privacy controls
description: What obsei does to protect personal data.
---

obsei provides controls that *support* compliance with privacy laws. It does not make compliance
claims: the organisation deploying it remains the controller and decides its lawful basis,
retention and transfers.

## At ingest

- **Redaction.** Detectors run before storage, models and sinks. Identifiers with checksums are
  validated to avoid false positives. Digits in any script are recognised (Arabic-Indic,
  Devanagari, full-width and others).

| Region | Detectors |
| --- | --- |
| global | email, payment card (Luhn), IBAN (mod 97), IPv4, IPv6, phone numbers |
| north_america | US SSN, Canadian SIN |
| uk | National Insurance number, NHS number |
| eu | France NIR, Spain DNI/NIE, Italy codice fiscale, Poland PESEL, Netherlands BSN |
| latam | Brazil CPF, Mexico CURP |
| apac | China resident ID, Singapore NRIC/FIN, Japan My Number, Australia TFN |
| india | Aadhaar (Verhoeff), PAN |
| africa | South Africa ID |

- **Names (optional).** Regexes cannot find person names. `pip install "obsei[names]>=1.0.0a1"`
  adds a local multilingual GLiNER model that replaces names with `<PERSON>` after the regex pass:

  ```yaml
  privacy:
    names:
      enabled: true
      model: /models/gliner_multi_pii-v1   # downloaded once; required in air-gapped mode
      threshold: 0.5
  ```

  Download the model with `huggingface-cli download urchade/gliner_multi_pii-v1 --local-dir
  /models/gliner_multi_pii-v1`. It runs on CPU; expect tens of milliseconds per record. Like any
  model it can miss names, so treat it as risk reduction, not a guarantee.
- **Pseudonyms.** Author handles become salted HMAC pseudonyms (`psn_...`). Without
  `OBSEI_PSEUDONYM_SALT`, authors are dropped. Pseudonymised data is still personal data.
- **Purpose.** Every record carries a purpose tag (default `feedback-analytics`).

## At rest and in use

- The DuckDB file is encrypted (AES via OpenSSL) with `OBSEI_DB_KEY`. The first encrypted write
  downloads DuckDB's `httpfs` extension, so it needs network access once unless the extension is
  already installed (the container image ships with it). To pre-install it:
  `python -c "import duckdb; duckdb.connect().execute('INSTALL httpfs')"`.
- Egress is air-gapped by default; public model and sink endpoints must be allowed explicitly.
- MCP tools never return author pseudonyms. Webhook and Parquet sinks omit them by default.

## Data subject requests and retention

```bash
obsei export --author "ana@example.com" --out ana.jsonl   # access / portability
obsei forget --author "ana@example.com"                   # erasure
obsei forget --older-than-days 365                        # retention
obsei forget --source appstore --instance 284882215       # remove a source
obsei audit                                               # log of erasures and exports
```

Every `forget` and `export` is written to an append-only audit log inside the encrypted store,
with the filters and counts but never the raw handle.

`forget` erases records from the obsei database only. Copies already delivered to sinks (Parquet
files, SQL tables, Slack messages, Jira, Linear or GitHub issues, webhook receivers) are not
touched; erase them in those systems as part of the same request.

These map to rights found in the GDPR and UK GDPR, India's DPDP Act, Brazil's LGPD, California's
CCPA/CPRA, Japan's APPI, South Africa's POPIA, China's PIPL, Singapore's PDPA and others. Check
the requirements that apply to you.
