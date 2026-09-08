from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import json


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/chargeease"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/chargeease"

    # JWT
    JWT_SECRET_KEY: str = "CHANGE-ME-TO-A-RANDOM-SECRET-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # MQTT (future)
    MQTT_BROKER_URL: Optional[str] = None
    MQTT_BROKER_PORT: int = 1883

    # Redis (optional)
    REDIS_URL: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DEBUG: bool = True

    # Telemetry validation
    TELEMETRY_MAX_FUTURE_SECONDS: int = 60
    TELEMETRY_MAX_SPEED_KPH: float = 200.0
    TELEMETRY_POOR_GPS_ACCURACY_M: float = 50.0

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}


settings = Settings()
