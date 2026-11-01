"""LLM provider interface and citation validation engine (T7.2, T7.3, ARCHITECTURE 11)."""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

import httpx

from backend.app.config import get_settings
from backend.app.errors import AppError

logger = logging.getLogger(__name__)

CITATION_REGEX = re.compile(r"\[([a-zA-Z0-9_\-\.\/]+):(\d+)(?:-(\d+))?\]")


class LLMProvider(ABC):
    """Abstract LLM Provider interface."""

    @abstractmethod
    async def generate(self, system: str, user_prompt: str, max_tokens: int = 1500) -> str:
        """Generate response text from system and user prompt."""
        pass


class NoneProvider(LLMProvider):
    """Placeholder when no LLM provider is configured."""

    async def generate(self, system: str, user_prompt: str, max_tokens: int = 1500) -> str:
        raise AppError("LLM_NOT_CONFIGURED", "No LLM provider configured.", status_code=503)


class GeminiProvider(LLMProvider):
    """Google Gemini REST API provider using direct async httpx."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self.api_key = api_key
        self.model = model or "gemini-1.5-flash"

    async def generate(self, system: str, user_prompt: str, max_tokens: int = 1500) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise AppError("LLM_API_ERROR", f"Gemini API returned status {resp.status_code}: {resp.text}", status_code=502)
            data = resp.json()
            try:
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return ""
            except Exception as e:
                raise AppError("LLM_PARSE_ERROR", f"Failed to parse Gemini response: {e}", status_code=502)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider using direct async httpx."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"

    async def generate(self, system: str, user_prompt: str, max_tokens: int = 1500) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise AppError("LLM_API_ERROR", f"OpenAI API returned status {resp.status_code}: {resp.text}", status_code=502)
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                raise AppError("LLM_PARSE_ERROR", f"Failed to parse OpenAI response: {e}", status_code=502)


class MockProvider(LLMProvider):
    """Predictable mock provider for unit testing."""

    def __init__(self, canned_response: str) -> None:
        self.canned_response = canned_response

    async def generate(self, system: str, user_prompt: str, max_tokens: int = 1500) -> str:
        return self.canned_response


def get_llm_provider() -> LLMProvider:
    """Instantiate the active LLM provider configured in environment."""
    settings = get_settings()
    provider_name = (settings.LLM_PROVIDER or "none").lower()
    api_key = settings.LLM_API_KEY
    model = settings.LLM_MODEL

    if not api_key or provider_name in ("none", ""):
        return NoneProvider()

    if provider_name == "gemini":
        return GeminiProvider(api_key=api_key, model=model)
    elif provider_name in ("openai", "azure"):
        return OpenAIProvider(api_key=api_key, model=model)
    else:
        logger.warning("Unrecognized LLM provider %s; falling back to NoneProvider", provider_name)
        return NoneProvider()


def validate_citations(
    raw_text: str,
    retrieved_chunks: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]], List[str], bool]:
    """Validate each [path:start-end] citation against retrieved chunks (T7.3 acceptance criterion).

    If a citation references a non-existent file or completely disjoint range:
    1. The citation bracket is removed from the text.
    2. A warning is added.
    3. The answer is flagged.
    """
    valid_citations: List[Dict[str, Any]] = []
    warnings: List[str] = []
    flagged = False

    cleaned_text = raw_text

    matches = list(CITATION_REGEX.finditer(raw_text))

    for m in matches:
        full_cite = m.group(0)
        cite_path = m.group(1)
        cite_start = int(m.group(2))
        cite_end = int(m.group(3)) if m.group(3) else cite_start

        # Check if any retrieved chunk matches this path and overlaps line range
        matched_chunk = None
        for chunk in retrieved_chunks:
            chunk_path = chunk.get("path", "")
            if chunk_path.lower() == cite_path.lower() or chunk_path.endswith(cite_path) or cite_path.endswith(chunk_path):
                c_start = chunk.get("start_line", 1)
                c_end = chunk.get("end_line", c_start)
                # Allow slight range tolerance (+/- 5 lines)
                if not (cite_end < c_start - 5 or cite_start > c_end + 5):
                    matched_chunk = chunk
                    break

        if matched_chunk:
            valid_citations.append({
                "citation": full_cite,
                "path": matched_chunk.get("path", cite_path),
                "start_line": cite_start,
                "end_line": cite_end,
                "chunk_id": matched_chunk.get("id"),
            })
        else:
            flagged = True
            warn_msg = f"Citation {full_cite} was removed: file or line range was not found in retrieved repository context."
            warnings.append(warn_msg)
            # Remove the invalid citation token from text
            cleaned_text = cleaned_text.replace(full_cite, "")

    return cleaned_text.strip(), valid_citations, warnings, flagged
