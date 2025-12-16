"""Entry point for running the arxiv agent."""

import asyncio
import logging
import sys

from dotenv import load_dotenv

from src.arxiv_agent.config import get_settings
from src.arxiv_agent.workflow import run_workflow


def _setup_logging() -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def _main() -> None:
    """Main async entry point."""
    load_dotenv()
    _setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("Arxiv Agent starting...")
    
    settings = get_settings()
    
    if not settings.google_api_key:
        logger.error("GOOGLE_API_KEY is required")
        sys.exit(1)
    
    import os
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
    
    try:
        digest_items = await run_workflow(settings)
        
        if digest_items:
            logger.info(f"Workflow completed successfully with {len(digest_items)} papers")
            for item in digest_items:
                logger.info(f"  - [{item.rating}] {item.title[:60]}...")
        else:
            logger.info("Workflow completed with no papers to report")
            
    except Exception as e:
        logger.exception(f"Workflow failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())

