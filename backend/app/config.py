"""Configuration management for the application."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Azure AI Foundry Configuration
    # Foundry endpoint format: https://<foundry-resource>.cognitiveservices.azure.com
    azure_foundry_endpoint: str
    azure_foundry_api_key: str
    azure_foundry_api_version: str = "2024-05-01-preview"
    azure_foundry_deployment_name: str
    
    # Application Configuration
    app_env: str = "development"
    log_level: str = "INFO"
    
    # Database Configuration
    database_url: str = "sqlite+aiosqlite:///./chatbot.db"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
