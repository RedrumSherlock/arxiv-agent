"""Configuration settings loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from .env file."""
    
    trace_back_days: int = Field(default=7, alias="TRACE_BACK_DAYS")
    search_topics: str = Field(default="machine learning", alias="SEARCH_TOPICS")
    acceptance_criteria: str = Field(
        default="Papers related to AI agents, LLM, or autonomous systems",
        alias="ACCEPTANCE_CRITERIA"
    )
    max_items: int = Field(default=5, alias="MAX_ITEMS")
    score_threshold: int = Field(default=50, alias="SCORE_THRESHOLD")
    
    openai_api_key_mini: str = Field(default="", alias="OPENAI_API_KEY_MINI")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    
    email_address_list: str = Field(default="", alias="EMAIL_ADDRESS_LIST")
    brevo_api_key: str = Field(default="", alias="BREVO_API_KEY")
    webhook_url: str = Field(default="", alias="WEBHOOK_URL")
    
    model_mini: str = Field(default="gemini-2.0-flash", alias="MODEL_MINI")
    model_full: str = Field(default="gemini-2.5-pro-preview-06-05", alias="MODEL_FULL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def email_list(self) -> list[str]:
        if not self.email_address_list:
            return []
        return [e.strip() for e in self.email_address_list.split(",") if e.strip()]

    @property
    def search_topic_list(self) -> list[str]:
        return [t.strip() for t in self.search_topics.split(",") if t.strip()]


def get_settings() -> Settings:
    return Settings()

