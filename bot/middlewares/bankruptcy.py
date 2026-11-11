
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


BANKRUPTCY_LIMIT = 4000


class BankruptcyMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):
        telegram_user = getattr(event, "from_user", None)

        if telegram_user is None:
            return await handler(event, data)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(
                    User.tg_id == telegram_user.id
                )
            )

            user = result.scalar_one_or_none()

            if user is None:
                return await handler(event, data)

            balance = user.balance or 0

        if balance < BANKRUPTCY_LIMIT:
            warning = (
                "💸 İFLAS ETTİN!\n\n"
                f"Mevcut bakiyen: {balance:,.2f} Sanal Kredi\n"
                f"İflas sınırı: {BANKRUPTCY_LIMIT:,} Sanal Kredi\n\n"
                "Oyunlara devam edebilmek için borç almalı "
                "veya bakiyeni artırmalısın.\n\n"
                "🪙 Borç işlemi için /borc komutunu kullan."
            )

            if isinstance(event, Message):
                await event.answer(warning)

            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "İflas ettin! Borç alana kadar oyun oynayamazsın.",
                    show_alert=True
                )

            return

        return await handler(event, data)
      
