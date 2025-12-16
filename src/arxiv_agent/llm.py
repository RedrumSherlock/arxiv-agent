"""LLM client for OpenAI-compatible APIs (Azure OpenAI, LiteLLM, etc.)."""

import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def init_client(api_key: str, api_endpoint: str) -> None:
    """Initialize the OpenAI-compatible client."""
    global _client
    _client = AsyncOpenAI(
        api_key=api_key,
        base_url=api_endpoint,
    )
    logger.info(f"LLM client initialized with endpoint: {api_endpoint}")


def get_client() -> AsyncOpenAI:
    """Get the initialized client."""
    if _client is None:
        raise RuntimeError("LLM client not initialized. Call init_client first.")
    return _client


async def chat_completion(
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Send a chat completion request.
    
    Args:
        model: Model name/deployment name
        system_prompt: System instruction
        user_prompt: User message
        
    Returns:
        Assistant response text
    """
    client = get_client()
    
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    
    return response.choices[0].message.content or ""

