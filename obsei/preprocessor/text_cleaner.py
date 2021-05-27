import logging
from typing import Any, Dict, List, Optional

from pydantic import PrivateAttr


from obsei.preprocessor.base_text_cleaner import (
    TextCleanerRequest,
    TextCleanerResponse,
    BaseTextCleaner,
    BaseTextCleanerConfig,
)

logger = logging.getLogger(__name__)


class TextCleaner(BaseTextCleaner):

    def __init__(self, **data: Any):
        super().__init__(**data)

    def clean_input(
        self,
        input_list: List[TextCleanerRequest],
        config: BaseTextCleanerConfig,
        **kwargs
    ) -> List[TextCleanerResponse]:
        pass