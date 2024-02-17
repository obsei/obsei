from typing import Annotated, Any
from bson import ObjectId
from pydantic import BaseModel
from typing import List

from api.src.interfaces.pydantic_annotation import ObjectIdPydanticAnnotation


class ExecuteListeningOutData(BaseModel):
    id: Annotated[ObjectId, ObjectIdPydanticAnnotation]


