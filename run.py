"""Entry point for running the arxiv agent."""

import asyncio
import logging
import sys

from dotenv import load_dotenv

from src.arxiv_agent.config import get_settings
from src.arxiv_agent.llm import init_client
from src.arxiv_agent.tools.web_search import init_tavily
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
    logging.getLogger("openai").setLevel(logging.WARNING)


async def _main() -> None:
    """Main async entry point."""
    load_dotenv()
    _setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("Arxiv Agent starting...")
    
    settings = get_settings()
    
    if not settings.api_key or not settings.api_endpoint:
        logger.error("API_KEY and API_ENDPOINT are required")
        sys.exit(1)
    
    init_client(settings.api_key, settings.api_endpoint)
    
    if settings.tavily_api_key:
        init_tavily(settings.tavily_api_key)
    else:
        logger.warning("TAVILY_API_KEY not set, web search for community feedback disabled")
    
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
