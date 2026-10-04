import os
import sys
import types
from collections.abc import Iterator

import pytest

from obsei.core.context import Context
from obsei.llm import EgressPolicy, LlmError
from obsei.llm.embed import LOCAL_MODEL, LocalEmbedder


class FakeVector:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


class FakeTextEmbedding:
    calls: list[dict[str, object]] = []  # noqa: RUF012

    def __init__(self, model_name: str, cache_dir: str | None, local_files_only: bool) -> None:
        if model_name == "missing":
            raise ValueError("not in cache")
        FakeTextEmbedding.calls.append(
            {"model": model_name, "cache_dir": cache_dir, "offline": local_files_only}
        )

    def embed(self, documents: list[str], batch_size: int) -> Iterator[FakeVector]:
        return (FakeVector([3.0, 4.0]) for _ in documents)


@pytest.fixture
def fake_fastembed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("fastembed")
    module.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fastembed", module)
    FakeTextEmbedding.calls.clear()


@pytest.mark.usefixtures("fake_fastembed")
def test_local_embedder_normalises_and_respects_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OBSEI_MODELS_DIR", "/models")
    embedder = Context(egress=EgressPolicy()).embedder("local")
    assert embedder.model == LOCAL_MODEL
    assert embedder.embed(["hola", "hello"]) == [[0.6, 0.8], [0.6, 0.8]]
    assert FakeTextEmbedding.calls == [
        {"model": LOCAL_MODEL, "cache_dir": "/models", "offline": True}
    ]
    Context(egress=EgressPolicy(mode="hybrid")).embedder("local:intfloat/multilingual-e5-large")
    assert FakeTextEmbedding.calls[-1]["offline"] is False


@pytest.mark.usefixtures("fake_fastembed")
def test_missing_offline_model_explains_download() -> None:
    with pytest.raises(LlmError, match="obsei models download"):
        LocalEmbedder("missing", offline=True)


def test_extra_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fastembed", None)
    with pytest.raises(LlmError, match=r"obsei\[embeddings\]"):
        LocalEmbedder(offline=False)


@pytest.mark.skipif(
    not os.environ.get("OBSEI_LIVE"), reason="set OBSEI_LIVE=1 to download the model"
)
def test_multilingual_model_groups_by_meaning() -> None:
    pytest.importorskip("fastembed")
    embedder = LocalEmbedder(offline=False)
    login_en, login_es, login_ja, refund_en = embedder.embed(
        [
            "I cannot log in to the app",
            "No puedo iniciar sesión en la app",
            "アプリにログインできません",
            "Please refund my double charge",
        ]
    )

    def cos(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cos(login_en, login_es) > cos(login_en, refund_en)
    assert cos(login_en, login_ja) > cos(login_en, refund_en)
