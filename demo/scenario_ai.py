"""End-to-end scenario for ai-support-bot with the Claude call stubbed out.

Checks the bot logic (history, hand-off, operator relay) without an API key.
Run: python demo/scenario_ai.py
"""

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-support-bot"))
sys.path.insert(0, str(ROOT / "demo"))
os.environ.update(BOT_TOKEN="42:TEST", SUPPORT_CHAT_ID="-100500", ANTHROPIC_API_KEY="test",
                  KNOWLEDGE_FILE=str(ROOT / "ai-support-bot/knowledge/brewlab.md"))

from aiogram import Dispatcher  # noqa: E402
from aiogram.types import User  # noqa: E402

from app.ai import HANDOFF_MARK, Answer, SupportAI  # noqa: E402
from app.handlers import chat  # noqa: E402
from app.memory import ChatMemory  # noqa: E402
from simulator import Emulator  # noqa: E402

SUPPORT_CHAT = -100500
OPERATOR = User(id=555, is_bot=False, first_name="Sophie")


class StubAI:
    """Stands in for SupportAI: canned replies, records what it was asked."""

    def __init__(self):
        self.calls: list[list[dict]] = []

    async def reply(self, history):
        self.calls.append(history)
        q = history[-1]["content"].lower()
        if "order" in q:
            return Answer("I can't see order details, a team member will check it for you.", True)
        return Answer(f"stub answer to: {history[-1]['content']}", False)


async def check_response_parsing() -> None:
    """Run the real SupportAI.reply against a fake Anthropic client."""
    ai = SupportAI()
    assert "Yirgacheffe" in ai.system  # knowledge base is in the system prompt

    def fake(text, stop="end_turn"):
        async def create(**kw):
            assert kw["model"] and kw["cache_control"] == {"type": "ephemeral"}
            return SimpleNamespace(
                stop_reason=stop,
                content=[SimpleNamespace(type="text", text=text)],
                usage=SimpleNamespace(input_tokens=1, cache_read_input_tokens=0, output_tokens=1),
            )
        ai.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))

    fake("UK shipping is £3.95, free over £30.")
    a = await ai.reply([{"role": "user", "content": "shipping?"}])
    assert a == Answer("UK shipping is £3.95, free over £30.", False), a

    fake(f"A team member will help with that. {HANDOFF_MARK}")
    a = await ai.reply([{"role": "user", "content": "where is my order"}])
    assert a.handoff and HANDOFF_MARK not in a.text, a

    fake("", stop="refusal")
    a = await ai.reply([{"role": "user", "content": "..."}])
    assert a.handoff


async def main() -> None:
    await check_response_parsing()

    ai, memory = StubAI(), ChatMemory()
    dp = Dispatcher(ai=ai, memory=memory)
    dp.include_routers(chat.operators, chat.customers)
    em = Emulator(dp, User(id=1001, is_bot=False, first_name="Olivia", username="olivia_r"))

    await em.send("/start")
    await em.tap("🚚 Shipping & delivery")
    assert "stub answer to: Shipping &amp; delivery" in em.last_bot_text()

    await em.send("Do you ship to Germany?")
    assert [m["role"] for m in ai.calls[-1]] == ["user", "assistant", "user"]

    await em.send("Where is my order #1042?")
    assert "team member" in em.last_bot_text() and em.chat()[-1].inline == [["👤 Talk to a human"]]

    await em.tap("👤 Talk to a human")
    ticket = em.chat(SUPPORT_CHAT)[-1]
    assert "#id1001" in ticket.html and "order #1042" in ticket.html, ticket.html

    # Operator answers by replying to the ticket in the support group
    await em.send("Hi Olivia! Order #1042 was shipped yesterday, tracking: RM123456789GB",
                  chat_id=SUPPORT_CHAT, user=OPERATOR, reply_to=ticket.message_id)
    assert "RM123456789GB" in em.last_bot_text() and "Sophie" in em.last_bot_text()
    assert memory.get(1001)[-1]["role"] == "assistant"

    # A customer replying to a bot message is still answered by the AI (not swallowed)
    await em.send("thanks!", reply_to=em.chat()[-1].message_id)
    assert em.last_bot_text() == "stub answer to: thanks!"

    await em.send("/reset")
    assert memory.get(1001) == []
    print("ai-support-bot: all checks passed")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), 60))
