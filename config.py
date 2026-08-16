from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    SECRET_KEY: str = "change-this-secret-key"
    DATABASE_URL: str = "sqlite:///eurotarde.db"
    ADMIN_DEFAULT_USERNAME: str = "admin"
    ADMIN_DEFAULT_PASSWORD: str = "change-this-admin-password"
    EUROMILLIONS_API_URL: str = "https://euromillions-api.com/api/v1"
    DRAW_UPDATE_HOUR: int = 0
    DRAW_UPDATE_MINUTE: int = 0
    SESSION_MAX_AGE: int = 3600

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
