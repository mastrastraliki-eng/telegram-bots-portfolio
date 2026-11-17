"""Entry point: python -m app.main"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .config import settings
from .db import Database
from .handlers import admin, client
from .reminders import reminder_loop


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db = Database(settings.db_path)
    await db.connect()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(db=db)  # `db` is injected into every handler that asks for it
    dp.include_routers(admin.router, client.router)

    await bot.set_my_commands([BotCommand(command="start", description="Main menu")])
    reminders = asyncio.create_task(reminder_loop(bot, db))
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
