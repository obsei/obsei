"""Synthetic multilingual demo data for the static Studio demo. No real customer text."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from obsei.core.record import Enrichment, Record, SourceRef
from obsei.privacy.redact import RegexRedactor
from obsei.store import Store


@dataclass(frozen=True)
class Issue:
    """One recurring demo issue. Each language group comes from one source, so source facets
    reach k-anonymity; ``days_ago`` is cycled over each group's records."""

    label: str
    intent: str
    sentiment: str
    rating: int
    days_ago: tuple[int, ...]
    groups: dict[str, tuple[str, tuple[str, ...]]]


ISSUES: dict[str, Issue] = {
    "login": Issue(
        label="Can't log in",
        intent="bug",
        sentiment="negative",
        rating=1,
        days_ago=(1, 3, 5, 9, 2, 4),
        groups={
            "en": (
                "appstore",
                (
                    "I cannot log in since the update",
                    "Login fails every time, cannot log in",
                    "Cannot log in on my phone after update",
                    "Stuck on the login screen, cannot log in",
                    "Cannot log in, it keeps failing with an error",
                    "I cannot log in, reset link does not work. Mail me at sam@example.com",
                ),
            ),
            "es": (
                "playstore",
                (
                    "No puedo iniciar sesión desde la actualización",
                    "No puedo iniciar sesión en el móvil",
                    "Error al iniciar sesión cada vez",
                    "No puedo iniciar sesión, el enlace no funciona",
                    "Imposible iniciar sesión desde ayer",
                ),
            ),
            "ja": (
                "appstore",
                (
                    "アップデート後にログインできません",
                    "ログインできません。エラーが出ます",
                    "スマホでログインできません",
                    "何度やってもログインできません",
                    "ログインできません。電話は090-1234-5678です",
                ),
            ),
        },
    ),
    "billing": Issue(
        label="Charged twice",
        intent="complaint",
        sentiment="negative",
        rating=1,
        days_ago=(48, 30, 12, 20, 5),
        groups={
            "en": (
                "zendesk",
                (
                    "I was charged twice this month, refund please",
                    "Charged twice on my card, need a refund",
                    "Charged twice for one subscription, refund me",
                    "Charged twice on card 4111 1111 1111 1111, refund please",
                    "You charged me twice, I want a refund",
                ),
            ),
            "pt": (
                "zendesk",
                (
                    "Fui cobrado duas vezes, quero reembolso",
                    "Cobrança duplicada no cartão, quero reembolso",
                    "Cobrado duas vezes este mês, reembolso por favor",
                    "Cobrança em dobro, preciso de reembolso",
                    "Me cobraram duas vezes, quero o reembolso",
                ),
            ),
            "de": (
                "zendesk",
                (
                    "Mir wurde doppelt abgebucht, bitte erstatten",
                    "Doppelte Abbuchung, ich will eine Erstattung",
                    "Zweimal abgebucht, bitte Erstattung",
                    "Doppelt abgebucht diesen Monat, Erstattung bitte",
                    "Doppelte Abbuchung auf der Karte, bitte erstatten",
                ),
            ),
        },
    ),
    "performance": Issue(
        label="Slow to load",
        intent="bug",
        sentiment="negative",
        rating=2,
        days_ago=(40, 9, 26, 16, 3),
        groups={
            "en": (
                "playstore",
                (
                    "The app is very slow to load",
                    "Very slow to load my dashboard",
                    "App is slow and laggy since the update",
                    "Loading is very slow on Android",
                    "So slow to load, takes a minute",
                ),
            ),
            "hi": (
                "playstore",
                (
                    "ऐप बहुत धीमा चलता है",
                    "ऐप खुलने में बहुत धीमा है",
                    "अपडेट के बाद ऐप बहुत धीमा है",
                    "ऐप बहुत धीमा है, लोड नहीं होता",
                    "ऐप बहुत धीमा है, कृपया ठीक करें",
                ),
            ),
        },
    ),
    "dark_mode": Issue(
        label="Dark mode request",
        intent="feature_request",
        sentiment="neutral",
        rating=4,
        days_ago=(52, 35, 22, 10, 18),
        groups={
            "en": (
                "survey",
                (
                    "Please add a dark mode",
                    "Would love a dark mode option",
                    "Dark mode please, the app is too bright",
                    "Any plans for dark mode?",
                    "Please add dark mode for night use",
                ),
            ),
            "fr": (
                "bluesky",
                (
                    "Ajoutez un mode sombre s'il vous plaît",
                    "Un mode sombre serait génial",
                    "Mode sombre s'il vous plaît, trop lumineux",
                    "Vivement un mode sombre",
                    "Merci d'ajouter un mode sombre",
                ),
            ),
        },
    ),
    "praise": Issue(
        label="Love the new look",
        intent="praise",
        sentiment="positive",
        rating=5,
        days_ago=(45, 6, 28, 11, 33),
        groups={
            "en": (
                "appstore",
                (
                    "Love the new design, great app",
                    "Great app, love the clean design",
                    "Love it, the new design is great",
                    "Beautiful design, love using this app",
                    "Great app and lovely design",
                ),
            ),
            "id": (
                "playstore",
                (
                    "Aplikasinya bagus sekali, desainnya keren",
                    "Desainnya keren, aplikasinya bagus",
                    "Aplikasi bagus, desain baru keren",
                    "Suka sekali desain barunya, aplikasi bagus",
                    "Aplikasi yang bagus dengan desain keren",
                ),
            ),
        },
    ),
}


def demo_records(now: datetime | None = None) -> list[Record]:
    moment = now or datetime.now(UTC)
    records: list[Record] = []
    for key, issue in ISSUES.items():
        for g, (lang, (source, texts)) in enumerate(issue.groups.items()):
            for i, text in enumerate(texts):
                age = issue.days_ago[i % len(issue.days_ago)]
                records.append(
                    Record(
                        source=SourceRef(
                            type=source, instance="demo", native_id=f"{key}-{lang}-{i}"
                        ),
                        text=text,
                        created_at=moment - timedelta(days=age, hours=i + 3 * g),
                        rating=float(issue.rating),
                        lang=lang,
                        enrichments={
                            "classify": Enrichment(
                                value={
                                    "intent": issue.intent,
                                    "sentiment": issue.sentiment,
                                    "language": lang,
                                },
                                confidence=0.9,
                                model="demo",
                                at=moment,
                            )
                        },
                    )
                )
    return RegexRedactor().redact(records)


def label_demo_themes(store: Store, *, k: int) -> None:
    """Give each shown theme the curated label of its majority demo issue, whatever embedder
    grouped them; the language is appended when several themes share an issue."""
    picks: dict[str, tuple[str, str | None]] = {}
    for theme in store.theme_summaries(min_size=k):
        records = [store.get(rid) for rid in store.theme_record_ids(theme.id, theme.size)]
        kept = [r for r in records if r is not None]
        issue = Counter(r.source.native_id.split("-", 1)[0] for r in kept).most_common(1)[0][0]
        lang = Counter(r.lang for r in kept).most_common(1)[0][0]
        picks[theme.id] = (issue, lang)
    shared = Counter(issue for issue, _ in picks.values())
    for theme_id, (issue, lang) in picks.items():
        label = ISSUES[issue].label
        store.label_theme(theme_id, f"{label} ({lang})" if shared[issue] > 1 else label, None)
