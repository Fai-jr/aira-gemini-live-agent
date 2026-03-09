from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "AIRA"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/aira_db"
    DATABASE_URL_SYNC: str = "postgresql://postgres:password@localhost:5432/aira_db"

    # Google AI
    GOOGLE_API_KEY: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_REGION: str = "us-central1"

    # Gemini Models
    GEMINI_LIVE_MODEL: str = "gemini-2.0-flash-exp"
    GEMINI_VISION_MODEL: str = "gemini-2.0-flash"

    # CORS - stored as comma-separated string in .env
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:8081"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    def get_allowed_origins(self) -> List[str]:
        origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]
        extra = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://localhost:8081",
        ]
        return list(set(origins + extra))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
