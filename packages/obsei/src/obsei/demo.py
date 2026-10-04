"""Synthetic multilingual demo data for the static Studio demo. No real customer text, people or
identifiers: contact details and ID numbers are made up (checksum-valid so redaction shows)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from obsei import studio
from obsei.core.record import Author, Enrichment, Record, SourceRef
from obsei.privacy.pseudonym import pseudonymize
from obsei.privacy.redact import RegexRedactor
from obsei.store import Store
from obsei.studio import AskExample, RedactionExample, Showcase, Snapshot

DEMO_SALT = b"obsei-synthetic-demo-salt"
LANGUAGES = {
    "ar": "Arabic",
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "hi": "Hindi",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
}
RATED_SOURCES = frozenset({"appstore", "playstore", "survey"})
ANONYMOUS_SOURCES = frozenset({"survey"})


@dataclass(frozen=True)
class Group:
    """Feedback about one issue in one language from one source (at least k people)."""

    lang: str
    source: str
    texts: tuple[str, ...]


@dataclass(frozen=True)
class Issue:
    """One recurring demo issue; ``days_ago`` is cycled over each group's records."""

    label: str
    intent: str
    sentiment: str
    rating: int
    days_ago: tuple[int, ...]
    groups: tuple[Group, ...]


ISSUES: dict[str, Issue] = {
    "login": Issue(
        label="Can't log in",
        intent="bug",
        sentiment="negative",
        rating=1,
        days_ago=(0, 1, 2, 1, 3, 4, 2, 5, 0, 3, 47, 1, 2, 4, 30, 3, 1, 6),
        groups=(
            Group(
                "en",
                "appstore",
                (
                    "I can't log in since the update",
                    "Since the latest update I can't log in",
                    "Can't log in after updating the app",
                    "After the update, login fails every time",
                    "I can't log in to my account since the update",
                    "Can't log in since the update and the reset email never arrives. "
                    "Reach me at sam.rivera@example.com",
                ),
            ),
            Group(
                "es",
                "playstore",
                (
                    "No puedo iniciar sesión desde la actualización",
                    "Desde la última actualización no puedo iniciar sesión",
                    "No puedo iniciar sesión después de actualizar la app",
                    "Tras la actualización, el inicio de sesión falla siempre",
                    "No puedo iniciar sesión en mi cuenta desde la actualización",
                ),
            ),
            Group(
                "ja",
                "appstore",
                (
                    "アップデート以降ログインできません",
                    "最新のアップデートからログインできません",
                    "アプリを更新したらログインできなくなりました",
                    "アップデートしてからログインできません",
                    "アップデート後、毎回ログインに失敗します",
                    "アップデート以降ログインできません。電話は090-1234-5678です",
                ),
            ),
            Group(
                "ko",
                "playstore",
                (
                    "업데이트 이후 로그인이 되지 않습니다",
                    "최신 업데이트 이후 로그인이 되지 않습니다",
                    "업데이트 이후 계정에 로그인이 되지 않습니다",
                    "업데이트 후 로그인이 계속 되지 않습니다",
                    "앱을 업데이트한 후 로그인이 되지 않습니다",
                    "업데이트 이후로 로그인이 되지 않습니다",
                ),
            ),
            Group(
                "ar",
                "zendesk",
                (
                    "لا أستطيع تسجيل الدخول منذ التحديث",
                    "منذ آخر تحديث لا أستطيع تسجيل الدخول",
                    "لا يمكنني تسجيل الدخول بعد تحديث التطبيق",
                    "منذ التحديث لا يمكنني تسجيل الدخول إلى حسابي",
                    "بعد التحديث يفشل تسجيل الدخول في كل مرة",
                    "لا أستطيع تسجيل الدخول منذ التحديث. رقمي ٠٥٠١٢٣٤٥٦٧",
                ),
            ),
        ),
    ),
    "billing": Issue(
        label="Charged twice",
        intent="complaint",
        sentiment="negative",
        rating=1,
        days_ago=(52, 38, 24, 11, 45, 3, 31, 17, 55, 20, 41, 27),
        groups=(
            Group(
                "en",
                "zendesk",
                (
                    "I was charged twice this month",
                    "I was charged twice for my subscription",
                    "I got charged twice for the same plan",
                    "My card was charged twice this month",
                    "I was charged twice on card 4111 1111 1111 1111",
                ),
            ),
            Group(
                "pt",
                "zendesk",
                (
                    "Fui cobrado duas vezes este mês",
                    "Fui cobrado duas vezes pela assinatura",
                    "Fui cobrado duas vezes pelo mesmo plano",
                    "Meu cartão foi cobrado duas vezes este mês",
                    "Fui cobrado duas vezes, meu CPF é 482.915.736-46",
                ),
            ),
            Group(
                "de",
                "zendesk",
                (
                    "Ich wurde diesen Monat zweimal belastet",
                    "Sie haben mir diesen Monat zweimal berechnet",
                    "Ich wurde für mein Abo zweimal belastet",
                    "Mir wurde zweimal Geld abgebucht",
                    "Ich wurde zweimal belastet, bitte erstatten Sie auf "
                    "DE89 3704 0044 0532 0130 00",
                    "Ich wurde zweimal belastet und möchte mein Geld zurück",
                ),
            ),
        ),
    ),
    "performance": Issue(
        label="Slow to load",
        intent="bug",
        sentiment="negative",
        rating=2,
        days_ago=(41, 27, 13, 50, 34, 19, 22, 44, 30, 5, 48),
        groups=(
            Group(
                "en",
                "playstore",
                (
                    "The app is very slow to load",
                    "The app is so slow to load",
                    "Very slow to load every time",
                    "The app is slow to load since last month",
                    "The app is really slow to load",
                ),
            ),
            Group(
                "hi",
                "playstore",
                (
                    "ऐप लोड होने में बहुत धीमा है",
                    "ऐप बहुत धीमे लोड होता है",
                    "ऐप हर बार बहुत धीमा लोड होता है",
                    "पिछले महीने से ऐप लोड होने में धीमा है",
                    "ऐप लोड होने में सच में बहुत धीमा है",
                ),
            ),
            Group(
                "it",
                "github",
                (
                    "L'app è molto lenta a caricarsi",
                    "L'app è lentissima a caricarsi",
                    "L'app è lentissima a caricarsi ogni volta",
                    "L'app è lenta a caricarsi dal mese scorso",
                    "L'app è davvero lenta a caricarsi",
                ),
            ),
        ),
    ),
    "dark_mode": Issue(
        label="Dark mode request",
        intent="feature_request",
        sentiment="neutral",
        rating=4,
        days_ago=(54, 36, 22, 10, 47, 29, 15, 40, 6, 33),
        groups=(
            Group(
                "en",
                "survey",
                (
                    "Please add a dark mode",
                    "I'd really like a dark mode",
                    "Please add a dark mode for the evening",
                    "A dark mode would be great",
                    "Dark mode please",
                ),
            ),
            Group(
                "fr",
                "bluesky",
                (
                    "Ajoutez un mode sombre s'il vous plaît",
                    "J'aimerais beaucoup un mode sombre",
                    "Ajoutez un mode sombre pour le soir",
                    "Un mode sombre, ce serait super",
                    "Mode sombre s'il vous plaît",
                ),
            ),
            Group(
                "it",
                "github",
                (
                    "Aggiungete una modalità scura, per favore",
                    "Vorrei tanto una modalità scura",
                    "Aggiungete una modalità scura per la sera",
                    "Una modalità scura sarebbe fantastica",
                    "Modalità scura, per favore",
                ),
            ),
        ),
    ),
    "praise": Issue(
        label="Love the new look",
        intent="praise",
        sentiment="positive",
        rating=5,
        days_ago=(33, 26, 18, 19, 39, 14, 28, 45, 4, 23, 50),
        groups=(
            Group(
                "en",
                "appstore",
                (
                    "Love the new design, it feels so clean",
                    "The new design looks fantastic",
                    "I love the new design of the app",
                    "The new design is much nicer",
                    "Really like the new design",
                ),
            ),
            Group(
                "id",
                "playstore",
                (
                    "Suka banget sama desain barunya",
                    "Desain barunya keren sekali",
                    "Saya suka desain baru aplikasinya",
                    "Desain barunya jauh lebih bagus",
                    "Suka sekali dengan desain yang baru",
                ),
            ),
            Group(
                "it",
                "appstore",
                (
                    "Adoro il nuovo design, è pulitissimo",
                    "Il nuovo design è fantastico",
                    "Adoro il nuovo design dell'app",
                    "Il nuovo design è molto più bello",
                    "Mi piace tanto il nuovo design",
                ),
            ),
        ),
    ),
    "checkout": Issue(
        label="Checkout fails",
        intent="bug",
        sentiment="negative",
        rating=1,
        days_ago=(25, 18, 32, 21, 11, 37, 16, 23, 29, 44),
        groups=(
            Group(
                "en",
                "playstore",
                (
                    "Checkout fails when I try to pay",
                    "Payment fails at checkout",
                    "Checkout keeps failing when I pay",
                    "I can't pay, checkout fails every time",
                    "Checkout fails at the payment step",
                ),
            ),
            Group(
                "de",
                "zendesk",
                (
                    "Der Checkout schlägt beim Bezahlen fehl",
                    "Die Zahlung im Checkout schlägt fehl",
                    "Der Checkout scheitert jedes Mal beim Bezahlen",
                    "Ich kann nicht bezahlen, der Checkout schlägt fehl",
                    "Der Checkout schlägt bei der Zahlung fehl",
                    "Checkout schlägt fehl. Rufen Sie mich an: +49 151 2345 6789",
                ),
            ),
            Group(
                "ar",
                "playstore",
                (
                    "يفشل الدفع عندما أحاول الدفع",
                    "عملية الدفع تفشل كل مرة أحاول الدفع",
                    "إتمام الطلب يفشل عندما أحاول الدفع",
                    "تفشل عملية الدفع عند محاولة الدفع",
                    "الدفع يفشل عند الخروج",
                ),
            ),
        ),
    ),
    "support": Issue(
        label="Great support",
        intent="praise",
        sentiment="positive",
        rating=5,
        days_ago=(49, 35, 21, 2, 42, 28, 14, 53, 17, 38),
        groups=(
            Group(
                "en",
                "survey",
                (
                    "Support solved my problem quickly",
                    "The support team fixed my issue fast",
                    "Support solved my problem in minutes",
                    "Great support, my problem was solved quickly",
                    "Support solved my problem really quickly",
                ),
            ),
            Group(
                "es",
                "survey",
                (
                    "El soporte resolvió mi problema rápido",
                    "El equipo de soporte arregló mi problema enseguida",
                    "El soporte resolvió mi problema en minutos",
                    "Gran soporte, resolvieron mi problema rápido",
                    "El soporte resolvió mi problema muy rápido",
                ),
            ),
            Group(
                "pt",
                "zendesk",
                (
                    "O suporte resolveu meu problema rápido",
                    "A equipe de suporte resolveu meu problema rapidinho",
                    "O suporte resolveu meu problema em minutos",
                    "Ótimo suporte, resolveram meu problema rápido",
                    "O suporte resolveu meu problema muito rápido",
                ),
            ),
        ),
    ),
    "delivery": Issue(
        label="Delivery late",
        intent="complaint",
        sentiment="negative",
        rating=2,
        days_ago=(30, 44, 16, 51, 23, 37, 9, 26, 5, 19),
        groups=(
            Group(
                "en",
                "bluesky",
                (
                    "My delivery was late",
                    "My order arrived a week late",
                    "Delivery is late again",
                    "My package is days late",
                    "Late delivery for the third time this month",
                ),
            ),
            Group(
                "fr",
                "zendesk",
                (
                    "Ma livraison était en retard",
                    "Ma commande est arrivée avec une semaine de retard",
                    "Livraison encore en retard",
                    "Mon colis a plusieurs jours de retard",
                    "Troisième livraison en retard ce mois-ci",
                ),
            ),
            Group(
                "hi",
                "zendesk",
                (
                    "मेरी डिलीवरी देर से आई",
                    "मेरा ऑर्डर एक हफ़्ते देर से आया",
                    "डिलीवरी फिर से देर से आई",
                    "मेरा पार्सल कई दिन देर से है",
                    "डिलीवरी देर से है। मेरा आधार 7181 9093 7865 है",
                ),
            ),
        ),
    ),
}


def raw_demo_records(now: datetime | None = None) -> list[Record]:
    """The synthetic records before redaction. Only the demo builder ever sees raw text."""
    moment = now or datetime.now(UTC)
    records: list[Record] = []
    for key, issue in ISSUES.items():
        for g, group in enumerate(issue.groups):
            for i, text in enumerate(group.texts):
                age = issue.days_ago[(i + 3 * g) % len(issue.days_ago)]
                handle = f"{group.source}/{group.lang}/{i}"
                records.append(
                    Record(
                        source=SourceRef(
                            type=group.source,
                            instance="demo",
                            native_id=f"{key}-{group.lang}-{i}",
                        ),
                        text=text,
                        created_at=moment - timedelta(days=age, hours=2 * i + 5 * g),
                        author=None
                        if group.source in ANONYMOUS_SOURCES
                        else Author(pseudonym=pseudonymize(handle, DEMO_SALT)),
                        rating=float(issue.rating) if group.source in RATED_SOURCES else None,
                        lang=group.lang,
                        enrichments={
                            "classify": Enrichment(
                                value={
                                    "intent": issue.intent,
                                    "sentiment": issue.sentiment,
                                    "language": group.lang,
                                },
                                confidence=0.9,
                                model="demo",
                                at=moment,
                            )
                        },
                    )
                )
    return records


def demo_records(raw: list[Record] | None = None) -> list[Record]:
    """The synthetic records as stored: redacted at ingest."""
    return RegexRedactor().redact(raw if raw is not None else raw_demo_records())


def issue_of(record: Record) -> str:
    return record.source.native_id.split("-", 1)[0]


def label_demo_themes(store: Store, *, k: int) -> None:
    """Give each shown theme the curated label of its majority demo issue, whatever embedder
    grouped them; the language is appended only when several themes share an issue."""
    picks: dict[str, tuple[str, str | None]] = {}
    for theme in store.theme_summaries(min_size=k):
        records = [store.get(rid) for rid in store.theme_record_ids(theme.id, theme.size)]
        kept = [r for r in records if r is not None]
        issue = Counter(issue_of(r) for r in kept).most_common(1)[0][0]
        lang = Counter(r.lang for r in kept).most_common(1)[0][0]
        picks[theme.id] = (issue, lang)
    shared = Counter(issue for issue, _ in picks.values())
    for theme_id, (issue, lang) in picks.items():
        label = ISSUES[issue].label
        store.label_theme(theme_id, f"{label} ({lang})" if shared[issue] > 1 else label, None)


REDACTION_SHOWCASE = ("login-en-5", "billing-pt-4", "delivery-hi-4")
DEMO_EVIDENCE = 50


def demo_snapshot(store: Store, raw: list[Record], *, k: int, embedder: str) -> Snapshot:
    """Label the themes and snapshot every shown record, plus the demo-only showcase."""
    label_demo_themes(store, k=k)
    snap = studio.snapshot(store, k=k, evidence_per_theme=DEMO_EVIDENCE)
    return snap.model_copy(
        update={"demo": True, "embedder": embedder, "showcase": showcase(snap, raw, store)}
    )


def showcase(snapshot: Snapshot, raw: list[Record], store: Store) -> Showcase:
    """Demo-only panels built from the generated data: before/after redaction for a few
    synthetic records, and recorded Ask answers that cite record ids shown in the evidence."""
    by_native = {r.source.native_id: r for r in raw}
    redactions = []
    for native_id in REDACTION_SHOWCASE:
        record = by_native[native_id]
        stored = store.get(record.id)
        if stored is not None:
            redactions.append(
                RedactionExample(
                    source=record.source.type,
                    lang=record.lang or "",
                    raw=record.text,
                    stored=stored.text,
                )
            )
    return Showcase(redactions=redactions, answers=_answers(snapshot, store))


def _shown(snapshot: Snapshot, store: Store, issue: str) -> list[tuple[str, Record]]:
    """(theme label, record) of evidence shown for ``issue``, newest first, one per language."""
    found: dict[str, tuple[str, Record]] = {}
    for theme in snapshot.themes:
        for item in snapshot.evidence.get(theme.id, []):
            record = store.get(item.id)
            if record is not None and issue_of(record) == issue and record.lang not in found:
                found[record.lang or ""] = (theme.label or theme.id, record)
    return sorted(found.values(), key=lambda pair: pair[1].created_at, reverse=True)


def _languages(issue: str) -> str:
    return ", ".join(LANGUAGES[g.lang] for g in ISSUES[issue].groups)


def _answers(snapshot: Snapshot, store: Store) -> list[AskExample]:
    login = [t for t in snapshot.themes if t.label and t.label.startswith(ISSUES["login"].label)]
    week = sum(t.last_7_days for t in login)
    before = sum(t.previous_7_days for t in login)
    answers: list[AskExample] = []
    cited = [r.id for _, r in _shown(snapshot, store, "login")[:3]]
    if login and cited:
        answers.append(
            AskExample(
                question="What changed this week?",
                answer=f"Login failures spiked after the latest app update: {week} reports in the "
                f"last 7 days against {before} the week before, in {_languages('login')}. "
                "Customers say they cannot sign in since updating; one adds that the password "
                "reset email never arrives.",
                citations=cited,
            )
        )
    money = _shown(snapshot, store, "billing")[:2] + _shown(snapshot, store, "checkout")[:1]
    if money:
        answers.append(
            AskExample(
                question="What are customers saying about payments?",
                answer="Two separate problems: customers charged twice for one subscription "
                f"({_languages('billing')}), and checkout failing at the payment step "
                f"({_languages('checkout')}).",
                citations=[r.id for _, r in money],
            )
        )
    praise = _shown(snapshot, store, "support")[:2] + _shown(snapshot, store, "praise")[:1]
    if praise:
        answers.append(
            AskExample(
                question="¿Qué es lo que más gusta a los clientes?",
                answer="El soporte, que resuelve los problemas en minutos, y el nuevo diseño, "
                "que describen como más limpio y bonito.",
                citations=[r.id for _, r in praise],
            )
        )
    return answers
