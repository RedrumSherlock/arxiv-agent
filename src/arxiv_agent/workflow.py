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
    send_status_email,
    send_status_webhook,
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
        days_start=settings.trace_back_days_start,
        days_end=settings.trace_back_days_end,
        categories=settings.arxiv_category_list or None,
    )

    if not papers:
        logger.warning("No papers found from arxiv")
        await _send_status_notifications(
            "No papers found from arxiv for the specified search criteria.",
            settings,
        )
        return []

    logger.info(f"Found {len(papers)} papers from arxiv")

    # Step 2: Filter papers
    filter_result = await filter_papers(
        model=settings.model_filter,
        papers=papers,
        acceptance_criteria=settings.acceptance_criteria,
        batch_size=settings.filter_batch_size,
    )

    relevant_papers = [f.paper for f in filter_result.papers if f.is_relevant]
    logger.info(f"{len(relevant_papers)} papers passed relevance filter")

    if not relevant_papers:
        logger.warning("No papers passed the relevance filter")
        message = _build_status_message(
            "No papers passed the relevance filter.",
            len(papers),
            filter_result.failed_batches,
            filter_result.total_batches,
            0,
            0,
        )
        await _send_status_notifications(message, settings)
        return []

    # Step 3: Score papers
    score_result = await score_papers(
        model=settings.model_scorer,
        papers=relevant_papers,
        acceptance_criteria=settings.acceptance_criteria,
        batch_size=settings.scorer_batch_size,
    )

    # Filter by score threshold and take top N
    qualified = [s for s in score_result.papers if s.score >= settings.score_threshold]
    top_papers = qualified[:settings.max_items]

    logger.info(f"{len(qualified)} papers above threshold, taking top {len(top_papers)}")

    if not top_papers:
        logger.warning("No papers met the score threshold")
        message = _build_status_message(
            f"No papers met the score threshold ({settings.score_threshold}).",
            len(papers),
            filter_result.failed_batches,
            filter_result.total_batches,
            score_result.failed_batches,
            score_result.total_batches,
        )
        await _send_status_notifications(message, settings)
        return []

    # Step 4: Deep analysis of top papers
    digest_items = []

    for scored_paper in top_papers:
        paper = scored_paper.paper
        logger.info(f"Analyzing paper: {paper.title[:60]}...")

        feedback = search_paper_feedback(paper.title, paper.arxiv_id)
        paper_content = download_and_extract_paper(paper.pdf_url, paper.arxiv_id)

        analysis = await analyze_paper(
            model=settings.model_analyzer,
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


def _build_status_message(
    reason: str,
    total_papers: int,
    filter_failed_batches: int,
    filter_total_batches: int,
    scorer_failed_batches: int,
    scorer_total_batches: int,
) -> str:
    """Build a status message with error details."""
    lines = [reason, "", f"Papers fetched from arxiv: {total_papers}"]

    if filter_total_batches > 0:
        if filter_failed_batches > 0:
            lines.append(
                f"Filter errors: {filter_failed_batches}/{filter_total_batches} batches failed"
            )
        else:
            lines.append(f"Filter: {filter_total_batches} batches processed successfully")

    if scorer_total_batches > 0:
        if scorer_failed_batches > 0:
            lines.append(
                f"Scorer errors: {scorer_failed_batches}/{scorer_total_batches} batches failed"
            )
        else:
            lines.append(f"Scorer: {scorer_total_batches} batches processed successfully")

    if filter_failed_batches > 0 or scorer_failed_batches > 0:
        lines.append("")
        lines.append("Note: Connection errors may have affected paper scoring. "
                     "Papers with failed scoring default to score 50.")

    return "\n".join(lines)


async def _send_status_notifications(
    message: str,
    settings: Settings,
) -> list[NotificationResult]:
    """Send status notifications via configured channels."""
    results = []

    if settings.email_list and settings.brevo_api_key and settings.brevo_sender_email:
        logger.info(f"Sending status email to {len(settings.email_list)} recipients")
        result = send_status_email(
            message=message,
            email_list=settings.email_list,
            brevo_api_key=settings.brevo_api_key,
            sender_email=settings.brevo_sender_email,
            sender_name=settings.brevo_sender_name,
        )
        results.append(result)
        if result.success:
            logger.info("Status email sent successfully")
        else:
            logger.error(f"Status email failed: {result.message}")

    if settings.webhook_url:
        logger.info("Sending status webhook notification")
        result = send_status_webhook(
            message=message,
            webhook_url=settings.webhook_url,
        )
        results.append(result)
        if result.success:
            logger.info("Status webhook sent successfully")
        else:
            logger.error(f"Status webhook failed: {result.message}")

    if not results:
        logger.warning("No notification channels configured")

    return results


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
