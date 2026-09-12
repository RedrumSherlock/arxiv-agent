"""Tool for fetching papers from arxiv API."""

import logging
import random
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser
import httpx

from ..models import ArxivFetchResult, ArxivPaper

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"

# arxiv asks API clients to identify themselves and to leave at least 3 seconds
# between requests. Their 429 "Rate exceeded" is a server-capacity signal rather
# than a per-client quota, so the only remedy is to wait and try again.
ARXIV_USER_AGENT = "arxiv-agent/0.1 (+https://github.com/RedrumSherlock/arxiv-agent)"
MIN_REQUEST_INTERVAL = 3.0
RETRY_BASE_DELAY = 15.0
RETRY_MAX_DELAY = 600.0
DEFAULT_RETRY_BUDGET = 2700.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_last_request_at = 0.0


def fetch_arxiv_papers(
    topics: list[str],
    days_start: int,
    days_end: int,
    categories: list[str] | None = None,
    retry_budget: float = DEFAULT_RETRY_BUDGET,
) -> ArxivFetchResult:
    """
    Fetch papers from arxiv API for given topics within the specified time range.

    Args:
        topics: List of search topics/keywords
        days_start: Start of range in days ago (e.g., 30 = from 30 days ago)
        days_end: End of range in days ago (e.g., 23 = to 23 days ago)
        categories: Optional list of arxiv categories to filter (e.g., ['cs.AI', 'cs.LG'])
        retry_budget: Total seconds to spend retrying rate-limited requests, shared
            across all topics

    Returns:
        ArxivFetchResult with the papers published between days_start and days_end
        ago, plus the topics whose queries failed.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days_start)
    end_date = datetime.now(timezone.utc) - timedelta(days=days_end)

    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    if categories:
        logger.info(f"Filtering by categories: {categories}")

    all_papers: dict[str, ArxivPaper] = {}
    failed_topics: list[str] = []
    deadline = time.monotonic() + retry_budget

    for topic in topics:
        try:
            papers = _search_arxiv_with_date_range(
                topic, start_date, end_date, categories, deadline
            )
        except httpx.HTTPError as e:
            logger.error(f"Topic '{topic}': arxiv query failed: {e}")
            failed_topics.append(topic)
            continue

        logger.info(f"Topic '{topic}': {len(papers)} papers in date range")
        for paper in papers:
            all_papers[paper.arxiv_id] = paper

    result = list(all_papers.values())

    if result:
        dates = sorted([p.published for p in result])
        logger.info(f"Paper date range: {dates[0].date()} to {dates[-1].date()}")

    logger.info(f"Fetched {len(result)} unique papers from arxiv ({days_start} to {days_end} days ago)")
    return ArxivFetchResult(
        papers=result,
        total_topics=len(topics),
        failed_topics=failed_topics,
    )


def _search_arxiv_with_date_range(
    query: str,
    start_date: datetime,
    end_date: datetime,
    categories: list[str] | None,
    deadline: float,
    batch_size: int = 200,
    max_batches: int = 10,
) -> list[ArxivPaper]:
    """Search arxiv with pagination until we find papers in the date range."""
    matching_papers = []
    offset = 0
    category_set = set(categories) if categories else None

    for batch_num in range(max_batches):
        papers = _search_arxiv(query, deadline, start=offset, max_results=batch_size)

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


def _search_arxiv(
    query: str, deadline: float, start: int = 0, max_results: int = 200
) -> list[ArxivPaper]:
    """Search arxiv for papers matching the query. Raises httpx.HTTPError on failure."""
    encoded_query = quote(f'"{query}"')
    url = f"{ARXIV_API_URL}?search_query=all:{encoded_query}&start={start}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"

    logger.debug(f"Arxiv query: start={start}, max={max_results}")

    response = _get_with_retry(url, deadline)
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


def _get_with_retry(url: str, deadline: float) -> httpx.Response:
    """
    GET a throttled arxiv URL, retrying rate limits and transient errors until the
    shared retry deadline runs out.
    """
    attempt = 0
    last_error: Exception

    while True:
        _throttle()
        try:
            response = httpx.get(
                url,
                timeout=120.0,
                headers={"User-Agent": ARXIV_USER_AGENT},
                follow_redirects=True,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in RETRYABLE_STATUS:
                raise
            last_error = e
            delay = _retry_delay(attempt, e.response.headers.get("Retry-After"))
        except httpx.HTTPError as e:
            last_error = e
            delay = _retry_delay(attempt, None)

        remaining = deadline - time.monotonic()
        if delay >= remaining:
            logger.error(
                f"Giving up on arxiv after {attempt + 1} attempts, retry budget exhausted: {last_error}"
            )
            raise last_error

        logger.warning(
            f"Arxiv request failed ({_brief(last_error)}); retrying in {delay:.0f}s, "
            f"{remaining / 60:.0f} min of retry budget left"
        )
        time.sleep(delay)
        attempt += 1


def _retry_delay(attempt: int, retry_after: str | None) -> float:
    """Delay before the next retry, honouring Retry-After when the server sends one."""
    if retry_after:
        try:
            return min(float(retry_after), RETRY_MAX_DELAY)
        except ValueError:
            pass
    backoff = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
    return backoff + random.uniform(0, backoff * 0.25)


def _brief(error: Exception) -> str:
    """First line of an exception, so retry logs stay to one line each."""
    return str(error).split("\n")[0]


def _throttle() -> None:
    """Keep at least MIN_REQUEST_INTERVAL seconds between arxiv requests."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


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
