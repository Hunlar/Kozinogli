
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from settings import BOT_TOKEN
from db.database import create_db_and_tables, close_database

from daily_credit import (
    grant_daily_credits,
    daily_credit_loop
)

from bot.middlewares.block_check import BlockCheckMiddleware
from bot.middlewares.subscription import (
    SubscriptionMiddleware,
    router as subscription_router
)

from bot.handlers import setup_handlers


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR TOKEN":
        raise ValueError("BOT_TOKEN ortam değişkeni tanımlanmamış!")

    await create_db_and_tables()

    # Günlük krediyi kontrol et ve gerekiyorsa dağıt.
    await grant_daily_credits()

    # Gece yarısı otomatik dağıtım görevini başlat.
    daily_task = asyncio.create_task(daily_credit_loop())

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    setup_handlers(dp)
    dp.include_router(subscription_router)

    # Engelleme ve zorunlu üyelik kontrolleri.
    dp.message.middleware(BlockCheckMiddleware())
    dp.callback_query.middleware(BlockCheckMiddleware())

    dp.message.outer_middleware(SubscriptionMiddleware())
    dp.callback_query.outer_middleware(SubscriptionMiddleware())

    try:
        print("ÖzVeGas başlatılıyor...")
        await dp.start_polling(bot)

    finally:
        daily_task.cancel()

        try:
            await daily_task
        except asyncio.CancelledError:
            pass

        await bot.session.close()
        await close_database()

        print("ÖzVeGas kapatıldı.")


if __name__ == "__main__":
    asyncio.run(main())
