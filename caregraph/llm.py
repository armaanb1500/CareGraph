"""Talks to the LLM provider.

The rest of CareGraph calls generate() and never touches the Gemini SDK
directly. When we add Ollama later, only this file needs to change.
"""

import functools
import time
from dataclasses import dataclass

import httpx
from google import genai
from google.genai import errors, types

from caregraph.config import get_settings

# 429 = rate limited (free tier), 500/503 = the server is overloaded.
# These usually succeed if you wait and try again.
RETRYABLE_STATUS = {429, 500, 503}
ATTEMPTS_PER_MODEL = 2

# A congested model can hang for over a minute before failing. Stop waiting
# after this long and move on to the next model instead.
REQUEST_TIMEOUT_SECONDS = 40


class LLMUnavailableError(Exception):
    """Every configured model was overloaded or timed out."""


@dataclass
class LLMResult:
    text: str
    model: str  # which model actually answered - matters for auditing later
    input_tokens: int
    output_tokens: int
    thinking_tokens: int


@functools.cache
def _client() -> genai.Client:
    # attempts=1 turns off the SDK's built-in retries so generate() is the
    # only place retry decisions happen.
    return genai.Client(
        api_key=get_settings().gemini_api_key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_SECONDS * 1000,  # the SDK wants milliseconds
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def generate(prompt: str, system: str | None = None, temperature: float = 0.2) -> LLMResult:
    """Send a prompt to the LLM and return its reply plus token usage.

    system:      standing instructions for how the model should behave.
    temperature: randomness. Low (0-0.3) for factual work, higher for creative work.

    Tries GEMINI_MODEL first. If it's overloaded or too slow, tries each of
    GEMINI_FALLBACK_MODELS in order.
    """
    settings = get_settings()
    if settings.llm_provider != "gemini":
        raise NotImplementedError(f"LLM_PROVIDER={settings.llm_provider!r} isn't supported yet")

    config = types.GenerateContentConfig(system_instruction=system, temperature=temperature)
    models = [settings.gemini_model, *settings.gemini_fallback_models]

    for model in models:
        for attempt in range(1, ATTEMPTS_PER_MODEL + 1):
            print(f"(asking {model}...)", flush=True)
            try:
                response = _client().models.generate_content(
                    model=model, contents=prompt, config=config
                )
                return _to_result(response, model)
            except httpx.TimeoutException:
                # Too slow. Waiting again is unlikely to help, so skip to the next model.
                print(f"({model} took over {REQUEST_TIMEOUT_SECONDS}s, moving on)")
                break
            except errors.APIError as e:
                if e.code == 504:  # the server gave up on its own deadline
                    print(f"({model} timed out on Google's side, moving on)")
                    break
                if e.code not in RETRYABLE_STATUS:
                    raise  # a real error (bad key, bad request) - retrying won't help
                if attempt < ATTEMPTS_PER_MODEL:
                    wait = 2**attempt  # 2s, 4s, ...: "exponential backoff"
                    print(f"({model} returned {e.code}, retrying in {wait}s...)")
                    time.sleep(wait)
                else:
                    print(f"({model} is still returning {e.code}, moving on)")

    raise LLMUnavailableError(
        "Every configured model is overloaded or too slow right now. Try again in a few minutes."
    )


def _to_result(response: types.GenerateContentResponse, model: str) -> LLMResult:
    usage = response.usage_metadata
    return LLMResult(
        text=response.text or "",
        model=model,
        input_tokens=usage.prompt_token_count or 0,
        output_tokens=usage.candidates_token_count or 0,
        thinking_tokens=usage.thoughts_token_count or 0,
    )
