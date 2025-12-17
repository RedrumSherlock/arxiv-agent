"""Main workflow orchestrator for the arxiv agent."""

import logging

from .config import Settings
from .models import DigestItem, NotificationResult
from .tools import (
    fetch_arxiv_papers,
    search_paper_feedback,
    download_and_extract_paper,
    send_email_notification,
    send_webhook_notification,
)
from .agents import filter_papers, score_papers, analyze_paper, analysis_to_digest

logger = logging.getLogger(__name__)


async def run_workflow(settings: Settings) -> list[DigestItem]:
    """
    Execute the complete arxiv agent workflow.
    
    Steps:
    1. Fetch papers from arxiv
    2. Filter papers by relevance
    3. Score remaining papers
    4. Analyze top papers in depth
    5. Send notifications
    
    Args:
        settings: Application settings
        
    Returns:
        List of digest items that were processed
    """
    logger.info("Starting arxiv agent workflow")
    
    # Step 1: Fetch papers
    logger.info(f"Fetching papers for topics: {settings.search_topic_list}")
    papers = fetch_arxiv_papers(
        topics=settings.search_topic_list,
        days_back=settings.trace_back_days,
    )
    
    if not papers:
        logger.warning("No papers found from arxiv")
        return []
    
    logger.info(f"Found {len(papers)} papers from arxiv")
    
    # Step 2: Filter papers
    filtered = await filter_papers(
        model=settings.model_mini,
        papers=papers,
        acceptance_criteria=settings.acceptance_criteria,
    )
    
    relevant_papers = [f.paper for f in filtered if f.is_relevant]
    logger.info(f"{len(relevant_papers)} papers passed relevance filter")
    
    if not relevant_papers:
        logger.warning("No papers passed the relevance filter")
        return []
    
    # Step 3: Score papers
    scored = await score_papers(
        model=settings.model_mini,
        papers=relevant_papers,
        acceptance_criteria=settings.acceptance_criteria,
    )
    
    # Filter by score threshold and take top N
    qualified = [s for s in scored if s.score >= settings.score_threshold]
    top_papers = qualified[:settings.max_items]
    
    logger.info(f"{len(qualified)} papers above threshold, taking top {len(top_papers)}")
    
    if not top_papers:
        logger.warning("No papers met the score threshold")
        return []
    
    # Step 4: Deep analysis of top papers
    digest_items = []
    
    for scored_paper in top_papers:
        paper = scored_paper.paper
        logger.info(f"Analyzing paper: {paper.title[:60]}...")
        
        feedback = search_paper_feedback(paper.title, paper.arxiv_id)
        paper_content = download_and_extract_paper(paper.pdf_url, paper.arxiv_id)
        
        analysis = await analyze_paper(
            model=settings.model_full,
            paper=paper,
            initial_score=scored_paper.score,
            community_feedback=feedback,
            paper_content=paper_content,
            acceptance_criteria=settings.acceptance_criteria,
        )
        
        digest_item = analysis_to_digest(analysis)
        digest_items.append(digest_item)
    
    logger.info(f"Completed analysis of {len(digest_items)} papers")
    
    # Step 5: Send notifications
    await _send_notifications(digest_items, settings)
    
    return digest_items


async def _send_notifications(
    digest_items: list[DigestItem],
    settings: Settings,
) -> list[NotificationResult]:
    """Send notifications via configured channels."""
    results = []
    
    if settings.email_list and settings.brevo_api_key and settings.brevo_sender_email:
        logger.info(f"Sending email to {len(settings.email_list)} recipients")
        result = send_email_notification(
            digest_items=digest_items,
            email_list=settings.email_list,
            brevo_api_key=settings.brevo_api_key,
            sender_email=settings.brevo_sender_email,
            sender_name=settings.brevo_sender_name,
        )
        results.append(result)
        if result.success:
            logger.info("Email notification sent successfully")
        else:
            logger.error(f"Email notification failed: {result.message}")
    
    if settings.webhook_url:
        logger.info("Sending webhook notification")
        result = send_webhook_notification(
            digest_items=digest_items,
            webhook_url=settings.webhook_url,
        )
        results.append(result)
        if result.success:
            logger.info("Webhook notification sent successfully")
        else:
            logger.error(f"Webhook notification failed: {result.message}")
    
    if not results:
        logger.warning("No notification channels configured")
    
    return results
