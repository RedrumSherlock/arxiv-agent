"""Agent for filtering papers based on relevance criteria."""

import json
import logging
from pathlib import Path

from ..llm import chat_completion
from ..models import ArxivPaper, FilteredPaper, FilterResult

logger = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    """Load prompt from prompts directory."""
    prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / f"{name}.txt"
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""


FILTER_INSTRUCTION = _load_prompt("filter") or """You are a research paper relevance filter.
Determine which papers are relevant based on the acceptance criteria.

For each paper, respond with a JSON array of objects:
[{"id": "paper_id", "is_relevant": true/false}, ...]

Only filter out papers clearly outside the acceptance criteria."""


async def filter_papers(
    model: str,
    papers: list[ArxivPaper],
    acceptance_criteria: str,
    batch_size: int = 10,
) -> FilterResult:
    """
    Filter papers based on acceptance criteria using the LLM in batches.

    Args:
        model: Model name to use
        papers: List of papers to filter
        acceptance_criteria: Criteria for accepting papers
        batch_size: Number of papers to process per LLM call

    Returns:
        FilterResult with filtered papers and error tracking
    """
    results = []
    paper_map = {p.arxiv_id: p for p in papers}
    total_batches = (len(papers) + batch_size - 1) // batch_size
    failed_batches = 0

    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        logger.info(f"Filtering batch {batch_num}/{total_batches} ({len(batch)} papers)")
        batch_results, batch_failed = await _filter_batch(model, batch, acceptance_criteria)

        if batch_failed:
            failed_batches += 1

        for arxiv_id, is_relevant in batch_results.items():
            if arxiv_id in paper_map:
                results.append(FilteredPaper(
                    paper=paper_map[arxiv_id],
                    is_relevant=is_relevant,
                ))

        for paper in batch:
            if paper.arxiv_id not in batch_results:
                results.append(FilteredPaper(paper=paper, is_relevant=True))

    relevant_count = sum(1 for r in results if r.is_relevant)
    logger.info(f"Filtered {len(papers)} papers, {relevant_count} marked as relevant")

    return FilterResult(
        papers=results,
        total_batches=total_batches,
        failed_batches=failed_batches,
    )


async def _filter_batch(
    model: str,
    papers: list[ArxivPaper],
    acceptance_criteria: str,
) -> tuple[dict[str, bool], bool]:
    """Filter a batch of papers and return relevance map with error flag."""
    papers_text = []
    for idx, paper in enumerate(papers):
        papers_text.append(f"""Paper {idx + 1}:
ID: {paper.arxiv_id}
Title: {paper.title}
Abstract: {paper.abstract}
Categories: {', '.join(paper.categories)}
""")

    prompt = f"""Acceptance Criteria: {acceptance_criteria}

Review the following {len(papers)} papers and determine which are relevant.

{chr(10).join(papers_text)}

Respond with a JSON array only:
[{{"id": "arxiv_id", "is_relevant": true/false}}, ...]"""

    try:
        response = await chat_completion(model, FILTER_INSTRUCTION, prompt)
        return _parse_batch_response(response, papers), False
    except Exception as e:
        logger.warning(f"Failed to filter batch: {e}")
        return {p.arxiv_id: True for p in papers}, True


def _parse_batch_response(response: str, papers: list[ArxivPaper]) -> dict[str, bool]:
    """Parse the JSON array response from batch filtering."""
    try:
        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            return {item["id"]: item.get("is_relevant", True) for item in data}
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"Failed to parse batch response: {e}")
    
    return {p.arxiv_id: True for p in papers}
