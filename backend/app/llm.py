"""Client for any "OpenAI-compatible" chat API: Groq, Gemini, OpenRouter, Mistral, Ollama...

They all accept the same request (POST {base_url}/chat/completions), so switching
provider is only LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in the .env.

Usage (lists the models your key can use, to pick LLM_MODEL):
    python -m app.llm
"""

import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings

LLM_TIMEOUT_SECONDS = 120  # free tiers can be slow on long prompts
# Room for the whole answer. Reasoning models (gpt-oss, qwen3) also "think" inside
# this budget, and the provider's default was too small for a full resume.
MAX_OUTPUT_TOKENS = 8192
MAX_ERROR_CHARS = 300

logger = logging.getLogger(__name__)


class LLMNotConfiguredError(RuntimeError):
    """LLM_API_KEY or LLM_MODEL is missing from the .env."""


class LLMError(RuntimeError):
    """The provider failed or answered something unusable."""


class LLMRateLimitedError(LLMError):
    """HTTP 429: the free quota for this minute/day is used up."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        # Seconds the provider asked us to wait (Retry-After header), when it says
        self.retry_after = retry_after


class LLMBadAnswerError(LLMError):
    """The request worked, but the answer isn't in the layout we asked for (worth one retry)."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    # "low" / "medium" / "high" for reasoning models (gpt-oss); "" = don't send it
    reasoning_effort: str = ""

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/")


def get_llm_config() -> LLMConfig:
    """From the .env. Raises LLMNotConfiguredError if the key or the model is missing.

    Also a FastAPI dependency, so tests swap it for a fake provider.
    """
    settings = get_settings()
    # get_secret_value(): the only way to read a SecretStr (printing it shows ****)
    api_key = settings.llm_api_key.get_secret_value()
    if not api_key or not settings.llm_model:
        raise LLMNotConfiguredError("Set LLM_API_KEY and LLM_MODEL in backend/.env")
    return LLMConfig(
        base_url=settings.llm_base_url,
        api_key=api_key,
        model=settings.llm_model,
        reasoning_effort=settings.llm_reasoning_effort,
    )


def auth_headers(config: LLMConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.api_key}"}


def raise_for_provider_error(response: httpx.Response) -> None:
    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        retry_after: float | None
        try:
            retry_after = float(response.headers.get("retry-after", ""))
        except ValueError:  # missing, or a date instead of seconds
            retry_after = None
        raise LLMRateLimitedError("Free quota used up; try again later", retry_after)
    if response.is_error:
        # The provider's own message helps ("model not found"), but cut it short
        raise LLMError(f"HTTP {response.status_code}: {response.text[:MAX_ERROR_CHARS]}")


def chat(
    client: httpx.Client, config: LLMConfig, system: str, user: str, temperature: float = 0.2
) -> str:
    """Send one system + user message and return the model's text answer.

    Plain text on purpose, not the providers' "JSON mode": a long text inside JSON
    (every newline and quote escaped) is where free models fail, and not every
    provider has that mode. The caller asks for a simple layout and parses it.
    Low temperature: we want faithful rewriting, not creativity.
    """
    body: dict[str, object] = {
        "model": config.model,
        "temperature": temperature,
        # max_tokens (not max_completion_tokens): the name every compatible API accepts
        "max_tokens": MAX_OUTPUT_TOKENS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if config.reasoning_effort:
        # Only sent when set: providers without reasoning models may reject the field
        body["reasoning_effort"] = config.reasoning_effort
    response = client.post(
        f"{config.endpoint}/chat/completions",
        headers=auth_headers(config),
        json=body,
        timeout=LLM_TIMEOUT_SECONDS,
    )
    raise_for_provider_error(response)

    try:
        choice = response.json()["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise LLMBadAnswerError("The provider answered in an unknown format") from error
    if choice.get("finish_reason") == "length":
        raise LLMBadAnswerError("The answer was cut off by the output limit")
    if not isinstance(content, str) or not content.strip():
        raise LLMBadAnswerError("The model answered nothing")
    return content.strip()


def list_models(client: httpx.Client, config: LLMConfig) -> list[str]:
    response = client.get(f"{config.endpoint}/models", headers=auth_headers(config), timeout=30)
    raise_for_provider_error(response)
    return sorted(model["id"] for model in response.json().get("data", []))


def main() -> None:
    settings = get_settings()
    api_key = settings.llm_api_key.get_secret_value()
    if not api_key:
        raise SystemExit("Set LLM_API_KEY in backend/.env first")
    config = LLMConfig(settings.llm_base_url, api_key, settings.llm_model)
    with httpx.Client() as client:
        for model_id in list_models(client, config):
            marker = "  <- LLM_MODEL" if model_id == settings.llm_model else ""
            print(f"{model_id}{marker}")


if __name__ == "__main__":
    main()
