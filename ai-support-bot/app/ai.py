"""AI answers grounded in the business knowledge base.

Three interchangeable backends:
- "gemini": Google Gemini API, has a free tier (key from aistudio.google.com)
- "ollama": a free local model (Llama, Qwen, Mistral...) served by Ollama, no API key at all
- "claude": Anthropic's Claude API, the strongest option for production
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import aiohttp
import anthropic

from .config import settings

log = logging.getLogger(__name__)

HANDOFF_MARK = "[HANDOFF]"

SYSTEM_TEMPLATE = """You are the customer support assistant of {business} in a Telegram chat.

Answer ONLY from the knowledge base below. Rules:
- Be friendly, concise and concrete: 1–4 short sentences or a short list. Reply in the customer's language.
- Plain text only: no Markdown, no asterisks, no headings. Emoji are fine, sparingly.
- Never invent prices, policies, order statuses or promises that are not in the knowledge base.
- If the answer is not in the knowledge base, or the customer asks about a specific order, wants a refund
  processed, is upset, or asks for a person: say briefly that a team member will help, and end your reply
  with the exact marker {mark}
- Stay on topic. Politely decline questions unrelated to {business}.

<knowledge_base>
{kb}
</knowledge_base>"""


@dataclass
class Answer:
    text: str
    handoff: bool


class BackendError(Exception):
    """The model could not be reached; `user_message` is safe to show to the customer."""

    def __init__(self, user_message: str, handoff: bool = False):
        super().__init__(user_message)
        self.user_message = user_message
        self.handoff = handoff


class Backend(Protocol):
    async def complete(self, system: str, history: list[dict]) -> str | None:
        """Return the model's reply, or None if the model declined to answer."""


class OllamaBackend:
    """Free local model through Ollama's HTTP API (https://ollama.com)."""

    def __init__(self, url: str, model: str):
        self.url = url.rstrip("/") + "/api/chat"
        self.model = model

    async def complete(self, system: str, history: list[dict]) -> str | None:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *history],
            "stream": False,
            "options": {"temperature": 0.3},
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as s:
                async with s.post(self.url, json=payload) as r:
                    r.raise_for_status()
                    data = await r.json()
        except (aiohttp.ClientError, TimeoutError) as e:
            log.warning("Ollama request failed: %r", e)
            raise BackendError("I can't reach my brain right now 😅 Please try again shortly.") from e
        return data["message"]["content"]


class GeminiBackend:
    """Google Gemini API via REST (https://ai.google.dev). Free tier available."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://generativelanguage.googleapis.com"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self.api_key = api_key
        self.url = f"{base_url.rstrip('/')}/v1beta/models/{model}:generateContent"

    async def complete(self, system: str, history: list[dict]) -> str | None:
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in history
            ],
            "generationConfig": {"temperature": 0.3},
        }
        headers = {"x-goog-api-key": self.api_key}
        data = None
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60), trust_env=True) as s:
            for attempt in range(3):
                if attempt:
                    await asyncio.sleep(2 * attempt)  # free tier is often briefly overloaded: back off and retry
                try:
                    async with s.post(self.url, json=payload, headers=headers) as r:
                        if r.status in (429, 500, 503):
                            log.warning("Gemini busy (%s), attempt %s", r.status, attempt + 1)
                            continue
                        if r.status >= 400:
                            log.warning("Gemini API error %s: %s", r.status, (await r.text())[:500])
                            raise BackendError("Something went wrong on my side. A team member will take a look.", True)
                        data = await r.json()
                        break
                except (aiohttp.ClientError, TimeoutError) as e:
                    log.warning("Gemini request failed: %r", e)
        if data is None:
            raise BackendError("We're getting a lot of messages right now. Please try again in a minute 🙏")

        candidates = data.get("candidates") or []
        if not candidates or candidates[0].get("finishReason") in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"}:
            return None  # blocked by safety filters
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))


class ClaudeBackend:
    """Anthropic Claude API (needs ANTHROPIC_API_KEY)."""

    def __init__(self, model: str, effort: str):
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.effort = effort

    async def complete(self, system: str, history: list[dict]) -> str | None:
        try:
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=history,
                # The system prompt never changes, so caching makes follow-up questions cheap.
                cache_control={"type": "ephemeral"},
                output_config={"effort": self.effort},
                # If the main model declines, the API retries on a fallback model in the same call.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise BackendError("We're getting a lot of messages right now. Please try again in a minute 🙏") from e
        except anthropic.APIConnectionError as e:
            log.exception("Claude connection error")
            raise BackendError("I can't reach my brain right now 😅 Please try again shortly.") from e
        except anthropic.APIStatusError as e:
            log.exception("Claude API error")
            raise BackendError("Something went wrong on my side. A team member will take a look.", True) from e

        if response.stop_reason == "refusal":
            return None
        log.info("usage: in=%s cached=%s out=%s", response.usage.input_tokens,
                 response.usage.cache_read_input_tokens, response.usage.output_tokens)
        return "".join(block.text for block in response.content if block.type == "text")


def build_backend() -> Backend:
    if settings.ai_provider == "claude":
        return ClaudeBackend(settings.claude_model, settings.claude_effort)
    if settings.ai_provider == "ollama":
        return OllamaBackend(settings.ollama_url, settings.ollama_model)
    if settings.ai_provider == "gemini":
        return GeminiBackend(settings.gemini_api_key, settings.gemini_model)
    raise ValueError(f"Unknown AI_PROVIDER: {settings.ai_provider!r} (use 'gemini', 'ollama' or 'claude')")


class SupportAI:
    def __init__(self, backend: Backend | None = None) -> None:
        self.backend = backend or build_backend()
        kb = Path(settings.knowledge_file).read_text(encoding="utf-8")
        self.system = SYSTEM_TEMPLATE.format(business=settings.business_name, kb=kb, mark=HANDOFF_MARK)

    async def reply(self, history: list[dict]) -> Answer:
        try:
            text = await self.backend.complete(self.system, history)
        except BackendError as e:
            return Answer(e.user_message, e.handoff)
        if text is None:  # the model declined
            return Answer("I can't help with that here, but a team member can.", True)

        text = text.strip()
        handoff = HANDOFF_MARK in text
        text = text.replace(HANDOFF_MARK, "").strip() or "Let me connect you with a team member."
        return Answer(text, handoff)
