from abc import ABC
from typing import Any, Dict, Optional


class BaseStore(ABC):
    def get_source_state(self, id: str) -> Optional[Dict[str, Any]]:
        pass

    def update_source_state(self, workflow_id: str, state: Dict[str, Any]):
        pass
