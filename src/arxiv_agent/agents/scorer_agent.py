"""Agent for scoring papers based on relevance and quality."""

import json
import logging
from pathlib import Path

from google.adk.agents import LlmAgent

from ..models import ArxivPaper, ScoredPaper

logger = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    """Load prompt from prompts directory."""
    prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / f"{name}.txt"
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""


SCORER_INSTRUCTION = _load_prompt("scorer") or """You are a research paper scorer.
Your task is to score papers from 1-100 based on their relevance, novelty, and potential impact.

Consider:
- Relevance to the specified criteria
- Novelty of the approach or findings
- Potential impact on the field
- Quality of the abstract and methodology hints
- Author affiliations and track record (if apparent)

Respond with a JSON object:
{
    "score": <integer 1-100>,
    "justification": "Brief explanation of the score"
}

Be calibrated: 90+ is exceptional/groundbreaking, 70-89 is very good, 50-69 is decent, below 50 is low relevance."""


def create_scorer_agent(model: str) -> LlmAgent:
    """Create an agent for scoring papers."""
    return LlmAgent(
        name="paper_scorer",
        model=model,
        instruction=SCORER_INSTRUCTION,
    )


async def score_papers(
    agent: LlmAgent,
    papers: list[ArxivPaper],
    acceptance_criteria: str,
) -> list[ScoredPaper]:
    """
    Score papers using the LLM agent.
    
    Args:
        agent: The scorer LLM agent
        papers: List of papers to score
        acceptance_criteria: Criteria for evaluation context
        
    Returns:
        List of ScoredPaper objects sorted by score descending
    """
    results = []
    
    for paper in papers:
        prompt = f"""Evaluation Context: {acceptance_criteria}

Paper Title: {paper.title}

Paper Abstract: {paper.abstract}

Authors: {', '.join(paper.authors)}

Categories: {', '.join(paper.categories)}

Score this paper from 1-100. Respond with JSON only."""

        try:
            response = await agent.run_async(prompt)
            result = _parse_scorer_response(response)
            
            results.append(ScoredPaper(
                paper=paper,
                score=result.get("score", 50),
                score_justification=result.get("justification", ""),
            ))
        except Exception as e:
            logger.warning(f"Failed to score paper {paper.arxiv_id}: {e}")
            results.append(ScoredPaper(paper=paper, score=50))
    
    results.sort(key=lambda x: x.score, reverse=True)
    logger.info(f"Scored {len(results)} papers, top score: {results[0].score if results else 0}")
    
    return results


def _parse_scorer_response(response: str) -> dict:
    """Parse the JSON response from the scorer agent."""
    try:
        text = str(response)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            score = int(data.get("score", 50))
            score = max(1, min(100, score))
            return {"score": score, "justification": data.get("justification", "")}
    except (json.JSONDecodeError, ValueError):
        pass
    return {"score": 50, "justification": "Failed to parse response"}

