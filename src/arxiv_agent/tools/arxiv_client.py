"""Tool for fetching papers from arxiv via its OAI-PMH interface."""

import logging
import random
import re
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from xml.etree import ElementTree

import httpx

from ..models import ArxivFetchResult, ArxivPaper

logger = logging.getLogger(__name__)

# arxiv's query API (export.arxiv.org/api/query) answers 429 "Rate exceeded"
# regardless of who asks or how slowly, so papers are harvested from OAI-PMH
# instead. Both interfaces share one policy: at most one request every three
# seconds over a single connection.
ARXIV_OAI_URL = "https://oaipmh.arxiv.org/oai"
ARXIV_USER_AGENT = "arxiv-agent/0.1 (+https://github.com/RedrumSherlock/arxiv-agent)"
MIN_REQUEST_INTERVAL = 3.0
RETRY_BASE_DELAY = 15.0
RETRY_MAX_DELAY = 600.0
DEFAULT_RETRY_BUDGET = 2700.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_PAGES_PER_SET = 60

OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/",
}

_last_request_at = 0.0


def fetch_arxiv_papers(
    topics: list[str],
    days_start: int,
    days_end: int,
    categories: list[str] | None = None,
    retry_budget: float = DEFAULT_RETRY_BUDGET,
) -> ArxivFetchResult:
    """
    Fetch papers submitted to the given arxiv categories within a time range.

    OAI-PMH selects by category and date, not by keyword, so the harvest is
    filtered against the topics locally on title and abstract.

    Args:
        topics: Search phrases; a paper is kept when any of them appears in its
            title or abstract. An empty list keeps every paper in the categories
        days_start: Start of range in days ago (e.g., 30 = from 30 days ago)
        days_end: End of range in days ago (e.g., 23 = to 23 days ago)
        categories: arxiv categories to harvest (e.g., ['cs.AI', 'cs.LG'])
        retry_budget: Total seconds to spend retrying failed requests, shared
            across all categories

    Returns:
        ArxivFetchResult with the papers submitted between days_start and
        days_end ago, plus the categories that could not be harvested.
    """
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days_start)
    end_date = today - timedelta(days=days_end)
    deadline = time.monotonic() + retry_budget

    logger.info(f"Date range: {start_date} to {end_date}")

    if not categories:
        logger.error("No arxiv categories configured; OAI-PMH harvesting needs at least one")
        return ArxivFetchResult(papers=[], total_sources=0, failed_sources=["(no categories)"])

    logger.info(f"Harvesting categories: {categories}")

    try:
        set_specs = _resolve_set_specs(categories, deadline)
    except httpx.HTTPError as e:
        logger.error(f"Could not list arxiv OAI sets: {_brief(e)}")
        return ArxivFetchResult(papers=[], total_sources=len(categories), failed_sources=categories)

    all_papers: dict[str, ArxivPaper] = {}
    failed_sources: list[str] = []

    for category in categories:
        set_spec = set_specs.get(category)
        if not set_spec:
            logger.error(f"Category '{category}': no matching OAI set")
            failed_sources.append(category)
            continue

        try:
            # Harvest up to today rather than end_date: OAI-PMH selects on last
            # modified date, so a paper submitted in the window but revised after
            # it would otherwise be invisible.
            papers = _harvest_set(set_spec, start_date, today, deadline)
        except httpx.HTTPError as e:
            logger.error(f"Category '{category}': harvest failed: {_brief(e)}")
            failed_sources.append(category)
            continue

        in_range = [p for p in papers if _submitted_in_window(p, start_date, end_date)]
        matching = [p for p in in_range if _matches_topics(p, topics)]
        logger.info(
            f"Category '{category}': {len(papers)} records, {len(in_range)} in date range, "
            f"{len(matching)} matching topics"
        )
        for paper in matching:
            all_papers[paper.arxiv_id] = paper

    result = list(all_papers.values())

    if result:
        dates = sorted([p.published for p in result])
        logger.info(f"Paper date range: {dates[0].date()} to {dates[-1].date()}")

    logger.info(f"Fetched {len(result)} unique papers from arxiv ({days_start} to {days_end} days ago)")
    return ArxivFetchResult(
        papers=result,
        total_sources=len(categories),
        failed_sources=failed_sources,
    )


def _resolve_set_specs(categories: list[str], deadline: float) -> dict[str, str]:
    """
    Map arxiv categories onto OAI set specs.

    Sets are named by group, e.g. 'cs.AI' lives at 'cs:cs:AI' and 'astro-ph.CO'
    at 'physics:astro-ph:CO', so the grouping is read off ListSets rather than
    guessed.
    """
    root = _oai_request({"verb": "ListSets"}, deadline)

    by_category: dict[str, str] = {}
    for spec_element in root.iter(f"{{{OAI_NS['oai']}}}setSpec"):
        spec = (spec_element.text or "").strip()
        parts = spec.split(":")
        if len(parts) == 3:
            by_category[f"{parts[1]}.{parts[2]}"] = spec
        elif len(parts) == 2:
            by_category.setdefault(parts[1], spec)

    return {c: by_category[c] for c in categories if c in by_category}


def _harvest_set(
    set_spec: str,
    from_date: date,
    until_date: date,
    deadline: float,
) -> list[ArxivPaper]:
    """Harvest every record in an OAI set, following resumption tokens."""
    params = {
        "verb": "ListRecords",
        "metadataPrefix": "arXiv",
        "set": set_spec,
        "from": from_date.isoformat(),
        "until": until_date.isoformat(),
    }
    papers: list[ArxivPaper] = []

    for page in range(MAX_PAGES_PER_SET):
        root = _oai_request(params, deadline)

        error = root.find("oai:error", OAI_NS)
        if error is not None:
            code = error.get("code", "")
            if code == "noRecordsMatch":
                break
            raise httpx.HTTPError(f"OAI error {code}: {(error.text or '').strip()}")

        for record in root.iter(f"{{{OAI_NS['oai']}}}record"):
            paper = _parse_record(record)
            if paper:
                papers.append(paper)

        token = root.find("oai:ListRecords/oai:resumptionToken", OAI_NS)
        if token is None or not (token.text or "").strip():
            break

        params = {"verb": "ListRecords", "resumptionToken": token.text.strip()}
    else:
        logger.warning(f"Set '{set_spec}': stopped at the {MAX_PAGES_PER_SET} page limit")

    return papers


def _parse_record(record: ElementTree.Element) -> ArxivPaper | None:
    """Parse one OAI record carrying arxiv metadata into an ArxivPaper."""
    meta = record.find("oai:metadata/arxiv:arXiv", OAI_NS)
    if meta is None:
        return None

    arxiv_id = _text(meta, "arxiv:id")
    title = _text(meta, "arxiv:title")
    if not arxiv_id or not title:
        return None

    created = _parse_date(_text(meta, "arxiv:created"))
    updated_text = _text(meta, "arxiv:updated")
    updated = _parse_date(updated_text) if updated_text else created

    authors = []
    for author in meta.findall("arxiv:authors/arxiv:author", OAI_NS):
        name = " ".join(
            part
            for part in (_text(author, "arxiv:forenames"), _text(author, "arxiv:keyname"))
            if part
        )
        if name:
            authors.append(name)

    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=_collapse(title),
        abstract=_collapse(_text(meta, "arxiv:abstract")),
        authors=authors,
        published=created,
        updated=updated,
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        categories=_text(meta, "arxiv:categories").split(),
    )


def _submitted_in_window(paper: ArxivPaper, start_date: date, end_date: date) -> bool:
    """
    Whether the paper was first submitted inside the window.

    A harvest returns revisions as well as new papers, and arxiv stamps a revised
    record with the revision date, so the date alone would let a years-old paper
    through. The identifier settles it: its YYMM prefix is the month arxiv
    announced the paper, so a prefix older than the stamped month means the record
    is a revision. The prefix can be one month later than the date when a paper
    submitted late in a month is announced in the next one.
    """
    submitted = paper.published.date()
    if not (start_date <= submitted <= end_date):
        return False

    match = re.fullmatch(r"(\d{2})(\d{2})\.\d{4,5}(v\d+)?", paper.arxiv_id)
    if not match:
        # Pre-2007 identifiers such as 'cs/0701001' cannot be new submissions.
        return False

    announced = (2000 + int(match.group(1))) * 12 + int(match.group(2))
    stamped = submitted.year * 12 + submitted.month
    return announced in (stamped, stamped + 1)


def _matches_topics(paper: ArxivPaper, topics: list[str]) -> bool:
    """Whether any topic phrase appears in the paper's title or abstract."""
    if not topics:
        return True
    haystack = f"{paper.title} {paper.abstract}".lower()
    return any(topic.strip().lower() in haystack for topic in topics if topic.strip())


def _oai_request(params: dict[str, str], deadline: float) -> ElementTree.Element:
    """Send one OAI-PMH request and return the parsed response root."""
    url = f"{ARXIV_OAI_URL}?{urlencode(params)}"
    logger.debug(f"OAI request: {params.get('verb')} {params.get('set', '')}")
    response = _get_with_retry(url, deadline)
    return ElementTree.fromstring(response.content)


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
                f"Giving up on arxiv after {attempt + 1} attempts, retry budget exhausted: "
                f"{_brief(last_error)}"
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


def _throttle() -> None:
    """Keep at least MIN_REQUEST_INTERVAL seconds between arxiv requests."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def _text(element: ElementTree.Element, path: str) -> str:
    """Stripped text of a child element, or an empty string when it is absent."""
    found = element.find(path, OAI_NS)
    return (found.text or "").strip() if found is not None else ""


def _collapse(text: str) -> str:
    """Collapse the newlines and padding arxiv wraps titles and abstracts in."""
    return re.sub(r"\s+", " ", text).strip()


def _brief(error: Exception) -> str:
    """First line of an exception, so retry logs stay to one line each."""
    return str(error).split("\n")[0]


def _parse_date(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD date from arxiv OAI metadata."""
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)
