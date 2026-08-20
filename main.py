# main.py
import asyncio
from aiogram import Bot, Dispatcher
from bot.handlers import setup_handlers
from db.database import create_db_and_tables
from settings import BOT_TOKEN
from aiogram.fsm.storage.memory import MemoryStorage
from bot.middlewares.block_check import BlockCheckMiddleware

async def main():
    await create_db_and_tables()  # Создаем таблицы перед запуском
    storage = MemoryStorage()  # Инициализируем хранилище состояний
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)  # Передаем хранилище
    setup_handlers(dp)
    dp.message.middleware(BlockCheckMiddleware())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())