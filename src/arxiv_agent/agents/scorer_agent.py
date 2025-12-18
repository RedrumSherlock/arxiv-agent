"""Agent for scoring papers based on relevance and quality."""

import json
import logging
from pathlib import Path

from ..llm import chat_completion
from ..models import ArxivPaper, ScoredPaper

logger = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    """Load prompt from prompts directory."""
    prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / f"{name}.txt"
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""


SCORER_INSTRUCTION = _load_prompt("scorer") or """You are a research paper scorer.
Score each paper from 1-100 based on relevance, novelty, and potential impact.

For each paper, respond with a JSON array:
[{"id": "arxiv_id", "score": 1-100, "justification": "brief reason"}, ...]

Be calibrated: 90+ exceptional, 70-89 very good, 50-69 decent, below 50 low relevance."""


async def score_papers(
    model: str,
    papers: list[ArxivPaper],
    acceptance_criteria: str,
    batch_size: int = 10,
) -> list[ScoredPaper]:
    """
    Score papers using the LLM in batches.
    
    Args:
        model: Model name to use
        papers: List of papers to score
        acceptance_criteria: Criteria for evaluation context
        batch_size: Number of papers to process per LLM call
        
    Returns:
        List of ScoredPaper objects sorted by score descending
    """
    results = []
    paper_map = {p.arxiv_id: p for p in papers}
    
    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(papers) + batch_size - 1) // batch_size
        logger.info(f"Scoring batch {batch_num}/{total_batches} ({len(batch)} papers)")
        
        batch_results = await _score_batch(model, batch, acceptance_criteria)
        
        for arxiv_id, score_data in batch_results.items():
            if arxiv_id in paper_map:
                results.append(ScoredPaper(
                    paper=paper_map[arxiv_id],
                    score=score_data["score"],
                    score_justification=score_data["justification"],
                ))
        
        for paper in batch:
            if paper.arxiv_id not in batch_results:
                results.append(ScoredPaper(paper=paper, score=50))
    
    results.sort(key=lambda x: x.score, reverse=True)
    logger.info(f"Scored {len(results)} papers, top score: {results[0].score if results else 0}")
    
    return results


async def _score_batch(
    model: str,
    papers: list[ArxivPaper],
    acceptance_criteria: str,
) -> dict[str, dict]:
    """Score a batch of papers and return scores map."""
    papers_text = []
    for idx, paper in enumerate(papers):
        papers_text.append(f"""Paper {idx + 1}:
ID: {paper.arxiv_id}
Title: {paper.title}
Abstract: {paper.abstract}
Authors: {', '.join(paper.authors)}
Categories: {', '.join(paper.categories)}
""")
    
    prompt = f"""Evaluation Context: {acceptance_criteria}

Score the following {len(papers)} papers from 1-100.

{chr(10).join(papers_text)}

Respond with a JSON array only:
[{{"id": "arxiv_id", "score": 1-100, "justification": "brief reason"}}, ...]"""

    try:
        response = await chat_completion(model, SCORER_INSTRUCTION, prompt)
        return _parse_batch_response(response, papers)
    except Exception as e:
        logger.warning(f"Failed to score batch: {e}")
        return {p.arxiv_id: {"score": 50, "justification": ""} for p in papers}


def _parse_batch_response(response: str, papers: list[ArxivPaper]) -> dict[str, dict]:
    """Parse the JSON array response from batch scoring."""
    try:
        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            result = {}
            for item in data:
                score = max(1, min(100, int(item.get("score", 50))))
                result[item["id"]] = {
                    "score": score,
                    "justification": item.get("justification", ""),
                }
            return result
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"Failed to parse batch response: {e}")
    
    return {p.arxiv_id: {"score": 50, "justification": ""} for p in papers}
