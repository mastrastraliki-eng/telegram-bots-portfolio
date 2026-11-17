"""Entry point: python -m app.main"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .ai import SupportAI
from .config import settings
from .handlers import chat
from .memory import ChatMemory


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(ai=SupportAI(), memory=ChatMemory())  # injected into handlers
    dp.include_routers(chat.operators, chat.customers)

    await bot.set_my_commands([
        BotCommand(command="start", description="Start over"),
        BotCommand(command="reset", description="Clear conversation"),
    ])
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
