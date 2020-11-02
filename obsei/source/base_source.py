from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from obsei.source.base_source_config import BaseSourceConfig


class SourceResponse:
    def __init__(
        self,
        processed_text: str,
        source_name: str,
        meta: Optional[Dict[str, Any]] = None,
    ):
        self.processed_text = processed_text
        self.meta = meta
        self.source_name = source_name


class BaseSource(ABC):

    @abstractmethod
    def lookup(self, config: BaseSourceConfig) -> List[SourceResponse]:
        pass
