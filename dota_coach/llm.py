"""Provider-agnostic LLM wrapper. Any OpenAI-compatible endpoint; all settings from .env."""
import os

from openai import AsyncOpenAI

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])
    return _client


async def ask(messages, tools=None):
    """Return the assistant message. Tool calls (if any) are in .tool_calls; caller runs them one at a time."""
    kwargs = {"model": os.environ["LLM_MODEL"], "messages": messages}
    if tools:
        kwargs["tools"] = tools
    resp = await _get_client().chat.completions.create(**kwargs)
    return resp.choices[0].message
