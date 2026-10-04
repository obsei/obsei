# obsei-typeform

Survey responses from Typeform's [Responses API](https://www.typeform.com/developers/responses/),
fetched incrementally with your own personal access token.

Install it from PyPI once published:

```bash
pip install obsei-typeform
```

Until then, install it from Git:

```bash
pip install "obsei-typeform @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-typeform"
```

Create a personal access token with the `responses:read` scope and export it (the name is the
`token_env` field, `TYPEFORM_TOKEN` by default). Accounts in Typeform's EU data center use
`api_base: https://api.eu.typeform.com`.

```yaml
plugins: [typeform]
pipelines:
  - name: surveys
    sources:
      - key: onboarding
        type: typeform
        config:
          form_id: aBcD1234
          text_fields: [what_could_be_better, anything_else]
          rating_field: nps
          lang_hidden_field: lang
```

| Field | Default | Meaning |
|---|---|---|
| `form_id` | required | The id in the form's URL (`https://<account>.typeform.com/to/<form_id>`). |
| `instance` | `form_id` | Label stored with each record. |
| `token_env` | `TYPEFORM_TOKEN` | Environment variable holding the token. |
| `api_base` | `https://api.typeform.com` | `https://api.eu.typeform.com` for EU accounts. |
| `text_fields` | all text answers | Field refs (or ids) whose answers form the text, in this order. Choice, multiple-choice, number and yes/no answers are allowed too. |
| `rating_field` | none | Ref of a number, rating, opinion scale or NPS field stored as the record's rating. |
| `lang_hidden_field` | none | Hidden field holding the respondent's language. |
| `author_hidden_field` | none | Hidden field holding a respondent id, stored only as a pseudonym (needs `OBSEI_PSEUDONYM_SALT`). |
| `since` | all responses | Oldest submission to fetch on the first run. |
| `page_size`, `max_pages` | 200, 50 | Responses per request (up to 1000) and requests per run. |

Only completed responses are fetched. Hidden fields, metadata and answers that are not in
`text_fields` (such as email or phone questions) never reach the record text, and surveys stay
anonymous unless you set `author_hidden_field`. The text still goes through obsei's redaction.
List `text_fields` explicitly when a form also asks free-text questions such as a name.

Each run pages from the newest response back to the previous run's position; a run stopped by
`max_pages` resumes where it left off.
