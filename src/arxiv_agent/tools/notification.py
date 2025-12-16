"""Tools for sending notifications via email and webhook."""

import logging

import httpx

from ..models import DigestItem, NotificationResult

logger = logging.getLogger(__name__)


def send_email_notification(
    digest_items: list[DigestItem],
    email_list: list[str],
    brevo_api_key: str,
    sender_email: str = "noreply@arxiv-agent.local",
) -> NotificationResult:
    """
    Send digest via email using Brevo API.
    
    Args:
        digest_items: List of digest items to send
        email_list: List of recipient email addresses
        brevo_api_key: Brevo API key
        sender_email: Sender email address
        
    Returns:
        NotificationResult indicating success/failure
    """
    if not email_list:
        return NotificationResult(success=False, channel="email", message="No recipients")
    
    if not brevo_api_key:
        return NotificationResult(success=False, channel="email", message="No API key")
    
    html_content = _build_email_html(digest_items)
    
    payload = {
        "sender": {"email": sender_email, "name": "Arxiv Agent"},
        "to": [{"email": email} for email in email_list],
        "subject": f"Arxiv Digest: {len(digest_items)} Papers",
        "htmlContent": html_content,
    }
    
    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={
                "api-key": brevo_api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        logger.info(f"Email sent successfully to {len(email_list)} recipients")
        return NotificationResult(success=True, channel="email")
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to send email: {e}")
        return NotificationResult(success=False, channel="email", message=str(e))


def send_webhook_notification(
    digest_items: list[DigestItem],
    webhook_url: str,
) -> NotificationResult:
    """
    Send digest via webhook POST request.
    
    Args:
        digest_items: List of digest items to send
        webhook_url: Webhook URL to POST to
        
    Returns:
        NotificationResult indicating success/failure
    """
    if not webhook_url:
        return NotificationResult(success=False, channel="webhook", message="No webhook URL")
    
    payload = {
        "type": "arxiv_digest",
        "count": len(digest_items),
        "papers": [item.model_dump() for item in digest_items],
    }
    
    try:
        response = httpx.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        response.raise_for_status()
        logger.info("Webhook notification sent successfully")
        return NotificationResult(success=True, channel="webhook")
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to send webhook: {e}")
        return NotificationResult(success=False, channel="webhook", message=str(e))


def _build_email_html(digest_items: list[DigestItem]) -> str:
    """Build HTML content for email digest."""
    items_html = ""
    
    for item in digest_items:
        items_html += f"""
        <div style="margin-bottom: 30px; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="margin-top: 0; color: #1a1a1a;">
                <a href="{item.arxiv_url}" style="color: #0066cc; text-decoration: none;">{item.title}</a>
            </h2>
            <p style="color: #666; font-size: 14px;"><strong>Authors:</strong> {item.authors}</p>
            <p style="color: #666; font-size: 14px;"><strong>Published:</strong> {item.publish_date}</p>
            <p style="color: #666; font-size: 14px;">
                <strong>Rating:</strong> 
                <span style="background: #{'2ecc71' if item.rating >= 70 else 'f39c12' if item.rating >= 50 else 'e74c3c'}; 
                       color: white; padding: 2px 8px; border-radius: 4px;">{item.rating}/100</span>
            </p>
            <h3 style="color: #333; margin-bottom: 8px;">Summary</h3>
            <p style="color: #444;">{item.summary}</p>
            <h3 style="color: #333; margin-bottom: 8px;">Rating Justification</h3>
            <p style="color: #444;">{item.rating_justification}</p>
            <h3 style="color: #333; margin-bottom: 8px;">Community Reputation</h3>
            <p style="color: #444;">{item.community_reputation}</p>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        </style>
    </head>
    <body>
        <h1 style="color: #1a1a1a; border-bottom: 2px solid #0066cc; padding-bottom: 10px;">
            📚 Arxiv Paper Digest
        </h1>
        <p style="color: #666;">Found {len(digest_items)} relevant papers for you.</p>
        {items_html}
        <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0; 
                       color: #999; font-size: 12px; text-align: center;">
            Generated by Arxiv Agent
        </footer>
    </body>
    </html>
    """

