"""obsei: privacy-first, self-hosted, AI-native Voice of Customer."""

from obsei._version import __version__
from obsei.core.record import Author, Enrichment, Record, SourceRef

__all__ = ["Author", "Enrichment", "Record", "SourceRef", "__version__"]
