"""Agent for filtering papers based on relevance criteria."""

import json
import logging
from pathlib import Path

from google.adk.agents import LlmAgent

from ..models import ArxivPaper, FilteredPaper

logger = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    """Load prompt from prompts directory."""
    prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / f"{name}.txt"
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""


FILTER_INSTRUCTION = _load_prompt("filter") or """You are a research paper relevance filter. 
Your task is to determine if a paper is relevant based on the given acceptance criteria.

For each paper, analyze the title and abstract, then respond with a JSON object:
{
    "is_relevant": true/false,
    "reason": "Brief explanation of your decision"
}

Be conservative - if there's a reasonable chance the paper is relevant, mark it as relevant.
Only filter out papers that are clearly outside the acceptance criteria."""


def create_filter_agent(model: str) -> LlmAgent:
    """Create an agent for filtering papers by relevance."""
    return LlmAgent(
        name="paper_filter",
        model=model,
        instruction=FILTER_INSTRUCTION,
    )


async def filter_papers(
    agent: LlmAgent,
    papers: list[ArxivPaper],
    acceptance_criteria: str,
) -> list[FilteredPaper]:
    """
    Filter papers based on acceptance criteria using the LLM agent.
    
    Args:
        agent: The filter LLM agent
        papers: List of papers to filter
        acceptance_criteria: Criteria for accepting papers
        
    Returns:
        List of FilteredPaper objects with relevance flags
    """
    results = []
    
    for paper in papers:
        prompt = f"""Acceptance Criteria: {acceptance_criteria}

Paper Title: {paper.title}

Paper Abstract: {paper.abstract}

Categories: {', '.join(paper.categories)}

Determine if this paper is relevant. Respond with JSON only."""

        try:
            response = await agent.run_async(prompt)
            result = _parse_filter_response(response)
            
            results.append(FilteredPaper(
                paper=paper,
                is_relevant=result.get("is_relevant", True),
                filter_reason=result.get("reason", ""),
            ))
        except Exception as e:
            logger.warning(f"Failed to filter paper {paper.arxiv_id}: {e}")
            results.append(FilteredPaper(paper=paper, is_relevant=True))
    
    relevant_count = sum(1 for r in results if r.is_relevant)
    logger.info(f"Filtered {len(papers)} papers, {relevant_count} marked as relevant")
    
    return results


def _parse_filter_response(response: str) -> dict:
    """Parse the JSON response from the filter agent."""
    try:
        text = str(response)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {"is_relevant": True, "reason": "Failed to parse response"}

