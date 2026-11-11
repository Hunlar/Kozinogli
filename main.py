
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from settings import BOT_TOKEN
from db.database import create_db_and_tables, close_database

from bot.middlewares.block_check import BlockCheckMiddleware
from bot.handlers import setup_handlers


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR TOKEN":
        raise ValueError("BOT_TOKEN ortam değişkeni tanımlanmamış!")

    await create_db_and_tables()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    setup_handlers(dp)

    dp.message.middleware(BlockCheckMiddleware())
    dp.callback_query.middleware(BlockCheckMiddleware())

    try:
        print("ÖzVeGas botu başlatılıyor...")
        await dp.start_polling(bot)

    finally:
        await bot.session.close()
        await close_database()
        print("ÖzVeGas botu kapatıldı.")


if __name__ == "__main__":
    asyncio.run(main())
