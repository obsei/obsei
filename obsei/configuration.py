import logging
import os
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field

from obsei.misc.utils import dict_to_object

logger = logging.getLogger(__name__)


class ObseiConfiguration(BaseModel):
    configuration: Optional[Dict[str, Any]] = None
    config_path: Optional[str] = Field(os.environ.get("obsei_config_path", None))
    config_filename: Optional[str] = Field(os.environ.get("obsei_config_filename", None))

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.configuration is None:
            self.configuration = yaml.load(
                open(f"{self.config_path}/{self.config_filename}", "r"),
                Loader=yaml.FullLoader,
            )
        logger.debug(f"Configuration: {self.configuration}")

    def initialize_instance(self, key_name: str = None):
        if (
            key_name is None
            or self.configuration is None
            or key_name not in self.configuration
            or not self.configuration[key_name]
        ):
            logger.warning(f"{key_name} not exist in configuration")
            return None
        return dict_to_object(self.configuration[key_name])
