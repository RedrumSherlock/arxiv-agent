"""Tool for downloading and extracting content from arxiv papers."""

import logging

import httpx

logger = logging.getLogger(__name__)


def download_and_extract_paper(pdf_url: str, arxiv_id: str) -> str:
    """
    Download a paper PDF and extract its text content.
    
    Args:
        pdf_url: URL to the PDF file
        arxiv_id: Arxiv ID for logging purposes
        
    Returns:
        Extracted text content from the paper (first ~10 pages)
    """
    logger.info(f"Downloading paper {arxiv_id} from {pdf_url}")
    
    try:
        pdf_content = _download_pdf(pdf_url)
        if not pdf_content:
            return ""
        
        text = _extract_text_from_pdf(pdf_content)
        return text[:50000]  # Limit to ~50k chars
        
    except Exception as e:
        logger.error(f"Failed to process paper {arxiv_id}: {e}")
        return ""


def _download_pdf(url: str) -> bytes | None:
    """Download PDF from URL."""
    try:
        response = httpx.get(
            url,
            timeout=60.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ArxivAgent/1.0)"},
        )
        response.raise_for_status()
        return response.content
    except httpx.HTTPError as e:
        logger.error(f"Failed to download PDF: {e}")
        return None


def _extract_text_from_pdf(pdf_content: bytes) -> str:
    """Extract text from PDF content."""
    try:
        from PyPDF2 import PdfReader
        import io
        
        reader = PdfReader(io.BytesIO(pdf_content))
        text_parts = []
        
        max_pages = min(len(reader.pages), 15)
        for i in range(max_pages):
            page = reader.pages[i]
            text = page.extract_text()
            if text:
                text_parts.append(text)
        
        return "\n\n".join(text_parts)
        
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        return ""

