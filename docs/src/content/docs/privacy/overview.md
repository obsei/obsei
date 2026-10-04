---
title: Privacy controls
description: What obsei does to protect personal data.
---

obsei provides controls that *support* compliance with privacy laws. It does not make compliance
claims: the organisation deploying it remains the controller and decides its lawful basis,
retention and transfers.

## At ingest

- **Redaction.** Detectors run before storage, models and sinks, over the text, context fields,
  source URL and native id, and author locale. Identifiers with checksums are
  validated to avoid false positives. Digits in any script are recognised (Arabic-Indic,
  Devanagari, full-width and others).

| Region | Detectors |
| --- | --- |
| Global | email, payment card (Luhn), IBAN (mod 97), IPv4, IPv6, phone numbers |
| North America | US SSN, Canadian SIN |
| United Kingdom | National Insurance number, NHS number |
| European Union | France NIR, Spain DNI/NIE, Italy codice fiscale, Poland PESEL, Netherlands BSN |
| Latin America | Brazil CPF, Mexico CURP |
| Asia-Pacific | China resident ID, Singapore NRIC/FIN, Japan My Number, Australia TFN |
| India | Aadhaar (Verhoeff), PAN |
| Africa | South Africa ID |

In `obsei.yaml`, `privacy.regions` takes the keys `global`, `north_america`, `uk`, `eu`, `latam`,
`apac`, `india` and `africa` (all by default).

- **Names (optional).** Regexes cannot find person names. The `names` extra
  ([how to add an extra](/quickstart/#optional-extras)) adds a local multilingual GLiNER model that replaces names with `<PERSON>` after the regex pass:

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

- The DuckDB file is encrypted (AES via OpenSSL) with `OBSEI_DB_KEY`. Writing it needs DuckDB's
  `httpfs` extension. In `private` or `hybrid` egress mode the first encrypted write downloads it
  if it is missing; air-gapped mode (the default) never downloads it. To pre-install it, run
  `INSTALL httpfs` once with network access into a directory, copy that directory over (same
  DuckDB version and platform) and point `OBSEI_DUCKDB_EXTENSIONS` at it. The container image
  ships with it pre-installed.
  `obsei doctor` reports whether it is ready. On a machine with network access, the one-time
  install is `"$(uv tool dir)/obsei/bin/python" -c "import duckdb; duckdb.connect().execute('INSTALL httpfs')"`
  (or the same `python -c` in the environment where you installed obsei with pip).
- Egress is air-gapped by default; public model and sink endpoints must be allowed explicitly.
  Every redirect hop of a sink request is checked as well, and a redirect to another origin
  drops credentials and custom headers. The REST source sends its credentials only to the origin
  of its configured `url`, never to hosts named by pagination links.
- Themes, their source, language and intent breakdowns, average ratings and graph links are shown
  only when they come from at least `themes.k_anonymity` people (distinct author pseudonyms;
  records without an author count individually). Theme labels never quote feedback.
- MCP tools never return author pseudonyms. Webhook and Parquet sinks omit them by default.

## Data subject requests and retention

```bash
obsei export --author "ana@example.com" --out ana.jsonl   # access / portability
obsei forget --author "ana@example.com"                   # erasure
obsei forget --older-than-days 365                        # retention
obsei forget --source appstore --instance 284882215       # remove a source
obsei audit                                               # log of erasures and exports
```

These commands use the store from `obsei.yaml` (`-c` picks another config, `--db` overrides the
path) and never create a new database. Every `forget` and `export` is written to an append-only
audit log inside the encrypted store, with the filters and counts but never the raw handle.

`forget` leaves tombstones: the erased record ids and, for `--author`, the author pseudonym. A
source that sends the same records again (CSV, file drop, REST without `since_param`) cannot
bring them back, and new records by an erased author are not stored. Tombstones hold no raw
personal data.

`forget` erases records from the obsei database only. Copies already delivered to sinks (Parquet
files, SQL tables, Slack messages, Jira, Linear or GitHub issues, webhook receivers) are not
touched; erase them in those systems as part of the same request.

These map to rights found in the GDPR and UK GDPR, India's DPDP Act, Brazil's LGPD, California's
CCPA/CPRA, Japan's APPI, South Africa's POPIA, China's PIPL, Singapore's PDPA and others. Check
the requirements that apply to you.
