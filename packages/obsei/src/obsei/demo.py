"""Synthetic multilingual demo data for the static Studio demo. No real customer text."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from obsei.core.record import Enrichment, Record, SourceRef
from obsei.privacy.redact import RegexRedactor

SOURCES = ("appstore", "playstore", "zendesk", "survey", "bluesky")

# theme -> (intent, sentiment, rating, growth, {lang: phrases})
THEMES: dict[str, tuple[str, str, int, float, dict[str, list[str]]]] = {
    "login": (
        "bug",
        "negative",
        1,
        1.6,
        {
            "en": [
                "I cannot log in since the update",
                "Login fails every time, cannot log in",
                "Cannot log in on my phone after update",
                "Stuck on the login screen, cannot log in",
                "Log in keeps failing with an error",
                "I cannot log in, reset link does not work. Mail me at sam@example.com",
            ],
            "es": [
                "No puedo iniciar sesión desde la actualización",
                "No puedo iniciar sesión en el móvil",
                "Error al iniciar sesión cada vez",
                "No puedo iniciar sesión, el enlace no funciona",
                "Imposible iniciar sesión desde ayer",
            ],
            "ja": [
                "アップデート後にログインできません",
                "ログインできません。エラーが出ます",
                "スマホでログインできません",
                "何度やってもログインできません",
                "ログインできません。電話は090-1234-5678です",
            ],
        },
    ),
    "billing": (
        "complaint",
        "negative",
        1,
        1.0,
        {
            "en": [
                "I was charged twice this month, refund please",
                "Double charge on my card, need a refund",
                "Charged twice for one subscription, refund me",
                "Refund the double charge on card 4111 1111 1111 1111",
                "You charged me twice, I want a refund",
            ],
            "pt": [
                "Fui cobrado duas vezes, quero reembolso",
                "Cobrança duplicada no cartão, quero reembolso",
                "Cobrado duas vezes este mês, reembolso por favor",
                "Cobrança em dobro, preciso de reembolso",
                "Me cobraram duas vezes, quero o reembolso",
            ],
            "de": [
                "Mir wurde doppelt abgebucht, bitte erstatten",
                "Doppelte Abbuchung, ich will eine Erstattung",
                "Zweimal abgebucht, bitte Erstattung",
                "Doppelt abgebucht diesen Monat, Erstattung bitte",
                "Doppelte Abbuchung auf der Karte, bitte erstatten",
            ],
        },
    ),
    "performance": (
        "bug",
        "negative",
        2,
        1.2,
        {
            "en": [
                "The app is very slow to load",
                "Very slow to load my dashboard",
                "App is slow and laggy since the update",
                "Loading is very slow on Android",
                "So slow to load, takes a minute",
            ],
            "hi": [
                "ऐप बहुत धीमा चलता है",
                "ऐप खुलने में बहुत धीमा है",
                "अपडेट के बाद ऐप बहुत धीमा है",
                "ऐप बहुत धीमा है, लोड नहीं होता",
                "ऐप बहुत धीमा है, कृपया ठीक करें",
            ],
        },
    ),
    "dark mode": (
        "feature_request",
        "neutral",
        4,
        0.8,
        {
            "en": [
                "Please add a dark mode",
                "Would love a dark mode option",
                "Dark mode please, the app is too bright",
                "Any plans for dark mode?",
                "Please add dark mode for night use",
            ],
            "fr": [
                "Ajoutez un mode sombre s'il vous plaît",
                "Un mode sombre serait génial",
                "Mode sombre s'il vous plaît, trop lumineux",
                "Vivement un mode sombre",
                "Merci d'ajouter un mode sombre",
            ],
        },
    ),
    "praise": (
        "praise",
        "positive",
        5,
        1.0,
        {
            "en": [
                "Love the new design, great app",
                "Great app, love the clean design",
                "Love it, the new design is great",
                "Beautiful design, love using this app",
                "Great app and lovely design",
            ],
            "id": [
                "Aplikasinya bagus sekali, desainnya keren",
                "Desainnya keren, aplikasinya bagus",
                "Aplikasi bagus, desain baru keren",
                "Suka sekali desain barunya, aplikasi bagus",
                "Aplikasi yang bagus dengan desain keren",
            ],
        },
    ),
}


def demo_records(now: datetime | None = None) -> list[Record]:
    moment = now or datetime.now(UTC)
    records: list[Record] = []
    for theme, (intent, sentiment, rating, growth, phrases) in THEMES.items():
        for lang, texts in phrases.items():
            for i, text in enumerate(texts):
                age = int(55 / (growth * (i + 1)))
                records.append(
                    Record(
                        source=SourceRef(
                            type=SOURCES[(len(records) + i) % len(SOURCES)],
                            instance="demo",
                            native_id=f"{theme}-{lang}-{i}",
                        ),
                        text=text,
                        created_at=moment - timedelta(days=age, hours=i),
                        rating=float(rating),
                        lang=lang,
                        enrichments={
                            "classify": Enrichment(
                                value={"intent": intent, "sentiment": sentiment, "language": lang},
                                confidence=0.9,
                                model="demo",
                                at=moment,
                            )
                        },
                    )
                )
    return RegexRedactor().redact(records)
