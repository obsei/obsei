"""Studio in a real browser (Chromium via Playwright): the static demo and the live app.

Skipped unless Playwright and its Chromium are installed (``uv run playwright install chromium``).
Set ``OBSEI_CHROMIUM`` to use another Chromium binary and ``OBSEI_SCREENSHOTS`` to a directory
to keep screenshots.
"""

from __future__ import annotations

import os
import re
import socket
import threading
import time
from collections.abc import Callable, Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pytest
import uvicorn
from typer.testing import CliRunner

from obsei import studio
from obsei.cli import app as cli
from obsei.config import ObseiConfig
from obsei.core.context import Context
from obsei.demo import demo_records
from obsei.llm.embed import HashingEmbedder
from obsei.serve import create_app
from obsei.store import Store
from obsei.themes import ThemesConfig, update_themes

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import Browser, Page, ViewportSize, expect, sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import ConsoleMessage, Response

pytestmark = pytest.mark.browser
Scheme = Literal["light", "dark"]

ADMIN = "admin-token-0123456789"
VIEWER = "viewer-token-0123456789"
UNSAFE_URL = "javascript:alert(document.domain)"
NARROW: ViewportSize = {"width": 390, "height": 844}
WIDE: ViewportSize = {"width": 1280, "height": 900}
SELECTED = re.compile(r"\bselected\b")


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as pw:
        executable = os.environ.get("OBSEI_CHROMIUM") or pw.chromium.executable_path
        if not Path(executable).exists():
            pytest.skip("Chromium is not installed: uv run playwright install chromium")
        launched = pw.chromium.launch(executable_path=executable)
        yield launched
        launched.close()


class Watched:
    """A page that records console errors, failed requests and CSP violations."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.errors: list[str] = []
        page.on("console", self._console)
        page.on("pageerror", lambda exc: self.errors.append(f"pageerror: {exc}"))
        page.on("requestfailed", lambda r: self.errors.append(f"failed: {r.url}"))
        page.on("response", self._response)
        page.add_init_script(
            "document.addEventListener('securitypolicyviolation', e =>"
            " console.error('CSP blocked ' + e.violatedDirective + ' ' + e.blockedURI))"
        )

    def _console(self, message: ConsoleMessage) -> None:
        if message.type == "error":
            self.errors.append(f"console: {message.text}")

    def _response(self, response: Response) -> None:
        if response.status >= 400:
            self.errors.append(f"{response.status}: {response.url}")


@pytest.fixture
def open_page(browser: Browser) -> Iterator[Callable[..., Watched]]:
    contexts: list[Any] = []

    def make(
        *, token: str | None = None, viewport: ViewportSize = WIDE, scheme: Scheme = "light"
    ) -> Watched:
        context = browser.new_context(viewport=viewport, color_scheme=scheme)
        contexts.append(context)
        if token is not None:
            context.add_init_script(f"sessionStorage.setItem('obsei-token', {token!r})")
        return Watched(context.new_page())

    yield make
    for context in contexts:
        context.close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture(scope="module")
def static_site(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    root = tmp_path_factory.mktemp("site")
    result = CliRunner().invoke(cli, ["demo", "--out", str(root / "demo")])
    assert result.exit_code == 0, result.output
    with Store(allow_unencrypted=True) as store:
        store.upsert(demo_records())
        update_themes(store, HashingEmbedder(), ThemesConfig(k_anonymity=5))
        studio.export(store, root / "export", k=5)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def live(monkeypatch_module: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch_module.setenv("STUDIO_VIEWER_TOKEN", VIEWER)
    records = [
        r.model_copy(
            update={
                "source": r.source.model_copy(
                    update={"url": UNSAFE_URL if i % 2 else f"https://example.com/r/{i}"}
                )
            }
        )
        for i, r in enumerate(demo_records())
    ]
    store = Store(allow_unencrypted=True)
    store.upsert(records)
    update_themes(store, HashingEmbedder(), ThemesConfig(k_anonymity=5))
    cfg = ObseiConfig.model_validate(
        {
            "pipelines": [
                {"name": "p", "sources": [{"key": "s", "type": "csv", "config": {"path": "x.csv"}}]}
            ],
            "access": {
                "users": [{"name": "vic", "token_env": "STUDIO_VIEWER_TOKEN", "role": "viewer"}]
            },
        }
    )
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(cfg, Context(), store, token=ADMIN),
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="off",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)
    store.close()


@pytest.fixture(scope="module")
def monkeypatch_module() -> Iterator[pytest.MonkeyPatch]:
    with pytest.MonkeyPatch.context() as mp:
        yield mp


def no_horizontal_overflow(page: Page) -> None:
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0


def visible_labels_do_not_overlap(page: Page) -> int:
    boxes: list[dict[str, float]] = page.evaluate(
        """[...document.querySelectorAll('.graph text')]
        .filter(t => t.getAttribute('visibility') !== 'hidden')
        .map(t => t.getBoundingClientRect().toJSON())"""
    )
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            separate = (
                a["right"] <= b["left"] + 0.5
                or b["right"] <= a["left"] + 0.5
                or a["bottom"] <= b["top"] + 0.5
                or b["bottom"] <= a["top"] + 0.5
            )
            assert separate, (a, b)
    return len(boxes)


def shoot(page: Page, name: str) -> None:
    folder = os.environ.get("OBSEI_SCREENSHOTS")
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=True)


DEMO_ONLY = (".intro", ".before-after", ".ask-examples")


def assert_studio_renders(page: Page, badge: str) -> None:
    page.wait_for_selector(".evidence li")
    assert page.text_content(".badge") == badge
    brand = page.get_by_role("link", name="obsei website")
    assert brand.get_attribute("href") == "https://obsei.com"
    assert "noopener" in (brand.get_attribute("rel") or "")
    expect(page.locator(".privacy")).to_be_visible()
    assert page.locator(".privacy .stat").count() >= 3
    assert page.locator(".themes .spark").count() == page.locator(".themes li").count()
    assert page.locator(".columns li.peak").count() == 1
    expect(page.locator(".decisions")).to_contain_text("Julia-1")
    expect(
        page.locator("section.panel", has=page.get_by_role("heading", name="Routes"))
    ).to_contain_text("urgent-bugs")
    assert page.locator(".decisions h3").all_text_contents() == ["angry", "team", "urgency"]
    assert page.locator(".evidence .labels").count() == page.locator(".evidence li").count()
    assert page.locator(".kpi").count() == 4
    assert page.locator(".themes li").count() >= 3
    assert page.locator(".graph .node").count() >= 5
    assert page.locator(".bars li").count() > 0
    assert "%" in (page.text_content(".kpi:nth-child(3) strong") or "")
    assert visible_labels_do_not_overlap(page) >= 3


def test_demo_export_renders_and_is_interactive(
    static_site: str, open_page: Callable[..., Watched]
) -> None:
    w = open_page()
    page = w.page
    page.goto(f"{static_site}/demo/")
    assert_studio_renders(page, "Demo data")
    assert page.locator("form.ask").count() == 0
    assert page.locator(".graph .node.kind-source").count() == 6
    for selector in DEMO_ONLY:
        expect(page.locator(selector)).to_be_visible()
    expect(page.locator(".intro")).to_contain_text("144M-parameter decision model")
    rising = page.locator(".themes li.rising")
    assert rising.count() >= 1
    expect(rising.first.locator("strong")).to_have_text(re.compile(r"^Can't log in"))
    expect(rising.first.locator(".trend")).to_have_class(re.compile(r"\bup\b"))
    expect(page.locator(".privacy mark.pii", has_text="<EMAIL>")).to_be_visible()
    assert page.locator(".before-after li").count() == 3
    expect(page.locator(".before-after blockquote.raw").first).to_contain_text("@example.com")

    hints = page.locator(".intro .hints button")
    assert hints.count() == 3
    hints.nth(0).click()
    expect(page.locator(".evidence-panel h2")).to_have_text(re.compile(r"^Evidence: Can't log in"))
    hints.nth(1).click()
    expect(page.locator(".graph .node.kind-lang.pinned")).to_have_count(1)
    hints.nth(2).click()
    expect(page.locator(".evidence li.cited mark.pii")).not_to_have_count(0)

    citation = page.locator(".ask-examples button.cite").first
    cited = citation.text_content()
    citation.click()
    expect(page.locator(f'.evidence li.cited[data-id="{cited}"]')).to_be_visible()

    second = page.locator(".themes li").nth(1)
    second.click()
    title = second.locator("strong").text_content()
    expect(page.get_by_role("heading", name=f"Evidence: {title}")).to_be_visible()
    expect(page.locator(".themes li.selected")).to_have_count(1)
    expect(second).to_have_class(SELECTED)

    node = page.locator(".graph .node.kind-theme").last
    node.locator("circle").click()
    expect(node).to_have_class(SELECTED)
    expect(page.locator(".themes li.selected")).not_to_have_text(title or "")
    page.wait_for_selector(".evidence li")
    shoot(page, "demo-desktop")
    assert w.errors == []


def test_static_export_of_real_data_is_not_labelled_demo(
    static_site: str, open_page: Callable[..., Watched]
) -> None:
    w = open_page()
    w.page.goto(f"{static_site}/export/")
    assert_studio_renders(w.page, "Snapshot")
    for selector in DEMO_ONLY:
        assert w.page.locator(selector).count() == 0
    assert w.errors == []


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_colour_schemes_and_phone_width(
    static_site: str, open_page: Callable[..., Watched], scheme: Scheme
) -> None:
    w = open_page(viewport=NARROW, scheme=scheme)
    page = w.page
    page.goto(f"{static_site}/demo/")
    page.wait_for_selector(".evidence li")
    background = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert background == ("rgb(244, 249, 249)" if scheme == "light" else "rgb(15, 26, 29)")
    no_horizontal_overflow(page)
    labels = visible_labels_do_not_overlap(page)
    assert labels >= 1
    size = page.evaluate(
        "(() => { const t = [...document.querySelectorAll('.graph text')]"
        ".find(t => t.getAttribute('visibility') !== 'hidden');"
        " return t.getBoundingClientRect().height; })()"
    )
    assert size >= 9
    shoot(page, f"demo-390-{scheme}")
    assert w.errors == []


def test_live_analyst_sees_evidence_with_safe_links(
    live: str, open_page: Callable[..., Watched]
) -> None:
    w = open_page(token=ADMIN)
    page = w.page
    response = page.goto(f"{live}/studio/")
    assert response is not None
    headers = response.headers
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "script-src 'self'" in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["x-frame-options"] == "DENY"
    assert_studio_renders(page, "Live")
    assert page.locator("form.ask").count() == 1
    for selector in DEMO_ONLY:
        assert page.locator(selector).count() == 0
    expect(page.locator(".privacy")).to_contain_text("air-gapped")

    links = page.locator(".evidence a")
    assert links.count() > 0
    for i in range(links.count()):
        assert (links.nth(i).get_attribute("href") or "").startswith("https://example.com/")
        assert links.nth(i).get_attribute("rel") == "noopener noreferrer"
    assert page.locator('a[href^="javascript:"]').count() == 0
    assert UNSAFE_URL in page.locator(".evidence .url").all_text_contents()

    page.locator(".graph .node.kind-theme").first.locator("circle").click()
    page.wait_for_selector(".evidence li")
    shoot(page, "live-analyst")
    assert w.errors == []


def test_live_viewer_is_told_evidence_needs_analyst(
    live: str, open_page: Callable[..., Watched]
) -> None:
    w = open_page(token=VIEWER)
    page = w.page
    page.goto(f"{live}/studio/")
    page.wait_for_selector("text=Evidence needs the analyst role.")
    assert page.text_content(".badge") == "Live"
    expect(page.locator(".privacy")).to_be_visible()
    expect(page.locator(".decisions")).to_be_visible()
    assert page.get_by_role("link", name="obsei website").get_attribute("href") == (
        "https://obsei.com"
    )
    assert page.locator("form.ask").count() == 0
    assert page.locator(".evidence").count() == 0
    shoot(page, "live-viewer")
    assert w.errors == []


def test_live_wrong_token_says_invalid(live: str, open_page: Callable[..., Watched]) -> None:
    w = open_page()
    page = w.page
    page.goto(f"{live}/studio/")
    page.wait_for_selector("form.token")
    assert page.locator(".error").count() == 0
    page.fill("form.token input", "not-the-token")
    page.click("form.token button")
    page.wait_for_selector("text=Invalid token")
    shoot(page, "live-invalid-token")
    assert page.locator("form.token").count() == 1
    page.fill("form.token input", ADMIN)
    page.click("form.token button")
    page.wait_for_selector(".evidence li")
    unexpected = [e for e in w.errors if "401" not in e]
    assert unexpected == []
