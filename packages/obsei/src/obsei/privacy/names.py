"""Person-name redaction with a multilingual entity model (``pip install 'obsei[names]'``).

Regex detectors cannot find names, so this runs a local GLiNER model after the regex pass. In
air-gapped mode the model must already be on disk: download it once and point ``model`` at the
directory. Names are replaced with ``<PERSON>``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Protocol, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.record import Record
from obsei.llm.egress import EgressPolicy
from obsei.privacy.redact import RegexRedactor, Region

DEFAULT_MODEL = "urchade/gliner_multi_pii-v1"
LABEL = "PERSON"
MAX_CHUNK = 800
_SENTENCE = re.compile(r"(?<=[.!?\u3002\uff01\uff1f\n])\s*")


class NamesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    model: str = Field(
        default=DEFAULT_MODEL, description="Hugging Face id, or a local directory (air-gapped)."
    )
    threshold: float = Field(default=0.5, gt=0, lt=1)
    labels: list[str] = Field(default_factory=lambda: ["person"])


class Span(TypedDict):
    start: int
    end: int


class _Model(Protocol):
    def predict_entities(self, text: str, labels: list[str], threshold: float) -> list[Span]: ...


class NameDetector(Protocol):
    def detect(self, text: str) -> list[Span]: ...


class NameRedactionError(RuntimeError):
    pass


def chunks(text: str, size: int = MAX_CHUNK) -> list[tuple[int, str]]:
    """Split on sentence ends into pieces of at most ``size`` characters, with their offsets."""
    pieces: list[tuple[int, str]] = []
    start = 0
    current = 0
    for match in _SENTENCE.finditer(text):
        end = match.end()
        if end - start > size and current > start:
            pieces.append((start, text[start:current]))
            start = current
        current = end
    if start < len(text):
        tail = text[start:]
        pieces.extend((start + i, tail[i : i + size]) for i in range(0, len(tail), size))
    return [(offset, piece) for offset, piece in pieces if piece.strip()]


class GlinerDetector:
    def __init__(self, config: NamesConfig, egress: EgressPolicy) -> None:
        local = Path(config.model).expanduser()
        if not local.exists() and egress.mode == "air_gapped":
            raise NameRedactionError(
                f"model {config.model!r} is not on disk and egress is air-gapped; download it "
                "once (huggingface-cli download <model> --local-dir <dir>) and set names.model "
                "to that directory"
            )
        try:
            from gliner import GLiNER  # noqa: PLC0415
        except ImportError:
            raise NameRedactionError("name redaction needs: pip install 'obsei[names]'") from None
        self.model: _Model = GLiNER.from_pretrained(str(local) if local.exists() else config.model)
        self.labels = list(config.labels)
        self.threshold = config.threshold

    def detect(self, text: str) -> list[Span]:
        spans: list[Span] = []
        for offset, piece in chunks(text):
            for entity in self.model.predict_entities(piece, self.labels, threshold=self.threshold):
                spans.append(
                    {"start": offset + int(entity["start"]), "end": offset + int(entity["end"])}
                )
        return spans


def mask(text: str, spans: Sequence[Span]) -> str:
    merged: list[Span] = []
    for span in sorted(spans, key=lambda s: s["start"]):
        if merged and span["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], span["end"])
        else:
            merged.append({"start": span["start"], "end": span["end"]})
    for span in reversed(merged):
        text = f"{text[: span['start']]}<{LABEL}>{text[span['end'] :]}"
    return text


class NameRedactor:
    def __init__(self, detector: NameDetector) -> None:
        self.detector = detector

    def _text(self, text: str) -> str:
        return mask(text, self.detector.detect(text)) if text.strip() else text

    def redact(self, batch: Sequence[Record]) -> list[Record]:
        return [
            r.model_copy(
                update={
                    "text": self._text(r.text),
                    "context": {k: self._text(v) for k, v in r.context.items()},
                }
            )
            for r in batch
        ]


class BatchRedactor(Protocol):
    def redact(self, batch: Sequence[Record]) -> Sequence[Record]: ...


class ChainRedactor:
    def __init__(self, *redactors: BatchRedactor) -> None:
        self.redactors = redactors

    def redact(self, batch: Sequence[Record]) -> list[Record]:
        records = list(batch)
        for redactor in self.redactors:
            records = list(redactor.redact(records))
        return records


@lru_cache(maxsize=4)
def _detector(
    model: str, threshold: float, labels: tuple[str, ...], egress: EgressPolicy
) -> GlinerDetector:
    return GlinerDetector(
        NamesConfig(enabled=True, model=model, threshold=threshold, labels=list(labels)), egress
    )


def redactor_for(
    regions: Iterable[Region], names: NamesConfig, egress: EgressPolicy
) -> BatchRedactor:
    """Regex redaction, followed by name redaction when enabled (the model loads once)."""
    regex = RegexRedactor(regions)
    if not names.enabled:
        return regex
    detector = _detector(names.model, names.threshold, tuple(names.labels), egress)
    return ChainRedactor(regex, NameRedactor(detector))
