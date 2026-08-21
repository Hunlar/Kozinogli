import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from db.database import create_db_and_tables
from settings import BOT_TOKEN
from bot.middlewares.block_check import BlockCheckMiddleware

# Импорт всех роутеров
from bot.handlers.auth import router as auth_router
from bot.handlers.common import router as common_router
from bot.handlers.profile import router as profile_router
from bot.handlers.games.games_menu import router as games_menu_router
from bot.handlers.games.slots import router as slots_router
from bot.handlers.games.roulette import router as roulette_router
from bot.handlers.games.blackjack import router as blackjack_router
from bot.handlers.games.mines import router as mines_router
from bot.handlers.games.crash import router as crash_router
from bot.handlers.games.even_odd import router as even_odd_router
from bot.handlers.admin_handlers import router as admin_router
from bot.handlers.top_up import router as top_up_router
from bot.handlers.support import router as support_router
from bot.handlers.bonuses import router as bonuses_router

async def main():
    await create_db_and_tables()
    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # Подключение роутеров
    dp.include_router(auth_router)
    dp.include_router(common_router)
    dp.include_router(profile_router)
    dp.include_router(games_menu_router)
    dp.include_router(slots_router)
    dp.include_router(roulette_router)
    dp.include_router(blackjack_router)
    dp.include_router(mines_router)
    dp.include_router(crash_router)
    dp.include_router(even_odd_router)
    dp.include_router(bonuses_router)
    dp.include_router(top_up_router)
    dp.include_router(support_router)
    dp.include_router(admin_router)

    # Middleware на ВСЕ события
    dp.message.middleware(BlockCheckMiddleware())
    dp.callback_query.middleware(BlockCheckMiddleware())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
