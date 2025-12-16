"""Tool for searching community feedback on papers."""

import logging

import httpx

from ..models import CommunityFeedback

logger = logging.getLogger(__name__)


def search_paper_feedback(paper_title: str, arxiv_id: str) -> CommunityFeedback:
    """
    Search for community feedback on a paper using web search.
    
    Args:
        paper_title: Title of the paper
        arxiv_id: Arxiv ID of the paper
        
    Returns:
        CommunityFeedback with gathered information
    """
    search_queries = [
        f"{paper_title} arxiv discussion",
        f"{arxiv_id} paper review",
        f"{paper_title} twitter",
    ]
    
    all_results = []
    sources = []
    
    for query in search_queries:
        results = _perform_search(query)
        all_results.extend(results)
        sources.extend([r.get("url", "") for r in results if r.get("url")])
    
    feedback_summary = _summarize_results(all_results) if all_results else "No community feedback found."
    
    return CommunityFeedback(
        paper_id=arxiv_id,
        feedback_summary=feedback_summary,
        sources=list(set(sources))[:5],
    )


def _perform_search(query: str) -> list[dict]:
    """
    Perform a web search. Returns mock results as placeholder.
    In production, integrate with actual search API (Google, Serper, etc.)
    """
    logger.info(f"Searching for: {query}")
    
    search_url = f"https://html.duckduckgo.com/html/?q={query}"
    
    try:
        response = httpx.get(
            search_url,
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ArxivAgent/1.0)"},
            follow_redirects=True,
        )
        if response.status_code == 200:
            return _parse_duckduckgo_html(response.text, query)
    except httpx.HTTPError as e:
        logger.warning(f"Search failed for '{query}': {e}")
    
    return []


def _parse_duckduckgo_html(html: str, query: str) -> list[dict]:
    """Parse DuckDuckGo HTML results (basic extraction)."""
    results = []
    
    import re
    link_pattern = re.compile(r'class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>')
    snippet_pattern = re.compile(r'class="result__snippet"[^>]*>([^<]*)</a>')
    
    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)
    
    for i, (url, title) in enumerate(links[:5]):
        snippet = snippets[i] if i < len(snippets) else ""
        if url and not url.startswith("/"):
            results.append({
                "title": title.strip(),
                "url": url,
                "snippet": snippet.strip(),
            })
    
    return results


def _summarize_results(results: list[dict]) -> str:
    """Summarize search results into a feedback string."""
    if not results:
        return "No community feedback found."
    
    summaries = []
    for r in results[:5]:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        if title or snippet:
            summaries.append(f"- {title}: {snippet}" if snippet else f"- {title}")
    
    return "\n".join(summaries) if summaries else "Limited community discussion found."

