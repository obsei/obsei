from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import HTTPException, Depends

from pydantic_settings import BaseSettings


class BasicAuthSetting(BaseSettings):
    user_basic_auth: str
    password_basic_auth: str


settings = BasicAuthSetting()
security = HTTPBasic()


def check_basic_authentication(
        credentials: HTTPBasicCredentials = Depends(security)
):
    if credentials.username != settings.user_basic_auth or credentials.password != settings.password_basic_auth:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
