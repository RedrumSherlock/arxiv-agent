"""Tool for fetching papers from arxiv API."""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser
import httpx

from ..models import ArxivPaper

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"


def fetch_arxiv_papers(
    topics: list[str],
    days_start: int,
    days_end: int,
    categories: list[str] | None = None,
) -> list[ArxivPaper]:
    """
    Fetch papers from arxiv API for given topics within the specified time range.
    
    Args:
        topics: List of search topics/keywords
        days_start: Start of range in days ago (e.g., 30 = from 30 days ago)
        days_end: End of range in days ago (e.g., 23 = to 23 days ago)
        categories: Optional list of arxiv categories to filter (e.g., ['cs.AI', 'cs.LG'])
        
    Returns:
        List of ArxivPaper objects published between days_start and days_end ago
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days_start)
    end_date = datetime.now(timezone.utc) - timedelta(days=days_end)
    
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    if categories:
        logger.info(f"Filtering by categories: {categories}")
    
    all_papers: dict[str, ArxivPaper] = {}
    
    for topic in topics:
        papers = _search_arxiv_with_date_range(topic, start_date, end_date, categories)
        logger.info(f"Topic '{topic}': {len(papers)} papers in date range")
        for paper in papers:
            all_papers[paper.arxiv_id] = paper
    
    result = list(all_papers.values())
    
    if result:
        dates = sorted([p.published for p in result])
        logger.info(f"Paper date range: {dates[0].date()} to {dates[-1].date()}")
    
    logger.info(f"Fetched {len(result)} unique papers from arxiv ({days_start} to {days_end} days ago)")
    return result


def _search_arxiv_with_date_range(
    query: str,
    start_date: datetime,
    end_date: datetime,
    categories: list[str] | None = None,
    batch_size: int = 200,
    max_batches: int = 10,
) -> list[ArxivPaper]:
    """Search arxiv with pagination until we find papers in the date range."""
    matching_papers = []
    offset = 0
    category_set = set(categories) if categories else None
    
    for batch_num in range(max_batches):
        papers = _search_arxiv(query, start=offset, max_results=batch_size)
        
        if not papers:
            break
        
        oldest_in_batch = min(p.published for p in papers)
        
        for paper in papers:
            if start_date <= paper.published <= end_date:
                if category_set is None or category_set.intersection(paper.categories):
                    matching_papers.append(paper)
        
        if oldest_in_batch < start_date:
            break
        
        offset += batch_size
    
    return matching_papers


def _search_arxiv(query: str, start: int = 0, max_results: int = 200) -> list[ArxivPaper]:
    """Search arxiv for papers matching the query."""
    encoded_query = quote(f'"{query}"')
    url = f"{ARXIV_API_URL}?search_query=all:{encoded_query}&start={start}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    
    logger.debug(f"Arxiv query: start={start}, max={max_results}")
    
    try:
        response = httpx.get(url, timeout=120.0)
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

