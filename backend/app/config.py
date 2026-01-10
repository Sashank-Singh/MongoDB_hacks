"""
Configuration settings for Agent OS
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "agent_os"
    
    # Fireworks AI (matches .env FIREWORK_API)
    FIREWORK_API: str = "fw_EznkTLP5DfZ32X7HSYWpgG"
    FIREWORKS_BASE_URL: str = "https://api.fireworks.ai/inference/v1"
    FIREWORKS_MODEL: str = "accounts/fireworks/models/deepseek-v3p2"
    
    # Legacy OpenAI (ignored but allowed in .env)
    OPENAI_API_KEY: Optional[str] = None
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # Redis (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
