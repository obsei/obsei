# obsei-telegram

Posts matching feedback to a Telegram chat, group or channel through the
[Bot API](https://core.telegram.org/bots/api).

Install it from PyPI:

```bash
pip install obsei-telegram
```

Create a bot with [@BotFather](https://t.me/BotFather) and copy its token into an environment
variable; it controls the bot, so treat it as a secret and never put it in `obsei.yaml`. Add the
bot to the chat it should post to. For a channel, make it an administrator that can post.

```yaml
plugins: [telegram]
egress:
  mode: private
  allowed_hosts: [api.telegram.org]
pipelines:
  - name: alerts
    sources:
      - key: ios
        type: appstore
        config: {app_id: "284882215"}
    enrichers:
      - type: classify
        config: {llm: default}
    sinks:
      - type: telegram
        config:
          chat_id: -1001234567890
          when: {classify.sentiment: [negative]}
          max_rating: 2
```

| Field | Default | Meaning |
|---|---|---|
| `bot_token_env` | `TELEGRAM_BOT_TOKEN` | Environment variable holding the bot token. |
| `chat_id` | required | Numeric chat id, or `@username` for a public channel. |
| `when` | all records | Routing conditions to match (values, `is`, `min_confidence`, `gte`/`lte`, `review`), as in the `slack` sink. |
| `max_rating` | none | Only records rated at or below this. |
| `max_messages` | 10 | Messages posted per run (up to 50); one more message counts the rest. |
| `max_text` | 1000 | Characters of feedback shown per record. |

Each matching record becomes one message showing its source, rating, sentiment and intent (when
the `classify` enricher ran), its redacted text and an *Open* link for http(s) URLs. Customer
text is HTML-escaped, so it cannot add links or formatting, and link previews are off. Authors
are never sent. `obsei check` calls `getChat` to confirm the token and chat without posting.

`api.telegram.org` is public, so obsei's default air-gapped egress policy blocks it. Allow it
with `OBSEI_EGRESS_MODE=private` and `OBSEI_EGRESS_ALLOW=api.telegram.org` or the `egress` block
above.

The Bot API puts the token in the request URL. Errors from this sink report only the status and
Telegram's description, but if you turn on debug logging for `httpx` it logs request URLs, token
included.
