"""Decision questions answered in process by zero-shot models (``pip install 'obsei[local]'``).

Each option (``"key: description"``) is scored as a natural-language-inference hypothesis about
the message; models with ``gliner2`` in their name run with GLiNER2 instead. In air-gapped mode the
models must already be in ``OBSEI_MODELS_DIR``: run ``obsei models download`` once with network.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import Protocol, TypeAlias, TypedDict

from obsei.llm.client import LlmError
from obsei.llm.decision import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)
from obsei.llm.embed import MODELS_DIR_ENV

LOCAL_CLASSIFIER = "MoritzLaurer/bge-m3-zeroshot-v2.0"
HYPOTHESIS = "This customer message is {}"
INSTALL_HINT = "local classification needs: pip install 'obsei[local]'"

Options: TypeAlias = Mapping[str, str | None]
Scorer: TypeAlias = Callable[[str, Options], dict[str, float]]


class _NliResult(TypedDict):
    labels: list[str]
    scores: list[float]


class _Nli(Protocol):
    def __call__(
        self, text: str, labels: list[str], *, hypothesis_template: str, multi_label: bool
    ) -> _NliResult: ...


class _Label(TypedDict):
    label: str
    confidence: float


class _Gliner2(Protocol):
    def classify_text(
        self, text: str, tasks: dict[str, object], *, include_confidence: bool
    ) -> dict[str, list[_Label]]: ...


def fetch(model: str, *, offline: bool, cache_dir: str | None = None) -> str:
    """A local directory as is, else the Hugging Face snapshot in ``OBSEI_MODELS_DIR``."""
    local = Path(model).expanduser()
    if local.is_dir():
        return str(local)
    try:
        from huggingface_hub import snapshot_download  # noqa: PLC0415
    except ImportError:
        raise LlmError(INSTALL_HINT) from None
    try:
        path: str = snapshot_download(
            model, cache_dir=cache_dir or os.environ.get(MODELS_DIR_ENV), local_files_only=offline
        )
    except (OSError, ValueError) as exc:
        hint = f"; download it first with: obsei models download --classifier {model}"
        raise LlmError(f"cannot load model {model!r}: {exc}{hint if offline else ''}") from None
    return path


def _nli(path: str) -> Scorer:
    from transformers import pipeline  # noqa: PLC0415

    classify: _Nli = pipeline("zero-shot-classification", model=path, device=-1)

    def score(text: str, options: Options) -> dict[str, float]:
        hypotheses = {f"{k}: {v}" if v else k: k for k, v in options.items()}
        out = classify(text, list(hypotheses), hypothesis_template=HYPOTHESIS, multi_label=False)
        return {hypotheses[h]: float(p) for h, p in zip(out["labels"], out["scores"], strict=True)}

    return score


def _gliner2(path: str) -> Scorer:
    from gliner2 import GLiNER2  # noqa: PLC0415

    model: _Gliner2 = GLiNER2.from_pretrained(path)

    def score(text: str, options: Options) -> dict[str, float]:
        task = {
            "labels": {k: v or k for k, v in options.items()},
            "multi_label": True,
            "cls_threshold": 0.0,
            "class_act": "softmax",
        }
        out = model.classify_text(text, {"q": task}, include_confidence=True)["q"]
        return {o["label"]: float(o["confidence"]) for o in out}

    return score


@lru_cache(maxsize=4)
def load(model: str, offline: bool) -> Scorer:
    path = fetch(model, offline=offline)
    try:
        return _gliner2(path) if "gliner2" in model.casefold() else _nli(path)
    except ImportError:
        raise LlmError(INSTALL_HINT) from None
    except (OSError, ValueError, RuntimeError) as exc:
        raise LlmError(f"cannot load model {model!r}: {exc}") from None


class LocalDecider:
    """Answers choice and score questions with ``model``, or the model ``models`` names for a
    question. Confidence is the top probability."""

    def __init__(
        self, model: str = LOCAL_CLASSIFIER, *, models: Mapping[str, str], offline: bool
    ) -> None:
        self._model = model
        self.models = dict(models)
        self.scorers = {m: load(m, offline) for m in {model, *self.models.values()}}

    @property
    def model(self) -> str:
        return ", ".join([self._model, *(f"{q}: {m}" for q, m in self.models.items())])

    def decide(self, state: str, questions: Mapping[str, Question]) -> dict[str, Answer]:
        return {name: self._answer(state, name, q) for name, q in questions.items()}

    def _answer(self, text: str, name: str, question: Question) -> Answer:
        score = self.scorers[self.models.get(name, self._model)]
        if isinstance(question, ChoiceQuestion):
            p = score(text, question.criteria)
            best = max(p, key=p.__getitem__)
            return ChoiceAnswer(type="choice", choice=best, probabilities=p, confidence=p[best])
        if isinstance(question, ScoreQuestion):
            levels = question.criteria
            p = score(text, dict.fromkeys(levels, question.instructions))
            expected = sum(i * p[level] for i, level in enumerate(levels))
            return ScoreAnswer(
                type="score",
                score=expected,
                probabilities=p,
                confidence=max(p.values()),
                label=levels[round(expected)],
            )
        raise LlmError(f"{name!r}: local models answer yes/no only with yes_means and no_means")
