"""
core/config.py — Application settings via pydantic-settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV:      str = 'development'
    APP_DEBUG:    bool = True
    DATABASE_URL: str = 'sqlite:///./dev.db'
    DJANGO_API_URL: str = 'http://localhost:8000'
    CORS_ORIGINS: str = 'http://localhost:3000'

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(',')]

    class Config:
        env_file = '.env'


settings = Settings()
