from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from obsei.source.base_source_config import BaseSourceConfig


class SourceResponse:
    def __init__(
        self,
        processed_text: str,
        meta_information: Optional[Dict[str, Any]] = None,
    ):
        self.processed_text = processed_text
        self.meta_information = meta_information


class BaseSource(ABC):

    @abstractmethod
    def lookup(self, config: BaseSourceConfig) -> List[SourceResponse]:
        pass
