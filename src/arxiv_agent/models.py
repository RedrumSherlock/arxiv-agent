"""Pydantic models for arxiv agent data structures."""

from datetime import datetime
from pydantic import BaseModel, Field


class ArxivPaper(BaseModel):
    """Raw paper data fetched from arxiv API."""
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published: datetime
    updated: datetime
    pdf_url: str
    categories: list[str]


class FilteredPaper(BaseModel):
    """Paper after initial filtering with relevance flag."""
    paper: ArxivPaper
    is_relevant: bool


class FilterResult(BaseModel):
    """Result of filtering papers including error tracking."""
    papers: list[FilteredPaper]
    total_batches: int
    failed_batches: int


class ScoredPaper(BaseModel):
    """Paper with relevance score."""
    paper: ArxivPaper
    score: int = Field(ge=0, le=100)
    score_justification: str = ""


class ScoreResult(BaseModel):
    """Result of scoring papers including error tracking."""
    papers: list[ScoredPaper]
    total_batches: int
    failed_batches: int


class CommunityFeedback(BaseModel):
    """Community feedback gathered from web search."""
    paper_id: str
    feedback_summary: str
    sources: list[str] = Field(default_factory=list)


class PaperAnalysis(BaseModel):
    """Full analysis of a paper combining all information."""
    paper: ArxivPaper
    score: int = Field(ge=0, le=100)
    score_justification: str
    summary: str
    authors_affiliations: str
    community_feedback: str
    paper_content_summary: str = ""


class DigestItem(BaseModel):
    """Final digest item ready for notification."""
    title: str
    summary: str
    authors: str
    publish_date: str
    rating: int
    rating_justification: str
    community_reputation: str
    arxiv_url: str


class NotificationResult(BaseModel):
    """Result of sending notification."""
    success: bool
    channel: str
    message: str = ""

