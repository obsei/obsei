from pydantic import BaseModel


class ResultData(BaseModel):
    ok: bool


class ResponseExecuteListening(BaseModel):
    status: bool
    message: str
