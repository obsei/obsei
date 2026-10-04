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

- **Pseudonyms.** Author handles become salted HMAC pseudonyms (`psn_...`). Without
  `OBSEI_PSEUDONYM_SALT`, authors are dropped. Pseudonymised data is still personal data.
- **Purpose.** Every record carries a purpose tag (default `feedback-analytics`).

## At rest and in use

- The DuckDB file is encrypted (AES via OpenSSL) with `OBSEI_DB_KEY`.
- Egress is air-gapped by default; public model and sink endpoints must be allowed explicitly.
- MCP tools never return author pseudonyms. Webhook and Parquet sinks omit them by default.

## Data subject requests and retention

```bash
obsei export --author "ana@example.com" --out ana.jsonl   # access / portability
obsei forget --author "ana@example.com"                   # erasure
obsei forget --older-than-days 365                        # retention
obsei forget --source appstore --instance 284882215       # remove a source
```

These map to rights found in the GDPR and UK GDPR, India's DPDP Act, Brazil's LGPD, California's
CCPA/CPRA, Japan's APPI, South Africa's POPIA, China's PIPL, Singapore's PDPA and others. Check
the requirements that apply to you.
