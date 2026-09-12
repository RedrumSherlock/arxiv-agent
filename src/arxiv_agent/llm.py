"""LLM client for OpenAI-compatible APIs (Azure OpenAI, LiteLLM, etc.)."""

import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Values the OpenAI-compatible reasoning_effort parameter accepts. Anything else
# is treated as "do not send the parameter", for models that do not support it.
VALID_REASONING_EFFORTS = frozenset({"none", "minimal", "low", "medium", "high", "xhigh"})

_client: AsyncOpenAI | None = None
_reasoning_effort: str = ""


def init_client(api_key: str, api_endpoint: str, reasoning_effort: str = "") -> None:
    """Initialize the OpenAI-compatible client."""
    global _client, _reasoning_effort
    _client = AsyncOpenAI(
        api_key=api_key,
        base_url=api_endpoint,
    )

    effort = reasoning_effort.strip().lower()
    if effort and effort not in VALID_REASONING_EFFORTS:
        logger.warning(f"Ignoring unsupported REASONING_EFFORT '{reasoning_effort}'")
        effort = ""
    _reasoning_effort = effort

    logger.info(
        f"LLM client initialized with endpoint: {api_endpoint}"
        + (f", reasoning effort: {effort}" if effort else "")
    )


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

    extra_args = {"reasoning_effort": _reasoning_effort} if _reasoning_effort else {}

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **extra_args,
    )

    return response.choices[0].message.content or ""

