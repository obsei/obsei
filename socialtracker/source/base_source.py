from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from socialtracker.source.base_source_config import BaseSourceConfig


class SourceResponse:
    def __init__(
        self,
        text: str,
        meta_information: Optional[Dict[str, Any]] = None,
    ):
        self.text = text
        self.meta_information = meta_information


class BaseSource(ABC):

    @abstractmethod
    def lookup(self, config: BaseSourceConfig) -> List[SourceResponse]:
        pass
