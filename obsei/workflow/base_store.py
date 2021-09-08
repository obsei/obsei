from abc import abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseSettings


class BaseStore(BaseSettings):
    @abstractmethod
    def get_source_state(self, id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_sink_state(self, id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_analyzer_state(self, id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_source_state(self, workflow_id: str, state: Dict[str, Any]):
        pass

    @abstractmethod
    def update_sink_state(self, workflow_id: str, state: Dict[str, Any]):
        pass

    @abstractmethod
    def update_analyzer_state(self, workflow_id: str, state: Dict[str, Any]):
        pass

    @abstractmethod
    def delete_workflow(self, id: str):
        pass
