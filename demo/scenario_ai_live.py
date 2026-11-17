"""Live conversation with ai-support-bot using a real model, recorded for screenshots.

Gemini (free tier, key from https://aistudio.google.com/apikey):
    GEMINI_API_KEY=... python demo/scenario_ai_live.py
Ollama (free, local):  AI_PROVIDER=ollama python demo/scenario_ai_live.py
Claude:                AI_PROVIDER=claude ANTHROPIC_API_KEY=... python demo/scenario_ai_live.py

No Telegram token is needed: the bot runs on the offline emulator from simulator.py.
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-support-bot"))
sys.path.insert(0, str(ROOT / "demo"))
os.environ.setdefault("AI_PROVIDER", "gemini")
os.environ.update(BOT_TOKEN="42:TEST", SUPPORT_CHAT_ID="-100500",
                  KNOWLEDGE_FILE=str(ROOT / "ai-support-bot/knowledge/brewlab.md"))

from aiogram import Dispatcher  # noqa: E402
from aiogram.types import User  # noqa: E402

from app.ai import SupportAI  # noqa: E402
from app.handlers import chat  # noqa: E402
from app.memory import ChatMemory  # noqa: E402
from simulator import Emulator  # noqa: E402
from transcript import save  # noqa: E402

SUPPORT_CHAT = -100500
OPERATOR = User(id=555, is_bot=False, first_name="Sophie")
TITLE = "Brew Lab Coffee"


async def main() -> None:
    memory = ChatMemory()
    dp = Dispatcher(ai=SupportAI(), memory=memory)
    dp.include_routers(chat.operators, chat.customers)
    em = Emulator(dp, User(id=1001, is_bot=False, first_name="Olivia", username="olivia_r"))

    await em.send("/start")
    em.snapshot("start", TITLE)
    await em.send("Hi! I mostly drink flat whites at home. Which beans should I get?")
    await em.send("Nice. How fast is delivery to Leeds, and is it free?")
    em.snapshot("answers", TITLE, last=4)
    await em.send("Also, my order #1042 hasn't arrived yet, it's been a week 😕")
    if em.chat()[-1].inline:  # the model asked for a human
        await em.tap("👤 Talk to a human")
        ticket = em.chat(SUPPORT_CHAT)[-1]
        em.snapshot("operator-chat", TITLE, chat_id=SUPPORT_CHAT, subtitle="support team group")
        await em.send("Hi Olivia, sorry about that! Your parcel got stuck at the depot, "
                      "we've sent a new one today, tracking RM482915736GB.",
                      chat_id=SUPPORT_CHAT, user=OPERATOR, reply_to=ticket.message_id)
    em.snapshot("handoff", TITLE, last=5)

    for b in em.chat():
        print(("BOT: " if b.side == "bot" else "YOU: ") + b.html, "\n")
    save("ai", em)


if __name__ == "__main__":
    asyncio.run(main())
