from pydantic_settings import BaseSettings

from dotenv import load_dotenv
import os

# Load .env from the root folder
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=dotenv_path)


class Settings(BaseSettings):
    db_engine: str
    db_user: str
    db_password: str
    db_host: str
    db_port: str
    db_name: str
    redis_host: str
    user_basic_auth: str
    password_basic_auth: str

    class Config:
        env_file = dotenv_path
        env_file_encoding = "utf-8"
        ignore_extra = True
        extra = "allow"


