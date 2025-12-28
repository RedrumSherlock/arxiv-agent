"""Configuration settings loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from .env file."""
    
    trace_back_days_start: int = Field(default=30, alias="TRACE_BACK_DAYS_START")
    trace_back_days_end: int = Field(default=23, alias="TRACE_BACK_DAYS_END")
    search_topics: str = Field(default="machine learning", alias="SEARCH_TOPICS")
    arxiv_categories: str = Field(default="cs.AI,cs.LG, cs.CL", alias="ARXIV_CATEGORIES")
    acceptance_criteria: str = Field(
        default="Papers related to AI agents, LLM, or autonomous systems",
        alias="ACCEPTANCE_CRITERIA"
    )
    max_items: int = Field(default=5, alias="MAX_ITEMS")
    score_threshold: int = Field(default=50, alias="SCORE_THRESHOLD")
    filter_batch_size: int = Field(default=10, alias="FILTER_BATCH_SIZE")
    scorer_batch_size: int = Field(default=10, alias="SCORER_BATCH_SIZE")
    
    # LLM API Configuration (OpenAI-compatible: Azure OpenAI, LiteLLM, etc.)
    api_key: str = Field(default="", alias="API_KEY")
    api_endpoint: str = Field(default="", alias="API_ENDPOINT")
    
    # Tavily API for web search
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    
    email_address_list: str = Field(default="", alias="EMAIL_ADDRESS_LIST")
    brevo_api_key: str = Field(default="", alias="BREVO_API_KEY")
    brevo_sender_email: str = Field(default="", alias="BREVO_SENDER_EMAIL")
    brevo_sender_name: str = Field(default="Arxiv Agent", alias="BREVO_SENDER_NAME")
    webhook_url: str = Field(default="", alias="WEBHOOK_URL")
    
    model_filter: str = Field(default="gemini-2.5-flash", alias="MODEL_FILTER")
    model_scorer: str = Field(default="gemini-2.5-flash", alias="MODEL_SCORER")
    model_analyzer: str = Field(default="gemini-2.5-pro", alias="MODEL_ANALYZER")
    
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

    @property
    def arxiv_category_list(self) -> list[str]:
        if not self.arxiv_categories:
            return []
        return [c.strip() for c in self.arxiv_categories.split(",") if c.strip()]


def get_settings() -> Settings:
    return Settings()
