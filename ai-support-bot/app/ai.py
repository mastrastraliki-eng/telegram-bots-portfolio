"""Claude-powered answers grounded in the business knowledge base."""

import logging
from dataclasses import dataclass
from pathlib import Path

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


class SupportAI:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY
        kb = Path(settings.knowledge_file).read_text(encoding="utf-8")
        # Built once and never changes, so prompt caching makes every follow-up request cheap.
        self.system = SYSTEM_TEMPLATE.format(business=settings.business_name, kb=kb, mark=HANDOFF_MARK)

    async def reply(self, history: list[dict]) -> Answer:
        try:
            response = await self.client.beta.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=self.system,
                messages=history,
                cache_control={"type": "ephemeral"},
                output_config={"effort": settings.claude_effort},
                # If the main model declines, the API retries on a fallback model in the same call.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError:
            log.warning("Claude rate limit hit")
            return Answer("We're getting a lot of messages right now. Please try again in a minute 🙏", False)
        except anthropic.APIConnectionError:
            log.exception("Claude connection error")
            return Answer("I can't reach my brain right now 😅 Please try again shortly.", False)
        except anthropic.APIStatusError:
            log.exception("Claude API error")
            return Answer("Something went wrong on my side. A team member will take a look.", True)

        if response.stop_reason == "refusal":
            return Answer("I can't help with that here, but a team member can.", True)

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        handoff = HANDOFF_MARK in text
        text = text.replace(HANDOFF_MARK, "").strip() or "Let me connect you with a team member."
        log.info("usage: in=%s cached=%s out=%s", response.usage.input_tokens,
                 response.usage.cache_read_input_tokens, response.usage.output_tokens)
        return Answer(text, handoff)
