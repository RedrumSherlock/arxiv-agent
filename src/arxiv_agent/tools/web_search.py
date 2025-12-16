"""Tool for searching community feedback on papers using Tavily."""

import logging

import httpx

from ..models import CommunityFeedback

logger = logging.getLogger(__name__)

_tavily_api_key: str = ""


def init_tavily(api_key: str) -> None:
    """Initialize Tavily with API key."""
    global _tavily_api_key
    _tavily_api_key = api_key


def search_paper_feedback(paper_title: str, arxiv_id: str) -> CommunityFeedback:
    """
    Search for community feedback on a paper using Tavily.
    
    Args:
        paper_title: Title of the paper
        arxiv_id: Arxiv ID of the paper
        
    Returns:
        CommunityFeedback with gathered information
    """
    if not _tavily_api_key:
        logger.warning("Tavily API key not configured, skipping web search")
        return CommunityFeedback(
            paper_id=arxiv_id,
            feedback_summary="Web search not configured.",
            sources=[],
        )
    
    query = f"{paper_title} {arxiv_id} discussion review feedback"
    results = _tavily_search(query)
    
    if not results:
        return CommunityFeedback(
            paper_id=arxiv_id,
            feedback_summary="No community feedback found.",
            sources=[],
        )
    
    feedback_summary = _format_results(results)
    sources = [r.get("url", "") for r in results if r.get("url")]
    
    return CommunityFeedback(
        paper_id=arxiv_id,
        feedback_summary=feedback_summary,
        sources=sources[:5],
    )


def _tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Perform search using Tavily API."""
    logger.info(f"Tavily search: {query[:50]}...")
    
    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": _tavily_api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except httpx.HTTPError as e:
        logger.warning(f"Tavily search failed: {e}")
        return []


def _format_results(results: list[dict]) -> str:
    """Format Tavily results into a feedback summary."""
    summaries = []
    for r in results:
        title = r.get("title", "")
        content = r.get("content", "")[:200]
        if title or content:
            summaries.append(f"- {title}: {content}" if content else f"- {title}")
    
    return "\n".join(summaries) if summaries else "Limited community discussion found."
