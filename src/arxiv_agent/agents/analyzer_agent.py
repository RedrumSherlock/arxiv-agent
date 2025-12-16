"""Agent for deep analysis of papers."""

import json
import logging
from pathlib import Path

from ..llm import chat_completion
from ..models import ArxivPaper, CommunityFeedback, PaperAnalysis, DigestItem

logger = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    """Load prompt from prompts directory."""
    prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / f"{name}.txt"
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""


ANALYZER_INSTRUCTION = _load_prompt("analyzer") or """You are a research paper analyst providing comprehensive paper analysis.

Your task is to analyze papers and provide:
1. A concise summary (under 100 words)
2. Author information with affiliations/organizations if identifiable
3. A final rating (1-100) with justification (under 100 words)
4. Community reputation summary (under 100 words)

Respond with a JSON object:
{
    "summary": "Concise summary of the paper",
    "authors_affiliations": "Authors with their affiliations",
    "rating": <integer 1-100>,
    "rating_justification": "Brief justification",
    "community_summary": "Summary of community reception"
}

Be thorough but concise. Focus on the most important insights."""


async def analyze_paper(
    model: str,
    paper: ArxivPaper,
    initial_score: int,
    community_feedback: CommunityFeedback,
    paper_content: str,
    acceptance_criteria: str,
) -> PaperAnalysis:
    """
    Perform deep analysis of a paper.
    
    Args:
        model: Model name to use
        paper: Paper to analyze
        initial_score: Score from initial scoring
        community_feedback: Gathered community feedback
        paper_content: Extracted paper content
        acceptance_criteria: Context for evaluation
        
    Returns:
        PaperAnalysis with comprehensive analysis
    """
    content_excerpt = paper_content[:15000] if paper_content else "Paper content not available."
    
    prompt = f"""Analyze this research paper comprehensively.

Evaluation Context: {acceptance_criteria}

Paper Title: {paper.title}

Authors: {', '.join(paper.authors)}

Abstract: {paper.abstract}

Categories: {', '.join(paper.categories)}

Initial Score: {initial_score}

Community Feedback:
{community_feedback.feedback_summary}

Paper Content (excerpt):
{content_excerpt}

Provide a comprehensive analysis. Respond with JSON only."""

    try:
        response = await chat_completion(model, ANALYZER_INSTRUCTION, prompt)
        result = _parse_analyzer_response(response)
        
        return PaperAnalysis(
            paper=paper,
            score=result.get("rating", initial_score),
            score_justification=result.get("rating_justification", ""),
            summary=result.get("summary", ""),
            authors_affiliations=result.get("authors_affiliations", ", ".join(paper.authors)),
            community_feedback=result.get("community_summary", community_feedback.feedback_summary),
            paper_content_summary=content_excerpt[:2000],
        )
    except Exception as e:
        logger.error(f"Failed to analyze paper {paper.arxiv_id}: {e}")
        return PaperAnalysis(
            paper=paper,
            score=initial_score,
            score_justification="Analysis failed",
            summary=paper.abstract[:200],
            authors_affiliations=", ".join(paper.authors),
            community_feedback=community_feedback.feedback_summary,
        )


def analysis_to_digest(analysis: PaperAnalysis) -> DigestItem:
    """Convert a PaperAnalysis to a DigestItem for notification."""
    return DigestItem(
        title=analysis.paper.title,
        summary=analysis.summary or analysis.paper.abstract[:300],
        authors=analysis.authors_affiliations,
        publish_date=analysis.paper.published.strftime("%Y-%m-%d"),
        rating=analysis.score,
        rating_justification=analysis.score_justification,
        community_reputation=analysis.community_feedback,
        arxiv_url=f"https://arxiv.org/abs/{analysis.paper.arxiv_id}",
    )


def _parse_analyzer_response(response: str) -> dict:
    """Parse the JSON response from the analyzer agent."""
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            if "rating" in data:
                data["rating"] = max(1, min(100, int(data["rating"])))
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return {}
