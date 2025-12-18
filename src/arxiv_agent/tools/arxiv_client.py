"""Tool for fetching papers from arxiv API."""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser
import httpx

from ..models import ArxivPaper

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"


def fetch_arxiv_papers(topics: list[str], days_back: int) -> list[ArxivPaper]:
    """
    Fetch papers from arxiv API for given topics within the specified time range.
    
    Args:
        topics: List of search topics/keywords
        days_back: Number of days to look back
        
    Returns:
        List of ArxivPaper objects
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    all_papers: dict[str, ArxivPaper] = {}
    
    for topic in topics:
        papers = _search_arxiv(topic, max_results=100)
        for paper in papers:
            if paper.published >= cutoff_date:
                all_papers[paper.arxiv_id] = paper
    
    result = list(all_papers.values())
    logger.info(f"Fetched {len(result)} unique papers from arxiv")
    return result


def _search_arxiv(query: str, max_results: int = 100) -> list[ArxivPaper]:
    """Search arxiv for papers matching the query."""
    encoded_query = quote(query)
    url = f"{ARXIV_API_URL}?search_query=all:{encoded_query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    
    try:
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch from arxiv: {e}")
        return []
    
    feed = feedparser.parse(response.text)
    papers = []
    
    for entry in feed.entries:
        try:
            paper = _parse_entry(entry)
            if paper:
                papers.append(paper)
        except Exception as e:
            logger.warning(f"Failed to parse entry: {e}")
            continue
    
    return papers


def _parse_entry(entry: dict) -> ArxivPaper | None:
    """Parse a feedparser entry into an ArxivPaper object."""
    arxiv_id = entry.get("id", "").split("/abs/")[-1]
    if not arxiv_id:
        return None
    
    title = entry.get("title", "").replace("\n", " ").strip()
    abstract = entry.get("summary", "").replace("\n", " ").strip()
    
    authors = [author.get("name", "") for author in entry.get("authors", [])]
    
    published = _parse_date(entry.get("published", ""))
    updated = _parse_date(entry.get("updated", ""))
    
    pdf_url = ""
    for link in entry.get("links", []):
        if link.get("type") == "application/pdf":
            pdf_url = link.get("href", "")
            break
    
    if not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    
    categories = []
    for tag in entry.get("tags", []):
        term = tag.get("term", "")
        if term:
            categories.append(term)
    
    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        published=published,
        updated=updated,
        pdf_url=pdf_url,
        categories=categories,
    )


def _parse_date(date_str: str) -> datetime:
    """Parse date string from arxiv feed."""
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)

